"""Tests for database repository."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from titrack.core.models import (
    EventContext,
    Item,
    ItemDelta,
    Price,
    Run,
    SlotState,
)
from titrack.data.inventory import set_gear_allowlist
from titrack.db.connection import Database
from titrack.db.repository import Repository


@pytest.fixture
def db():
    """Create a temporary database for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = Database(db_path, auto_seed=False)
        database.connect()
        yield database
        database.close()


@pytest.fixture
def repo(db):
    """Create a repository for each test."""
    repo = Repository(db)
    # Set a test player context so queries return results
    repo.set_player_context(season_id=1, player_id="test_player")
    return repo


class TestSettingsRepository:
    """Tests for settings CRUD."""

    def test_set_and_get_setting(self, repo):
        repo.set_setting("test_key", "test_value")
        value = repo.get_setting("test_key")
        assert value == "test_value"

    def test_get_nonexistent_setting(self, repo):
        value = repo.get_setting("nonexistent")
        assert value is None

    def test_update_setting(self, repo):
        repo.set_setting("key", "value1")
        repo.set_setting("key", "value2")
        assert repo.get_setting("key") == "value2"


class TestRunsRepository:
    """Tests for runs CRUD."""

    def test_insert_and_get_run(self, repo):
        run = Run(
            id=None,
            zone_signature="Map_Test",
            start_ts=datetime(2026, 1, 26, 10, 0, 0),
            end_ts=None,
            is_hub=False,
        )
        run_id = repo.insert_run(run)
        assert run_id > 0

        fetched = repo.get_run(run_id)
        assert fetched is not None
        assert fetched.zone_signature == "Map_Test"
        assert fetched.is_hub is False

    def test_update_run_end(self, repo):
        run = Run(
            id=None,
            zone_signature="Map_Test",
            start_ts=datetime(2026, 1, 26, 10, 0, 0),
            end_ts=None,
            is_hub=False,
        )
        run_id = repo.insert_run(run)

        end_ts = datetime(2026, 1, 26, 10, 5, 0)
        repo.update_run_end(run_id, end_ts)

        fetched = repo.get_run(run_id)
        assert fetched.end_ts == end_ts

    def test_get_active_run(self, repo):
        # Insert ended run
        run1 = Run(
            id=None,
            zone_signature="Map_1",
            start_ts=datetime(2026, 1, 26, 9, 0, 0),
            end_ts=datetime(2026, 1, 26, 9, 5, 0),
            is_hub=False,
        )
        repo.insert_run(run1)

        # Insert active run
        run2 = Run(
            id=None,
            zone_signature="Map_2",
            start_ts=datetime(2026, 1, 26, 10, 0, 0),
            end_ts=None,
            is_hub=False,
        )
        run2_id = repo.insert_run(run2)

        active = repo.get_active_run()
        assert active is not None
        assert active.id == run2_id

    def test_get_recent_runs(self, repo):
        for i in range(5):
            run = Run(
                id=None,
                zone_signature=f"Map_{i}",
                start_ts=datetime(2026, 1, 26, i, 0, 0),
                end_ts=None,
                is_hub=False,
            )
            repo.insert_run(run)

        runs = repo.get_recent_runs(limit=3)
        assert len(runs) == 3
        # Should be in descending order by start time
        assert runs[0].zone_signature == "Map_4"


class TestItemDeltasRepository:
    """Tests for item deltas CRUD."""

    def test_insert_and_get_deltas(self, repo):
        run = Run(
            id=None,
            zone_signature="Map_Test",
            start_ts=datetime(2026, 1, 26, 10, 0, 0),
            end_ts=None,
            is_hub=False,
        )
        run_id = repo.insert_run(run)

        delta = ItemDelta(
            page_id=102,
            slot_id=0,
            config_base_id=100300,
            delta=50,
            context=EventContext.PICK_ITEMS,
            proto_name="PickItems",
            run_id=run_id,
            timestamp=datetime(2026, 1, 26, 10, 1, 0),
        )
        repo.insert_delta(delta)

        deltas = repo.get_deltas_for_run(run_id)
        assert len(deltas) == 1
        assert deltas[0].delta == 50
        assert deltas[0].context == EventContext.PICK_ITEMS

    def test_get_run_summary(self, repo):
        run = Run(
            id=None,
            zone_signature="Map_Test",
            start_ts=datetime(2026, 1, 26, 10, 0, 0),
            end_ts=None,
            is_hub=False,
        )
        run_id = repo.insert_run(run)

        # Multiple deltas for same item
        for delta_val in [50, 25, 100]:
            delta = ItemDelta(
                page_id=102,
                slot_id=0,
                config_base_id=100300,
                delta=delta_val,
                context=EventContext.PICK_ITEMS,
                proto_name="PickItems",
                run_id=run_id,
                timestamp=datetime.now(),
            )
            repo.insert_delta(delta)

        summary = repo.get_run_summary(run_id)
        assert summary[100300] == 175  # 50 + 25 + 100


