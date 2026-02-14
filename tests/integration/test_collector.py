"""Integration tests for the collector."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from titrack.collector.collector import Collector
from titrack.core.models import ItemDelta, Run
from titrack.data.inventory import set_gear_allowlist
from titrack.db.connection import Database
from titrack.db.repository import Repository
from titrack.parser.patterns import FE_CONFIG_BASE_ID
from titrack.parser.player_parser import PlayerInfo


# Test player info for setting player context
TEST_PLAYER_INFO = PlayerInfo(
    name="TestPlayer",
    level=100,
    season_id=1,
    hero_id=1,
    player_id="test_player_123",
)


SAMPLE_LOG = """\
[2026.01.26-10.00.00:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/XZ_YuJinZhiXiBiNanSuo200
[2026.01.26-10.00.05:000][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 500
[2026.01.26-10.01.00:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/02KD/KD_YuanSuKuangDong000/KD_YuanSuKuangDong000
[2026.01.26-10.01.30:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
[2026.01.26-10.01.30:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 550
[2026.01.26-10.01.30:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
[2026.01.26-10.02.00:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
[2026.01.26-10.02.00:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 625
[2026.01.26-10.02.00:002][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 1 ConfigBaseId = 200100 Num = 3
[2026.01.26-10.02.00:003][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
[2026.01.26-10.03.00:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
[2026.01.26-10.03.00:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 700
[2026.01.26-10.03.00:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
[2026.01.26-10.05.00:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/XZ_YuJinZhiXiBiNanSuo200
"""

# Sample log with InitBagData (inventory snapshot from sorting)
SAMPLE_LOG_WITH_INIT = """\
[2026.01.27-12.36.57:771][ 65]GameLog: Display: [Game] ItemChange@ ProtoName=ResetItemsLayout start
[2026.01.27-12.36.57:771][ 65]GameLog: Display: [Game] ItemChange@ Reset PageId=102
[2026.01.27-12.36.57:774][ 65]GameLog: Display: [Game] ItemChange@ ProtoName=ResetItemsLayout end
[2026.01.27-12.36.57:774][ 65]GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 609
[2026.01.27-12.36.57:776][ 65]GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 1 ConfigBaseId = 100200 Num = 999
[2026.01.27-12.36.57:776][ 65]GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 2 ConfigBaseId = 100200 Num = 442
[2026.01.27-12.36.57:776][ 65]GameLog: Display: [Game] BagMgr@:InitBagData PageId = 103 SlotId = 0 ConfigBaseId = 440004 Num = 2
[2026.01.27-12.36.57:776][ 65]GameLog: Display: [Game] BagMgr@:InitBagData PageId = 103 SlotId = 1 ConfigBaseId = 430000 Num = 20
"""


@pytest.fixture
def test_env():
    """Create a test environment with temp log file and database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create log file
        log_path = tmpdir / "test.log"
        log_path.write_text(SAMPLE_LOG)

        # Create database
        db_path = tmpdir / "test.db"
        db = Database(db_path, auto_seed=False)
        db.connect()

        yield {
            "tmpdir": tmpdir,
            "log_path": log_path,
            "db_path": db_path,
            "db": db,
        }

        db.close()


class TestCollectorIntegration:
    """Integration tests for full collector workflow."""

    def test_process_sample_log(self, test_env):
        """Test processing the sample log file."""
        db = test_env["db"]
        log_path = test_env["log_path"]

        deltas_received = []
        runs_started = []
        runs_ended = []

        collector = Collector(
            db=db,
            log_path=log_path,
            on_delta=lambda d: deltas_received.append(d),
            on_run_start=lambda r: runs_started.append(r),
            on_run_end=lambda r: runs_ended.append(r),
            player_info=TEST_PLAYER_INFO,
        )
        collector.initialize()
        line_count = collector.process_file(from_beginning=True)

        # Verify lines processed
        assert line_count > 0

        # Verify runs detected
        assert len(runs_started) >= 3  # Hub, Map, Hub

        # Verify deltas detected
        assert len(deltas_received) > 0

    def test_fe_tracking(self, test_env):
        """Test that FE gains are tracked correctly."""
        db = test_env["db"]
        log_path = test_env["log_path"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        collector = Collector(db=db, log_path=log_path, player_info=TEST_PLAYER_INFO)
        collector.initialize()
        collector.process_file(from_beginning=True)

        # Get inventory summary
        inventory = collector.get_inventory_summary()

        # We should have FE tracked
        # Initial 500, then gains of 50, 75, 75 = 700 final
        assert FE_CONFIG_BASE_ID in inventory
        assert inventory[FE_CONFIG_BASE_ID] == 700

    def test_run_segmentation(self, test_env):
        """Test that runs are properly segmented."""
        db = test_env["db"]
        log_path = test_env["log_path"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        collector = Collector(db=db, log_path=log_path, player_info=TEST_PLAYER_INFO)
        collector.initialize()
        collector.process_file(from_beginning=True)

        runs = repo.get_recent_runs(limit=10)

        # Should have runs for: Hub, Map, Hub
        assert len(runs) >= 3

        # Find the map run
        map_runs = [r for r in runs if not r.is_hub]
        assert len(map_runs) >= 1

        # The map run should have the FE deltas
        map_run = map_runs[0]
        summary = repo.get_run_summary(map_run.id)
        assert FE_CONFIG_BASE_ID in summary
        # Deltas during map run: 50 + 75 + 75 = 200
        assert summary[FE_CONFIG_BASE_ID] == 200

    def test_slot_state_persistence(self, test_env):
        """Test that slot state is persisted to database."""
        db = test_env["db"]
        log_path = test_env["log_path"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        collector = Collector(db=db, log_path=log_path, player_info=TEST_PLAYER_INFO)
        collector.initialize()
        collector.process_file(from_beginning=True)

        # Get slot state from DB
        states = repo.get_all_slot_states()
        assert len(states) >= 2  # FE slot and item slot

        # Verify FE slot state
        fe_state = repo.get_slot_state(102, 0)
        assert fe_state is not None
        assert fe_state.config_base_id == FE_CONFIG_BASE_ID
        assert fe_state.num == 700

    def test_resume_from_position(self, test_env):
        """Test resuming collection from saved position."""
        db = test_env["db"]
        log_path = test_env["log_path"]

        # First run
        collector1 = Collector(db=db, log_path=log_path, player_info=TEST_PLAYER_INFO)
        collector1.initialize()
        collector1.process_file(from_beginning=True)

        # Add more content to log
        with open(log_path, "a") as f:
            f.write(
                "[2026.01.26-10.10.00:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start\n"
            )
            f.write(
                "[2026.01.26-10.10.00:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 800\n"
            )
            f.write(
                "[2026.01.26-10.10.00:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end\n"
            )

        # Second run - should resume
        deltas = []
        collector2 = Collector(
            db=db,
            log_path=log_path,
            on_delta=lambda d: deltas.append(d),
            player_info=TEST_PLAYER_INFO,
        )
        collector2.initialize()
        collector2.process_file(from_beginning=False)

        # Should only process new deltas
        assert len(deltas) == 1
        assert deltas[0].delta == 100  # 800 - 700

    def test_context_tracking(self, test_env):
        """Test that PickItems context is tracked correctly."""
        db = test_env["db"]
        log_path = test_env["log_path"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        deltas = []
        collector = Collector(
            db=db,
            log_path=log_path,
            on_delta=lambda d: deltas.append(d),
            player_info=TEST_PLAYER_INFO,
        )
        collector.initialize()
        collector.process_file(from_beginning=True)

        # Find deltas with PickItems context
        pick_deltas = [d for d in deltas if d.proto_name == "PickItems"]
        other_deltas = [d for d in deltas if d.proto_name is None]

        # Most deltas should be from PickItems
        assert len(pick_deltas) > 0

    def test_init_bag_updates_state_without_delta(self, test_env):
        """Test that InitBagData events update slot state but don't create deltas."""
        db = test_env["db"]
        tmpdir = test_env["tmpdir"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        # Create log file with init data
        log_path = tmpdir / "init_test.log"
        log_path.write_text(SAMPLE_LOG_WITH_INIT)

        deltas_received = []
        collector = Collector(
            db=db,
            log_path=log_path,
            on_delta=lambda d: deltas_received.append(d),
            player_info=TEST_PLAYER_INFO,
        )
        collector.initialize()
        collector.process_file(from_beginning=True)

        # Should have no deltas (init events don't create deltas)
        assert len(deltas_received) == 0

        # But slot state should be updated
        states = repo.get_all_slot_states()
        assert len(states) == 5  # 3 slots in page 102, 2 in page 103

        # Verify FE slot (102, 0)
        fe_state = repo.get_slot_state(102, 0)
        assert fe_state is not None
        assert fe_state.config_base_id == FE_CONFIG_BASE_ID
        assert fe_state.num == 609

        # Verify other slot (102, 1)
        other_state = repo.get_slot_state(102, 1)
        assert other_state is not None
        assert other_state.config_base_id == 100200
        assert other_state.num == 999

        # Verify page 103 slot
        misc_state = repo.get_slot_state(103, 0)
        assert misc_state is not None
        assert misc_state.config_base_id == 440004
        assert misc_state.num == 2

    def test_exchange_events_update_state_without_delta(self, test_env):
        """Test that Push2/XchgReceive/ExchangeItem events update slot state but don't create deltas."""
        db = test_env["db"]
        tmpdir = test_env["tmpdir"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        # Seed initial slot state via an init line so the collector knows what's in slot 0
        log_content = """\
[2026.01.28-10.00.00:000][  0]GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 500
[2026.01.28-10.00.00:000][  0]GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 41 ConfigBaseId = 5144 Num = 10
[2026.01.28-10.01.00:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=Push2 start
[2026.01.28-10.01.00:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 1500
[2026.01.28-10.01.00:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=Push2 end
[2026.01.28-10.01.01:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=XchgReceive start
[2026.01.28-10.01.01:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 1500
[2026.01.28-10.01.01:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=XchgReceive end
[2026.01.28-10.02.00:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=ExchangeItem start
[2026.01.28-10.02.00:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 41 ConfigBaseId = 5144 Num = 14
[2026.01.28-10.02.00:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=ExchangeItem end
"""
        log_path = tmpdir / "exchange_test.log"
        log_path.write_text(log_content)

        deltas_received = []
        collector = Collector(
            db=db,
            log_path=log_path,
            on_delta=lambda d: deltas_received.append(d),
            player_info=TEST_PLAYER_INFO,
        )
        collector.initialize()
        collector.process_file(from_beginning=True)

        # No deltas should be created (exchange/recycle events are not loot)
        assert len(deltas_received) == 0

        # But slot state should reflect the trade house sale
        fe_state = repo.get_slot_state(102, 0)
        assert fe_state is not None
        assert fe_state.config_base_id == FE_CONFIG_BASE_ID
        assert fe_state.num == 1500

        # Slot state should reflect recycled items too
        recycle_state = repo.get_slot_state(102, 41)
        assert recycle_state is not None
        assert recycle_state.config_base_id == 5144
        assert recycle_state.num == 14

    def test_exchange_events_during_map_run_no_delta(self, test_env):
        """Test that exchange events inside a map run don't create deltas."""
        db = test_env["db"]
        tmpdir = test_env["tmpdir"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        # Enter a map, pick up some FE, then collect a trade house sale, pick up more
        log_content = """\
[2026.01.28-10.00.00:000][  0]GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 500
[2026.01.28-10.00.05:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/02KD/KD_YuanSuKuangDong000/KD_YuanSuKuangDong000
[2026.01.28-10.00.30:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
[2026.01.28-10.00.30:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 550
[2026.01.28-10.00.30:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
[2026.01.28-10.01.00:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=Push2 start
[2026.01.28-10.01.00:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 1550
[2026.01.28-10.01.00:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=Push2 end
[2026.01.28-10.01.30:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
[2026.01.28-10.01.30:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 1600
[2026.01.28-10.01.30:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
[2026.01.28-10.05.00:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/XZ_YuJinZhiXiBiNanSuo200
"""
        log_path = tmpdir / "exchange_in_map.log"
        log_path.write_text(log_content)

        deltas_received = []
        collector = Collector(
            db=db,
            log_path=log_path,
            on_delta=lambda d: deltas_received.append(d),
            player_info=TEST_PLAYER_INFO,
        )
        collector.initialize()
        collector.process_file(from_beginning=True)

        # Only PickItems deltas should exist (50 + 50 = 100 FE from loot)
        assert all(d.proto_name == "PickItems" for d in deltas_received)
        total_loot = sum(d.delta for d in deltas_received)
        assert total_loot == 100  # 50 from first pickup + 50 from second pickup

        # Final slot state should include the exchange amount
        fe_state = repo.get_slot_state(102, 0)
        assert fe_state.num == 1600

        # Verify the map run only has 100 FE of loot, not 1100
        runs = repo.get_recent_runs(limit=10)
        map_runs = [r for r in runs if not r.is_hub]
        assert len(map_runs) >= 1
        map_run = map_runs[0]
        summary = repo.get_run_summary(map_run.id)
        assert summary[FE_CONFIG_BASE_ID] == 100

    def test_init_bag_followed_by_pickup(self, test_env):
        """Test that init events set baseline for subsequent pickup deltas."""
        db = test_env["db"]
        tmpdir = test_env["tmpdir"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        # Create log file: init snapshot, then a pickup
        log_content = """\
[2026.01.27-12.36.57:774][ 65]GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 500
[2026.01.27-12.37.00:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
[2026.01.27-12.37.00:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 550
[2026.01.27-12.37.00:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
"""
        log_path = tmpdir / "init_then_pickup.log"
        log_path.write_text(log_content)

        deltas_received = []
        collector = Collector(
            db=db,
            log_path=log_path,
            on_delta=lambda d: deltas_received.append(d),
            player_info=TEST_PLAYER_INFO,
        )
        collector.initialize()
        collector.process_file(from_beginning=True)

        # Should have exactly 1 delta (from the pickup, not from init)
        assert len(deltas_received) == 1
        assert deltas_received[0].delta == 50  # 550 - 500
        assert deltas_received[0].config_base_id == FE_CONFIG_BASE_ID
        assert deltas_received[0].proto_name == "PickItems"

        # Final state should be 550
        fe_state = repo.get_slot_state(102, 0)
        assert fe_state.num == 550

    def test_gear_items_excluded_by_default(self, test_env):
        """Test that gear page items (PageId 100) are excluded when not in allowlist."""
        db = test_env["db"]
        tmpdir = test_env["tmpdir"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        log_content = """\
[2026.01.28-10.00.00:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/02KD/KD_YuanSuKuangDong000/KD_YuanSuKuangDong000
[2026.01.28-10.00.30:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
[2026.01.28-10.00.30:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 100 SlotId = 5 ConfigBaseId = 999001 Num = 1
[2026.01.28-10.00.30:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
[2026.01.28-10.05.00:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/XZ_YuJinZhiXiBiNanSuo200
"""
        log_path = tmpdir / "gear_excluded.log"
        log_path.write_text(log_content)

        deltas_received = []
        collector = Collector(
            db=db,
            log_path=log_path,
            on_delta=lambda d: deltas_received.append(d),
            player_info=TEST_PLAYER_INFO,
        )
        collector.initialize()
        collector.process_file(from_beginning=True)

        # No deltas — gear page is excluded
        assert len(deltas_received) == 0

        # Slot state should NOT be tracked
        states = repo.get_all_slot_states()
        gear_states = [s for s in states if s.page_id == 100]
        assert len(gear_states) == 0

    def test_allowed_gear_items_tracked(self, test_env):
        """Test that allowlisted gear items (PageId 100) create deltas."""
        db = test_env["db"]
        tmpdir = test_env["tmpdir"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        # Add item 999001 to allowlist
        set_gear_allowlist(frozenset([999001]))

        log_content = """\
[2026.01.28-10.00.00:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/02KD/KD_YuanSuKuangDong000/KD_YuanSuKuangDong000
[2026.01.28-10.00.30:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
[2026.01.28-10.00.30:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 100 SlotId = 5 ConfigBaseId = 999001 Num = 1
[2026.01.28-10.00.30:002][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
[2026.01.28-10.05.00:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/XZ_YuJinZhiXiBiNanSuo200
"""
        log_path = tmpdir / "gear_allowed.log"
        log_path.write_text(log_content)

        deltas_received = []
        collector = Collector(
            db=db,
            log_path=log_path,
            on_delta=lambda d: deltas_received.append(d),
            player_info=TEST_PLAYER_INFO,
        )
        collector.initialize()
        collector.process_file(from_beginning=True)

        # Delta should be created for the allowlisted gear item
        assert len(deltas_received) == 1
        assert deltas_received[0].config_base_id == 999001
        assert deltas_received[0].page_id == 100
        assert deltas_received[0].delta == 1

    def test_gear_non_allowed_items_still_excluded(self, test_env):
        """Test that non-allowlisted gear items are still excluded even when allowlist is populated."""
        db = test_env["db"]
        tmpdir = test_env["tmpdir"]
        repo = Repository(db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, TEST_PLAYER_INFO.player_id)

        # Only 999001 is allowed, not 999002
        set_gear_allowlist(frozenset([999001]))

        log_content = """\
[2026.01.28-10.00.00:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/02KD/KD_YuanSuKuangDong000/KD_YuanSuKuangDong000
[2026.01.28-10.00.30:000][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
[2026.01.28-10.00.30:001][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 100 SlotId = 5 ConfigBaseId = 999001 Num = 1
[2026.01.28-10.00.30:002][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 100 SlotId = 6 ConfigBaseId = 999002 Num = 1
[2026.01.28-10.00.30:003][  0]GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
[2026.01.28-10.05.00:000][  0]GameLog: Display: [Game] SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/XZ_YuJinZhiXiBiNanSuo200
"""
        log_path = tmpdir / "gear_mixed.log"
        log_path.write_text(log_content)

        deltas_received = []
        collector = Collector(
            db=db,
            log_path=log_path,
            on_delta=lambda d: deltas_received.append(d),
            player_info=TEST_PLAYER_INFO,
        )
        collector.initialize()
        collector.process_file(from_beginning=True)

        # Only the allowlisted item should create a delta
        assert len(deltas_received) == 1
        assert deltas_received[0].config_base_id == 999001
