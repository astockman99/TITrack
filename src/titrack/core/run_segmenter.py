"""Run segmenter - track map run boundaries from level events."""

from datetime import datetime
from typing import Optional

from titrack.core.models import ParsedLevelEvent, Run
from titrack.parser.patterns import HUB_ZONE_PATTERNS


def is_hub_zone(level_info: str) -> bool:
    """
    Check if a level is a hub/town zone.

    Args:
        level_info: Level identifier string

    Returns:
        True if this is a hub zone
    """
    for pattern in HUB_ZONE_PATTERNS:
        if pattern.search(level_info):
            return True
    return False


class RunSegmenter:
    """
    Track run boundaries based on level events.

    A "run" starts when entering a non-hub zone and ends when
    entering a different zone (hub or map).
    """

    def __init__(self) -> None:
        self._current_run: Optional[Run] = None
        self._next_run_id: int = 1

    def set_next_run_id(self, run_id: int) -> None:
        """Set the next run ID (for loading from database)."""
        self._next_run_id = run_id

    def get_current_run(self) -> Optional[Run]:
        """Get the currently active run, if any."""
        return self._current_run

    def process_event(
        self,
        event: ParsedLevelEvent,
        timestamp: Optional[datetime] = None,
        level_id: Optional[int] = None,
        level_type: Optional[int] = None,
        level_uid: Optional[int] = None,
        season_id: Optional[int] = None,
        player_id: Optional[str] = None,
    ) -> tuple[Optional[Run], Optional[Run]]:
        """
        Process a level event and update run state.

        Args:
            event: Parsed level event
            timestamp: Event timestamp (defaults to now)
            level_id: Optional LevelId for zone differentiation
            level_type: Optional LevelType (3=normal, 11=nightmare)
            level_uid: Optional LevelUid (unique map instance ID)
            season_id: Optional season/league ID
            player_id: Optional player ID

        Returns:
            Tuple of (ended_run or None, new_run or None)
        """
        timestamp = timestamp or datetime.now()
        ended_run: Optional[Run] = None
        new_run: Optional[Run] = None

        # Only OpenMainWorld triggers run transitions (actual game format)
        if event.event_type != "OpenMainWorld":
            return None, None

        zone_sig = event.level_info
        is_hub = is_hub_zone(zone_sig)

        # End current run if exists
        if self._current_run is not None:
            self._current_run.end_ts = timestamp
            ended_run = self._current_run
            self._current_run = None

        # Start new run
        new_run = Run(
            id=self._next_run_id,
            zone_signature=zone_sig,
            start_ts=timestamp,
            end_ts=None,
            is_hub=is_hub,
            level_id=level_id,
            level_type=level_type,
            level_uid=level_uid,
            season_id=season_id,
            player_id=player_id,
        )
        self._next_run_id += 1
        self._current_run = new_run

        return ended_run, new_run

    def force_end_current_run(
        self, timestamp: Optional[datetime] = None
    ) -> Optional[Run]:
        """
        Force-end the current run (e.g., on shutdown).

        Args:
            timestamp: End timestamp (defaults to now)

        Returns:
            The ended run, or None if no active run
        """
        if self._current_run is None:
            return None
        timestamp = timestamp or datetime.now()
        self._current_run.end_ts = timestamp
        ended_run = self._current_run
        self._current_run = None
        return ended_run

    def load_active_run(self, run: Run) -> None:
        """Load an active run from database on startup."""
        self._current_run = run
