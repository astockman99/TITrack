"""Collector - main collection loop orchestrating parsing and storage."""

import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from titrack.core.delta_calculator import DeltaCalculator
from titrack.core.models import (
    EventContext,
    ItemDelta,
    ParsedBagEvent,
    ParsedContextMarker,
    ParsedLevelEvent,
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

        # Context tracking
        self._current_context = EventContext.OTHER
        self._current_proto_name: Optional[str] = None

        # Exchange price tracking: SynId -> ConfigBaseId
        self._pending_price_searches: dict[int, int] = {}

        self._running = False

    def initialize(self) -> None:
        """
        Initialize collector state from database.

        Loads slot states, active run, and log position.
        """
        # Load slot states
        states = self.repository.get_all_slot_states()
        self.delta_calc.load_state(states)

        # Load active run
        active_run = self.repository.get_active_run()
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
        elif isinstance(event, ParsedLevelEvent):
            self._handle_level_event(event, timestamp)

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
        """Handle BagMgr modification events."""
        current_run = self.run_segmenter.get_current_run()
        run_id = current_run.id if current_run and not current_run.is_hub else None

        delta, new_state = self.delta_calc.process_event(
            event=event,
            context=self._current_context,
            proto_name=self._current_proto_name,
            run_id=run_id,
            timestamp=timestamp,
        )

        # Persist slot state
        self.repository.upsert_slot_state(new_state)

        # Persist and notify delta
        if delta:
            self.repository.insert_delta(delta)
            if self._on_delta:
                self._on_delta(delta)

    def _handle_level_event(self, event: ParsedLevelEvent, timestamp: datetime) -> None:
        """Handle level transition events."""
        ended_run, new_run = self.run_segmenter.process_event(event, timestamp)

        if ended_run:
            self.repository.update_run_end(ended_run.id, ended_run.end_ts)
            if self._on_run_end:
                self._on_run_end(ended_run)

        if new_run:
            run_id = self.repository.insert_run(new_run)
            new_run.id = run_id
            if self._on_run_start:
                self._on_run_start(new_run)

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

            # Create and store price
            price = Price(
                config_base_id=config_base_id,
                price_fe=ref_price,
                source="exchange",
                updated_at=timestamp,
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
            if state.num > 0:
                totals[state.config_base_id] = totals.get(state.config_base_id, 0) + state.num
        return totals