class TestSlotStateRepository:
    """Tests for slot state CRUD."""

    def test_upsert_and_get_state(self, repo):
        state = SlotState(
            page_id=102,
            slot_id=0,
            config_base_id=100300,
            num=500,
            updated_at=datetime.now(),
        )
        repo.upsert_slot_state(state)

        fetched = repo.get_slot_state(102, 0)
        assert fetched is not None
        assert fetched.num == 500

    def test_update_existing_state(self, repo):
        state1 = SlotState(
            page_id=102,
            slot_id=0,
            config_base_id=100300,
            num=500,
            updated_at=datetime.now(),
        )
        repo.upsert_slot_state(state1)

        state2 = SlotState(
            page_id=102,
            slot_id=0,
            config_base_id=100300,
            num=600,
            updated_at=datetime.now(),
        )
        repo.upsert_slot_state(state2)

        fetched = repo.get_slot_state(102, 0)
        assert fetched.num == 600

    def test_get_all_slot_states(self, repo):
        for i in range(3):
            state = SlotState(
                page_id=102,
                slot_id=i,
                config_base_id=100300 + i,
                num=100 * i,
                updated_at=datetime.now(),
            )
            repo.upsert_slot_state(state)

        states = repo.get_all_slot_states()
        assert len(states) == 3


class TestItemsRepository:
    """Tests for items CRUD."""

    def test_upsert_and_get_item(self, repo):
        item = Item(
            config_base_id=100300,
            name_en="Flame Elementium",
            name_cn="火元素",
            type_cn="货币",
            icon_url="https://example.com/icon.png",
            url_en=None,
            url_cn=None,
        )
        repo.upsert_item(item)

        fetched = repo.get_item(100300)
        assert fetched is not None
        assert fetched.name_en == "Flame Elementium"

    def test_get_item_name_found(self, repo):
        item = Item(
            config_base_id=100300,
            name_en="Flame Elementium",
            name_cn=None,
            type_cn=None,
            icon_url=None,
            url_en=None,
            url_cn=None,
        )
        repo.upsert_item(item)

        name = repo.get_item_name(100300)
        assert name == "Flame Elementium"

    def test_get_item_name_not_found(self, repo):
        name = repo.get_item_name(999999)
        assert name == "Unknown 999999"

    def test_upsert_items_batch(self, repo):
        items = [
            Item(
                config_base_id=i,
                name_en=f"Item_{i}",
                name_cn=None,
                type_cn=None,
                icon_url=None,
                url_en=None,
                url_cn=None,
            )
            for i in range(100, 105)
        ]
        repo.upsert_items_batch(items)

        assert repo.get_item_count() == 5


class TestPricesRepository:
    """Tests for prices CRUD."""

    def test_upsert_and_get_price(self, repo):
        price = Price(
            config_base_id=100300,
            price_fe=1.0,
            source="manual",
            updated_at=datetime.now(),
        )
        repo.upsert_price(price)

        fetched = repo.get_price(100300)
        assert fetched is not None
        assert fetched.price_fe == 1.0


class TestLogPositionRepository:
    """Tests for log position CRUD."""

    def test_save_and_get_position(self, repo):
        file_path = Path("C:/test/log.txt")
        repo.save_log_position(file_path, 12345, 50000)

        result = repo.get_log_position()
        assert result is not None
        path, pos, size = result
        assert path == file_path
        assert pos == 12345
        assert size == 50000

    def test_get_position_when_empty(self, repo):
        result = repo.get_log_position()
        assert result is None


class TestHiddenItemsRepository:
    """Tests for hidden items CRUD."""

    def test_get_hidden_items_empty(self, repo):
        hidden = repo.get_hidden_items()
        assert hidden == set()

    def test_set_and_get_hidden_items(self, repo):
        repo.set_hidden_items({100300, 200001})
        hidden = repo.get_hidden_items()
        assert hidden == {100300, 200001}

    def test_set_hidden_items_replaces(self, repo):
        repo.set_hidden_items({100300, 200001})
        repo.set_hidden_items({300001})
        hidden = repo.get_hidden_items()
        assert hidden == {300001}

    def test_set_empty_clears(self, repo):
        repo.set_hidden_items({100300})
        repo.set_hidden_items(set())
        hidden = repo.get_hidden_items()
        assert hidden == set()

    def test_clear_hidden_items(self, repo):
        repo.set_hidden_items({100300, 200001})
        repo.clear_hidden_items()
        hidden = repo.get_hidden_items()
        assert hidden == set()

    def test_hidden_items_per_player(self, db):
        repo1 = Repository(db)
        repo1.set_player_context(season_id=1, player_id="player_a")
        repo1.set_hidden_items({100300})

        repo2 = Repository(db)
        repo2.set_player_context(season_id=1, player_id="player_b")
        repo2.set_hidden_items({200001})

        assert repo1.get_hidden_items() == {100300}
        assert repo2.get_hidden_items() == {200001}


