"""Tests for run segmenter."""

from datetime import datetime

import pytest

from titrack.core.models import ParsedLevelEvent, Run
from titrack.core.run_segmenter import RunSegmenter, is_hub_zone
from titrack.data.zones import SANDLORD_LEVEL_IDS, is_sandlord_zone


class TestIsHubZone:
    """Tests for hub zone detection."""

    def test_detects_hub(self):
        assert is_hub_zone("MainHub_Social") is True

    def test_detects_town(self):
        assert is_hub_zone("Town_Central") is True

    def test_detects_hideout(self):
        assert is_hub_zone("Player_Hideout") is True

    def test_map_is_not_hub(self):
        assert is_hub_zone("Map_Desert_T16_001") is False

    def test_case_insensitive(self):
        assert is_hub_zone("MAINHUB_social") is True

    def test_detects_embers_rest(self):
        # Real game path for Ember's Rest hideout
        assert is_hub_zone("/Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200") is True

    def test_map_zone_not_hub(self):
        # Real game path for a map zone
        assert is_hub_zone("/Game/Art/Maps/02KD/KD_YuanSuKuangDong000") is False


@pytest.fixture
def segmenter():
    """Create a fresh segmenter for each test."""
    return RunSegmenter()


class TestRunSegmenter:
    """Tests for RunSegmenter."""

    def test_enter_map_starts_run(self, segmenter):
        event = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="Map_Desert_T16_001",
            raw_line="test",
        )
        ended, new = segmenter.process_event(event)

        assert ended is None  # No previous run
        assert new is not None
        assert new.zone_signature == "Map_Desert_T16_001"
        assert new.is_hub is False
        assert new.is_active is True

    def test_enter_hub_creates_hub_run(self, segmenter):
        event = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="MainHub_Social",
            raw_line="test",
        )
        ended, new = segmenter.process_event(event)

        assert new is not None
        assert new.is_hub is True

    def test_transition_ends_previous_run(self, segmenter):
        ts1 = datetime(2026, 1, 26, 10, 0, 0)
        ts2 = datetime(2026, 1, 26, 10, 5, 0)

        event1 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="Map_Desert_T16_001",
            raw_line="test",
        )
        segmenter.process_event(event1, timestamp=ts1)

        event2 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="MainHub_Social",
            raw_line="test",
        )
        ended, new = segmenter.process_event(event2, timestamp=ts2)

        assert ended is not None
        assert ended.zone_signature == "Map_Desert_T16_001"
        assert ended.end_ts == ts2
        assert ended.duration_seconds == 300  # 5 minutes

    def test_other_event_types_do_not_trigger_run(self, segmenter):
        # Only OpenMainWorld should trigger runs
        event = ParsedLevelEvent(
            event_type="SomeOtherEvent",
            level_info="Map_Desert_T16_001",
            raw_line="test",
        )
        ended, new = segmenter.process_event(event)

        assert ended is None
        assert new is None

    def test_run_ids_increment(self, segmenter):
        event1 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="Map_1",
            raw_line="test",
        )
        _, run1 = segmenter.process_event(event1)

        event2 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="Map_2",
            raw_line="test",
        )
        _, run2 = segmenter.process_event(event2)

        assert run1.id == 1
        assert run2.id == 2

    def test_force_end_current_run(self, segmenter):
        event = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="Map_Desert_T16_001",
            raw_line="test",
        )
        segmenter.process_event(event)

        ended = segmenter.force_end_current_run()
        assert ended is not None
        assert ended.end_ts is not None
        assert segmenter.get_current_run() is None

    def test_force_end_no_run_returns_none(self, segmenter):
        ended = segmenter.force_end_current_run()
        assert ended is None

    def test_set_next_run_id(self, segmenter):
        segmenter.set_next_run_id(100)

        event = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="Map_1",
            raw_line="test",
        )
        _, run = segmenter.process_event(event)

        assert run.id == 100

    def test_load_active_run(self, segmenter):
        run = Run(
            id=50,
            zone_signature="Map_Test",
            start_ts=datetime.now(),
            end_ts=None,
            is_hub=False,
        )
        segmenter.load_active_run(run)

        assert segmenter.get_current_run() == run

    def test_sandlord_zone_transition_does_not_create_new_run(self, segmenter):
        """Transitioning between sandlord zones should keep the same run."""
        ts1 = datetime(2026, 2, 21, 12, 28, 0)
        ts2 = datetime(2026, 2, 21, 12, 29, 0)

        # Enter Cloud Oasis (LevelId 9999999)
        event1 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="/Game/Art/Season/S10/Maps/YunDuanLvZhou/YunDuanLvZhou",
            raw_line="test",
        )
        _, oasis_run = segmenter.process_event(
            event1, timestamp=ts1, level_id=9999999, level_type=21
        )
        assert oasis_run is not None
        assert oasis_run.level_id == 9999999

        # Transition to Quicksand Treasure Stash (LevelId 9999997) — should NOT create new run
        event2 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="/Game/Art/Maps/06SQ/SQ_NvShenQunBai100/SQ_NvShenQunBai100",
            raw_line="test",
        )
        ended, new = segmenter.process_event(
            event2, timestamp=ts2, level_id=9999997, level_type=22
        )
        assert ended is None
        assert new is None
        # The original oasis run should still be active
        assert segmenter.get_current_run() is oasis_run
        assert oasis_run.end_ts is None

    def test_sandlord_to_hub_ends_run(self, segmenter):
        """Leaving a sandlord zone for a hub should end the run normally."""
        ts1 = datetime(2026, 2, 21, 12, 28, 0)
        ts2 = datetime(2026, 2, 21, 12, 35, 0)

        event1 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="/Game/Art/Season/S10/Maps/YunDuanLvZhou/YunDuanLvZhou",
            raw_line="test",
        )
        segmenter.process_event(event1, timestamp=ts1, level_id=9999999)

        event2 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="/Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/XZ_YuJinZhiXiBiNanSuo200",
            raw_line="test",
        )
        ended, new = segmenter.process_event(event2, timestamp=ts2)

        assert ended is not None
        assert ended.level_id == 9999999
        assert ended.end_ts == ts2
        assert new is not None
        assert new.is_hub is True

    def test_sandlord_round_trip_stays_one_run(self, segmenter):
        """Cloud Oasis -> Quicksand -> Cloud Oasis should be one continuous run."""
        ts1 = datetime(2026, 2, 21, 12, 28, 0)
        ts2 = datetime(2026, 2, 21, 12, 29, 0)
        ts3 = datetime(2026, 2, 21, 12, 30, 0)

        # Enter Cloud Oasis
        event1 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="/Game/Art/Season/S10/Maps/YunDuanLvZhou/YunDuanLvZhou",
            raw_line="test",
        )
        _, oasis_run = segmenter.process_event(
            event1, timestamp=ts1, level_id=9999999
        )

        # Go to Quicksand
        event2 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="/Game/Art/Maps/06SQ/SQ_NvShenQunBai100/SQ_NvShenQunBai100",
            raw_line="test",
        )
        segmenter.process_event(event2, timestamp=ts2, level_id=9999997)

        # Return to Cloud Oasis
        event3 = ParsedLevelEvent(
            event_type="OpenMainWorld",
            level_info="/Game/Art/Season/S10/Maps/YunDuanLvZhou/YunDuanLvZhou",
            raw_line="test",
        )
        ended, new = segmenter.process_event(event3, timestamp=ts3, level_id=9999999)

        assert ended is None
        assert new is None
        # Still the same original run
        assert segmenter.get_current_run() is oasis_run
        assert oasis_run.id == 1  # Run ID didn't change


class TestSandlordZone:
    """Tests for sandlord zone detection."""

    def test_cloud_oasis_is_sandlord(self):
        assert is_sandlord_zone(9999999) is True

    def test_quicksand_treasure_stash_is_sandlord(self):
        assert is_sandlord_zone(9999997) is True

    def test_normal_map_not_sandlord(self):
        assert is_sandlord_zone(4606) is False

    def test_none_not_sandlord(self):
        assert is_sandlord_zone(None) is False

    def test_hub_not_sandlord(self):
        assert is_sandlord_zone(110) is False
