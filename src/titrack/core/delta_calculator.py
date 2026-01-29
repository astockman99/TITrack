"""Delta calculator - compute item changes from slot state and events."""

from datetime import datetime
from typing import Optional

from titrack.core.models import (
    EventContext,
    ItemDelta,
    ParsedBagEvent,
    SlotKey,
    SlotState,
)


class DeltaCalculator:
    """
    Calculate item deltas by tracking slot state.

    Maintains in-memory state of all known slots and computes
    deltas when new BagMgr events arrive.
    """

    def __init__(self) -> None:
        # Current state of each slot: SlotKey -> SlotState
        self._slot_states: dict[SlotKey, SlotState] = {}

    def load_state(self, states: list[SlotState]) -> None:
        """
        Load existing slot states (e.g., from database on startup).

        Args:
            states: List of slot states to load
        """
        for state in states:
            self._slot_states[state.key] = state

    def get_state(self, key: SlotKey) -> Optional[SlotState]:
        """Get current state for a slot."""
        return self._slot_states.get(key)

    def get_all_states(self) -> list[SlotState]:
        """Get all current slot states."""
        return list(self._slot_states.values())

    def process_event(
        self,
        event: ParsedBagEvent,
        context: EventContext,
        proto_name: Optional[str],
        run_id: Optional[int],
        timestamp: Optional[datetime] = None,
        season_id: Optional[int] = None,
        player_id: Optional[str] = None,
    ) -> tuple[Optional[ItemDelta], SlotState]:
        """
        Process a bag event and compute the delta.

        Args:
            event: Parsed bag modification event
            context: Current context (PICK_ITEMS, OTHER)
            proto_name: Protocol name if in a context block
            run_id: Current run ID if in a run
            timestamp: Event timestamp (defaults to now)
            season_id: Current season/league ID
            player_id: Current player ID

        Returns:
            Tuple of (delta or None if no change, new slot state)
        """
        timestamp = timestamp or datetime.now()
        key = SlotKey(event.page_id, event.slot_id)
        old_state = self._slot_states.get(key)

        # Create new state
        new_state = SlotState(
            page_id=event.page_id,
            slot_id=event.slot_id,
            config_base_id=event.config_base_id,
            num=event.num,
            updated_at=timestamp,
            player_id=player_id,
        )

        # Update state
        self._slot_states[key] = new_state

        # Calculate delta
        if old_state is None:
            # New slot - entire amount is the delta
            if event.num == 0:
                # Empty slot, no delta
                return None, new_state
            delta = ItemDelta(
                page_id=event.page_id,
                slot_id=event.slot_id,
                config_base_id=event.config_base_id,
                delta=event.num,
                context=context,
                proto_name=proto_name,
                run_id=run_id,
                timestamp=timestamp,
                season_id=season_id,
                player_id=player_id,
            )
            return delta, new_state

        if old_state.config_base_id == event.config_base_id:
            # Same item type - delta is difference in quantity
            delta_amount = event.num - old_state.num
            if delta_amount == 0:
                return None, new_state
            delta = ItemDelta(
                page_id=event.page_id,
                slot_id=event.slot_id,
                config_base_id=event.config_base_id,
                delta=delta_amount,
                context=context,
                proto_name=proto_name,
                run_id=run_id,
                timestamp=timestamp,
                season_id=season_id,
                player_id=player_id,
            )
            return delta, new_state

        # Different item type - slot was swapped
        # Create delta for the new item (full amount as gain)
        # Note: We don't create a "loss" delta for the old item
        # because the old item was moved, not destroyed
        if event.num == 0:
            # Slot cleared
            return None, new_state
        delta = ItemDelta(
            page_id=event.page_id,
            slot_id=event.slot_id,
            config_base_id=event.config_base_id,
            delta=event.num,
            context=context,
            proto_name=proto_name,
            run_id=run_id,
            timestamp=timestamp,
            season_id=season_id,
            player_id=player_id,
        )
        return delta, new_state

    def clear_state(self) -> None:
        """Clear all slot state (for testing or reset)."""
        self._slot_states.clear()