class TestGearAllowlistRepository:
    """Tests for gear allowlist filtering in repository queries."""

    def test_slot_states_exclude_gear_by_default(self, repo):
        """Gear-page slot states are excluded when allowlist is empty."""
        # Insert gear and non-gear slot states
        repo.upsert_slot_state(SlotState(
            page_id=100, slot_id=0, config_base_id=999001, num=1, updated_at=datetime.now(),
        ))
        repo.upsert_slot_state(SlotState(
            page_id=102, slot_id=0, config_base_id=100300, num=500, updated_at=datetime.now(),
        ))

        states = repo.get_all_slot_states()
        assert len(states) == 1
        assert states[0].page_id == 102

    def test_slot_states_include_allowlisted_gear(self, repo):
        """Allowlisted gear items pass through in slot state queries."""
        set_gear_allowlist(frozenset([999001]))

        repo.upsert_slot_state(SlotState(
            page_id=100, slot_id=0, config_base_id=999001, num=1, updated_at=datetime.now(),
        ))
        repo.upsert_slot_state(SlotState(
            page_id=100, slot_id=1, config_base_id=999002, num=1, updated_at=datetime.now(),
        ))
        repo.upsert_slot_state(SlotState(
            page_id=102, slot_id=0, config_base_id=100300, num=500, updated_at=datetime.now(),
        ))

        states = repo.get_all_slot_states()
        # Should include 999001 (allowlisted) and 100300 (non-gear), but NOT 999002
        assert len(states) == 2
        config_ids = {s.config_base_id for s in states}
        assert 999001 in config_ids
        assert 100300 in config_ids
        assert 999002 not in config_ids

    def test_run_summary_includes_allowlisted_gear(self, repo):
        """Allowlisted gear items appear in run summaries."""
        set_gear_allowlist(frozenset([999001]))

        run = Run(
            id=None, zone_signature="Map_Test",
            start_ts=datetime(2026, 1, 26, 10, 0, 0), end_ts=None, is_hub=False,
        )
        run_id = repo.insert_run(run)

        # Allowlisted gear delta
        repo.insert_delta(ItemDelta(
            page_id=100, slot_id=0, config_base_id=999001, delta=1,
            context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run_id, timestamp=datetime.now(),
        ))
        # Non-allowlisted gear delta
        repo.insert_delta(ItemDelta(
            page_id=100, slot_id=1, config_base_id=999002, delta=1,
            context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run_id, timestamp=datetime.now(),
        ))
        # Normal commodity delta
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=100300, delta=50,
            context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run_id, timestamp=datetime.now(),
        ))

        summary = repo.get_run_summary(run_id)
        assert 999001 in summary  # allowlisted gear
        assert 999002 not in summary  # non-allowlisted gear
        assert 100300 in summary  # commodity

    def test_deltas_for_run_includes_allowlisted_gear(self, repo):
        """Allowlisted gear items appear in run delta queries."""
        set_gear_allowlist(frozenset([999001]))

        run = Run(
            id=None, zone_signature="Map_Test",
            start_ts=datetime(2026, 1, 26, 10, 0, 0), end_ts=None, is_hub=False,
        )
        run_id = repo.insert_run(run)

        repo.insert_delta(ItemDelta(
            page_id=100, slot_id=0, config_base_id=999001, delta=1,
            context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run_id, timestamp=datetime.now(),
        ))
        repo.insert_delta(ItemDelta(
            page_id=100, slot_id=1, config_base_id=999002, delta=1,
            context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run_id, timestamp=datetime.now(),
        ))

        deltas = repo.get_deltas_for_run(run_id)
        config_ids = {d.config_base_id for d in deltas}
        assert 999001 in config_ids
        assert 999002 not in config_ids

    def test_cumulative_loot_includes_allowlisted_gear(self, repo):
        """Allowlisted gear items appear in cumulative loot report."""
        set_gear_allowlist(frozenset([999001]))

        run = Run(
            id=None, zone_signature="Map_Test",
            start_ts=datetime(2026, 1, 26, 10, 0, 0),
            end_ts=datetime(2026, 1, 26, 10, 5, 0), is_hub=False,
        )
        run_id = repo.insert_run(run)

        repo.insert_delta(ItemDelta(
            page_id=100, slot_id=0, config_base_id=999001, delta=3,
            context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run_id, timestamp=datetime.now(),
        ))
        repo.insert_delta(ItemDelta(
            page_id=100, slot_id=1, config_base_id=999002, delta=2,
            context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run_id, timestamp=datetime.now(),
        ))

        loot = repo.get_cumulative_loot()
        loot_map = {item["config_base_id"]: item["total_quantity"] for item in loot}
        assert 999001 in loot_map
        assert loot_map[999001] == 3
        assert 999002 not in loot_map
