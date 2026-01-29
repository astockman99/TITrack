"""Collector - main collection loop orchestrating parsing and storage."""

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from titrack.core.delta_calculator import DeltaCalculator
from titrack.core.models import (
    EventContext,
    ItemDelta,
    ParsedBagEvent,
    ParsedContextMarker,
    ParsedLevelEvent,
    ParsedLevelIdEvent,
    ParsedPlayerDataEvent,
    Price,
    Run,
)
from titrack.core.run_segmenter import RunSegmenter
from titrack.db.connection import Database
from titrack.db.repository import Repository
from titrack.parser.log_parser import parse_line
from titrack.parser.log_tailer import LogTailer
from titrack.parser.exchange_parser import (
    ExchangeMessageParser,
    ExchangePriceRequest,
    ExchangePriceResponse,
    calculate_reference_price,
)
from titrack.parser.player_parser import PlayerInfo, get_effective_player_id
from titrack.data.inventory import EXCLUDED_PAGES


class Collector:
    """
    Main collector that ties all components together.

    Watches log file, parses events, computes deltas,
    tracks runs, and persists everything to database.
    """

    def __init__(
        self,
        db: Database,
        log_path: Path,
        on_delta: Optional[Callable[[ItemDelta], None]] = None,
        on_run_start: Optional[Callable[[Run], None]] = None,
        on_run_end: Optional[Callable[[Run], None]] = None,
        on_price_update: Optional[Callable[[Price], None]] = None,
        on_player_change: Optional[Callable[[PlayerInfo], None]] = None,
        player_info: Optional[PlayerInfo] = None,
    ) -> None:
        """
        Initialize collector.

        Args:
            db: Database connection
            log_path: Path to game log file
            on_delta: Callback for each delta (for live display)
            on_run_start: Callback when a run starts
            on_run_end: Callback when a run ends
            on_price_update: Callback when a price is learned from exchange
            on_player_change: Callback when player/character changes
            player_info: Current player info for data isolation
        """
        self.db = db
        self.repository = Repository(db)
        self.tailer = LogTailer(log_path)
        self.delta_calc = DeltaCalculator()
        self.run_segmenter = RunSegmenter()
        self.exchange_parser = ExchangeMessageParser()

        self._on_delta = on_delta
        self._on_run_start = on_run_start
        self._on_run_end = on_run_end
        self._on_price_update = on_price_update
        self._on_player_change = on_player_change

        # Player context for data isolation
        self._player_info = player_info
        self._season_id: Optional[int] = player_info.season_id if player_info else None
        # Use effective_player_id: actual player_id if available, otherwise "season_name" as identifier
        # This ensures different characters have separate inventories even if player_id isn't in logs
        self._player_id: Optional[str] = get_effective_player_id(player_info)

        # Set repository player context for filtered queries
        self.repository.set_player_context(self._season_id, self._player_id)

        # Track pending player data from streaming log (for character change detection)
        self._pending_player_data: dict[str, any] = {}
        self._player_data_last_update: Optional[datetime] = None
        self._player_data_batch_threshold_seconds = 2.0  # New player data if > 2 seconds gap

        # Context tracking
        self._current_context = EventContext.OTHER
        self._current_proto_name: Optional[str] = None

        # LevelId/LevelType/LevelUid tracking (for zone differentiation)
        self._pending_level_id: Optional[int] = None
        self._pending_level_type: Optional[int] = None
        self._pending_level_uid: Optional[int] = None

        # Exchange price tracking: SynId -> ConfigBaseId
        self._pending_price_searches: dict[int, int] = {}

        # InitBagData batch tracking: page_id -> last init timestamp
        # Used to detect new init batches and clear stale slot states
        self._last_init_page: Optional[int] = None
        self._last_init_time: Optional[datetime] = None
        self._init_batch_threshold_seconds = 2.0  # New batch if > 2 seconds gap

        self._running = False

    def initialize(self) -> None:
        """
        Initialize collector state from database.

        Loads slot states, active run, and log position.
        """
        # Load slot states (filtered by player_id if set)
        states = self.repository.get_all_slot_states(player_id=self._player_id)
        self.delta_calc.load_state(states)

        # Load active run (filtered by season/player if set)
        active_run = self.repository.get_active_run(
            season_id=self._season_id, player_id=self._player_id
        )
        if active_run:
            self.run_segmenter.load_active_run(active_run)

        # Set next run ID
        max_run_id = self.repository.get_max_run_id()
        self.run_segmenter.set_next_run_id(max_run_id + 1)

        # Load log position and apply to tailer
        position_data = self.repository.get_log_position()
        if position_data:
            file_path, position, file_size = position_data
            if file_path == self.tailer.file_path:
                self.tailer.set_position(position, file_size)

    def _process_player_change(self, new_player_info: PlayerInfo) -> bool:
        """
        Process a detected player/character change.

        Args:
            new_player_info: The new player info detected from logs

        Returns:
            True if player changed and context was updated, False otherwise.
        """
        # Get effective player IDs for comparison
        old_effective_id = self._player_id
        new_effective_id = get_effective_player_id(new_player_info)

        # Check if player actually changed
        old_season_id = self._season_id
        old_name = self._player_info.name if self._player_info else None
        new_season_id = new_player_info.season_id
        new_name = new_player_info.name

        # Consider it the same player if effective player_id matches
        # (this now incorporates season + name when actual player_id is unavailable)
        same_player = old_effective_id == new_effective_id

        if same_player:
            # Same player, just update level if changed
            self._player_info = new_player_info
            return False

        # Player changed! Update context
        print(f"Player change detected: {old_name or 'None'} -> {new_name} ({new_player_info.season_name})")

        self._player_info = new_player_info
        self._season_id = new_season_id
        self._player_id = new_effective_id

        # Update repository context
        self.repository.set_player_context(self._season_id, self._player_id)

        # End any active run from the old character
        ended_run = self.run_segmenter.force_end_current_run()
        if ended_run:
            self.repository.update_run_end(ended_run.id, ended_run.end_ts)

        # Clear and reload slot states for new player
        self.delta_calc.clear_state()
        states = self.repository.get_all_slot_states(player_id=self._player_id)
        self.delta_calc.load_state(states)

        # Notify callback if registered
        if self._on_player_change:
            self._on_player_change(new_player_info)

        return True

    def reinitialize(self) -> None:
        """
        Reinitialize collector state from database.

        Call this after clearing run data to sync in-memory state.
        """
        # Reset run segmenter
        self.run_segmenter._current_run = None
        max_run_id = self.repository.get_max_run_id()
        self.run_segmenter.set_next_run_id(max_run_id + 1)

        # Reload slot states
        states = self.repository.get_all_slot_states()
        self.delta_calc.load_state(states)

        # Load log position
        position_data = self.repository.get_log_position()
        if position_data:
            file_path, position, file_size = position_data
            if file_path == self.tailer.file_path:
                self.tailer.set_position(position, file_size)

    def clear_run_data(self) -> int:
        """
        Clear all run tracking data using the collector's database connection.

        This ensures data is cleared in the same connection the collector uses.
        Also updates log position to current end so old events aren't re-parsed.

        Returns:
            Number of runs deleted.
        """
        # Clear database
        runs_deleted = self.repository.clear_run_data()

        # Reset in-memory state
        self.run_segmenter._current_run = None
        self.run_segmenter.set_next_run_id(1)

        # Update log position to current position so we don't re-parse old events
        self.repository.save_log_position(
            self.tailer.file_path,
            self.tailer.position,
            self.tailer.file_size
        )

        return runs_deleted

    def process_line(self, line: str, timestamp: Optional[datetime] = None) -> None:
        """
        Process a single log line.

        Args:
            line: Raw log line
            timestamp: Event timestamp (defaults to now)
        """
        timestamp = timestamp or datetime.now()

        # Try exchange message parsing first (multi-line stateful)
        exchange_event = self.exchange_parser.parse_line(line)
        if exchange_event is not None:
            self._handle_exchange_event(exchange_event, timestamp)

        # Standard single-line event parsing
        event = parse_line(line)

        if event is None:
            return

        if isinstance(event, ParsedContextMarker):
            self._handle_context_marker(event)
        elif isinstance(event, ParsedBagEvent):
            self._handle_bag_event(event, timestamp)
        elif isinstance(event, ParsedLevelIdEvent):
            # Store LevelId, LevelType, and LevelUid for the upcoming level event
            self._pending_level_id = event.level_id
            self._pending_level_type = event.level_type
            self._pending_level_uid = event.level_uid
        elif isinstance(event, ParsedLevelEvent):
            self._handle_level_event(event, timestamp)
        elif isinstance(event, ParsedPlayerDataEvent):
            self._handle_player_data_event(event, timestamp)

    def _handle_context_marker(self, event: ParsedContextMarker) -> None:
        """Handle ItemChange context markers."""
        if event.is_start:
            if event.proto_name == "PickItems":
                self._current_context = EventContext.PICK_ITEMS
            self._current_proto_name = event.proto_name
        else:
            self._current_context = EventContext.OTHER
            self._current_proto_name = None

    def _handle_bag_event(self, event: ParsedBagEvent, timestamp: datetime) -> None:
        """Handle BagMgr modification and init events."""
        # Skip excluded inventory pages (e.g., Gear tab - prices not reliable)
        if event.page_id in EXCLUDED_PAGES:
            return

        # Handle InitBagData batch detection - clear stale slots when new batch starts
        if event.is_init:
            is_new_batch = (
                self._last_init_page != event.page_id
                or self._last_init_time is None
                or (timestamp - self._last_init_time).total_seconds() > self._init_batch_threshold_seconds
            )

            if is_new_batch:
                # Clear all slot states for this page and player (both DB and in-memory)
                self.repository.clear_page_slot_states(event.page_id, player_id=self._player_id)
                # Clear from delta calculator's in-memory state
                keys_to_remove = [
                    key for key in self.delta_calc._slot_states
                    if key.page_id == event.page_id
                ]
                for key in keys_to_remove:
                    del self.delta_calc._slot_states[key]

            self._last_init_page = event.page_id
            self._last_init_time = timestamp

        current_run = self.run_segmenter.get_current_run()
        run_id = current_run.id if current_run and not current_run.is_hub else None

        delta, new_state = self.delta_calc.process_event(
            event=event,
            context=self._current_context,
            proto_name=self._current_proto_name,
            run_id=run_id,
            timestamp=timestamp,
            season_id=self._season_id,
            player_id=self._player_id,
        )

        # Persist slot state
        self.repository.upsert_slot_state(new_state)

        # For init events (inventory snapshot), only update slot state, don't create deltas
        # This prevents pollution of loot tracking when user sorts inventory
        if event.is_init:
            return

        # Persist and notify delta
        if delta:
            self.repository.insert_delta(delta)
            if self._on_delta:
                self._on_delta(delta)

    def _handle_level_event(self, event: ParsedLevelEvent, timestamp: datetime) -> None:
        """Handle level transition events."""
        # Use pending level_id/level_type/level_uid if available
        level_id = self._pending_level_id
        level_type = self._pending_level_type
        level_uid = self._pending_level_uid
        self._pending_level_id = None  # Clear after use
        self._pending_level_type = None
        self._pending_level_uid = None

        ended_run, new_run = self.run_segmenter.process_event(
            event, timestamp, level_id, level_type, level_uid,
            season_id=self._season_id, player_id=self._player_id
        )

        # DEBUG: Print zone transitions to console
        if new_run:
            hub_status = "[HUB]" if new_run.is_hub else "[MAP]"
            level_info = f" (LevelId={new_run.level_id})" if new_run.level_id else ""
            nightmare_tag = " [NIGHTMARE]" if new_run.level_type == 11 else ""
            print(f"ZONE: {hub_status} {new_run.zone_signature}{level_info}{nightmare_tag}")

        if ended_run:
            self.repository.update_run_end(ended_run.id, ended_run.end_ts)
            if self._on_run_end:
                self._on_run_end(ended_run)

        if new_run:
            run_id = self.repository.insert_run(new_run)
            new_run.id = run_id
            if self._on_run_start:
                self._on_run_start(new_run)

    def _handle_player_data_event(
        self, event: ParsedPlayerDataEvent, timestamp: datetime
    ) -> None:
        """Handle player data from streaming log (for character change detection)."""
        # Check if this is a new batch of player data (time gap > threshold)
        is_new_batch = (
            self._player_data_last_update is None
            or (timestamp - self._player_data_last_update).total_seconds()
            > self._player_data_batch_threshold_seconds
        )

        if is_new_batch:
            # Start fresh accumulation
            self._pending_player_data = {}

        self._player_data_last_update = timestamp

        # Accumulate fields from this event
        if event.name is not None:
            self._pending_player_data["name"] = event.name
        if event.level is not None:
            self._pending_player_data["level"] = event.level
        if event.season_id is not None:
            self._pending_player_data["season_id"] = event.season_id
        if event.hero_id is not None:
            self._pending_player_data["hero_id"] = event.hero_id
        if event.player_id is not None:
            self._pending_player_data["player_id"] = event.player_id

        # Check if we have enough data to identify a player (name + season_id minimum)
        if "name" in self._pending_player_data and "season_id" in self._pending_player_data:
            new_player_info = PlayerInfo(
                name=self._pending_player_data["name"],
                level=self._pending_player_data.get("level", 0),
                season_id=self._pending_player_data["season_id"],
                hero_id=self._pending_player_data.get("hero_id", 0),
                player_id=self._pending_player_data.get("player_id"),
            )

            # Process potential player change
            changed = self._process_player_change(new_player_info)
            if changed:
                # Clear pending data after successful change
                self._pending_player_data = {}

    def _handle_exchange_event(
        self,
        event: ExchangePriceRequest | ExchangePriceResponse,
        timestamp: datetime,
    ) -> None:
        """Handle exchange price search events."""
        if isinstance(event, ExchangePriceRequest):
            # Store pending search for correlation
            self._pending_price_searches[event.syn_id] = event.config_base_id

        elif isinstance(event, ExchangePriceResponse):
            # Find the corresponding request
            config_base_id = self._pending_price_searches.pop(event.syn_id, None)
            if config_base_id is None:
                return  # No matching request found

            if not event.prices_fe:
                return  # No prices to process

            # Calculate reference price (10th percentile by default)
            ref_price = calculate_reference_price(event.prices_fe, method="percentile_10")

            # Create and store price (tagged with season_id for isolation)
            price = Price(
                config_base_id=config_base_id,
                price_fe=ref_price,
                source="exchange",
                updated_at=timestamp,
                season_id=self._season_id,
            )
            self.repository.upsert_price(price)

            # Notify callback
            if self._on_price_update:
                self._on_price_update(price)

    def process_file(self, from_beginning: bool = False) -> int:
        """
        Process the entire log file (non-blocking).

        Args:
            from_beginning: If True, read from start; otherwise from last position

        Returns:
            Number of lines processed
        """
        if from_beginning:
            self.tailer.reset()

        line_count = 0
        for line in self.tailer.read_new_lines():
            self.process_line(line)
            line_count += 1

        # Save position
        self.repository.save_log_position(
            self.tailer.file_path,
            self.tailer.position,
            self.tailer.file_size,
        )

        return line_count

    def tail(self, poll_interval: float = 0.5) -> None:
        """
        Continuously tail the log file.

        Args:
            poll_interval: Seconds between file checks
        """
        self._running = True
        while self._running:
            line_count = self.process_file()
            if line_count == 0:
                time.sleep(poll_interval)

    def stop(self) -> None:
        """Stop the tail loop."""
        self._running = False

        # End any active run
        ended_run = self.run_segmenter.force_end_current_run()
        if ended_run:
            self.repository.update_run_end(ended_run.id, ended_run.end_ts)

    def get_inventory_summary(self) -> dict[int, int]:
        """
        Get current inventory totals by item.

        Returns:
            Dict mapping config_base_id -> total quantity
        """
        states = self.delta_calc.get_all_states()
        totals: dict[int, int] = {}
        for state in states:
            # Skip excluded pages (e.g., Gear)
            if state.page_id in EXCLUDED_PAGES:
                continue
            if state.num > 0:
                totals[state.config_base_id] = totals.get(state.config_base_id, 0) + state.num
        return totals
