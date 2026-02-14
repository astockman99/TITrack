"""Tests for API routes."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from titrack.api.app import create_app
from titrack.core.models import EventContext, Item, ItemDelta, Price, Run, SlotState
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


@pytest.fixture
def db(tmp_path):
    """Create a temporary database."""
    db_path = tmp_path / "test.db"
    db = Database(db_path, auto_seed=False)
    db.connect()
    yield db
    db.close()


@pytest.fixture
def repo(db):
    """Create a repository."""
    repo = Repository(db)
    # Set test player context so queries return results
    repo.set_player_context(TEST_PLAYER_INFO.season_id, "test_player_123")
    return repo


@pytest.fixture
def client(db):
    """Create a test client."""
    app = create_app(db, collector_running=False, player_info=TEST_PLAYER_INFO)
    return TestClient(app)


@pytest.fixture
def seeded_db(db, repo):
    """Database with some test data."""
    # Add items
    fe_item = Item(
        config_base_id=FE_CONFIG_BASE_ID,
        name_en="Flame Elementium",
        name_cn=None,
        type_cn=None,
        icon_url="https://example.com/fe.png",
        url_en=None,
        url_cn=None,
    )
    other_item = Item(
        config_base_id=200001,
        name_en="Test Item",
        name_cn=None,
        type_cn=None,
        icon_url="https://example.com/item.png",
        url_en=None,
        url_cn=None,
    )
    repo.upsert_item(fe_item)
    repo.upsert_item(other_item)

    # Add a run
    now = datetime.now()
    run = Run(
        id=None,
        zone_signature="TestZone",
        start_ts=now - timedelta(minutes=5),
        end_ts=now,
        is_hub=False,
    )
    run_id = repo.insert_run(run)

    # Add deltas for the run
    fe_delta = ItemDelta(
        page_id=102,
        slot_id=0,
        config_base_id=FE_CONFIG_BASE_ID,
        delta=100,
        context=EventContext.PICK_ITEMS,
        proto_name="PickItems",
        run_id=run_id,
        timestamp=now,
    )
    repo.insert_delta(fe_delta)

    # Add slot states
    fe_state = SlotState(
        page_id=102,
        slot_id=0,
        config_base_id=FE_CONFIG_BASE_ID,
        num=500,
        updated_at=now,
    )
    repo.upsert_slot_state(fe_state)

    # Add a price
    price = Price(
        config_base_id=200001,
        price_fe=10.5,
        source="manual",
        updated_at=now,
    )
    repo.upsert_price(price)

    return db


class TestStatusEndpoint:
    def test_get_status(self, client):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["collector_running"] is False


class TestRunsEndpoints:
    def test_list_runs_empty(self, client):
        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []
        assert data["total"] == 0

    def test_list_runs_with_data(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 1
        assert data["runs"][0]["zone_name"] == "TestZone"
        assert data["runs"][0]["fe_gained"] == 100

    def test_get_run_by_id(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.get("/api/runs/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["fe_gained"] == 100

    def test_get_run_not_found(self, client):
        response = client.get("/api/runs/999")
        assert response.status_code == 404

    def test_get_stats(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.get("/api/runs/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_runs"] == 1
        assert data["total_fe"] == 100


class TestInventoryEndpoint:
    def test_get_inventory_empty(self, client):
        response = client.get("/api/inventory")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total_fe"] == 0

    def test_get_inventory_with_data(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.get("/api/inventory")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total_fe"] == 500


class TestHiddenItemsEndpoints:
    def test_get_hidden_items_empty(self, client):
        response = client.get("/api/inventory/hidden")
        assert response.status_code == 200
        data = response.json()
        assert data["hidden_ids"] == []

    def test_set_and_get_hidden_items(self, client):
        response = client.put(
            "/api/inventory/hidden",
            json={"hidden_ids": [200001, 300001]},
        )
        assert response.status_code == 200
        data = response.json()
        assert set(data["hidden_ids"]) == {200001, 300001}

        response = client.get("/api/inventory/hidden")
        assert response.status_code == 200
        data = response.json()
        assert set(data["hidden_ids"]) == {200001, 300001}

    def test_hidden_items_filtered_from_inventory(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        # Add a second item to slot state so we have 2 visible items
        repo = Repository(seeded_db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, "test_player_123")
        repo.upsert_slot_state(SlotState(
            page_id=102, slot_id=1, config_base_id=200001,
            num=10, updated_at=datetime.now(),
        ))

        # Verify both items show up
        response = client.get("/api/inventory")
        data = response.json()
        ids = [i["config_base_id"] for i in data["items"]]
        assert FE_CONFIG_BASE_ID in ids
        assert 200001 in ids
        net_worth_before = data["net_worth_fe"]

        # Hide the second item
        client.put("/api/inventory/hidden", json={"hidden_ids": [200001]})

        # Verify it's filtered out
        response = client.get("/api/inventory")
        data = response.json()
        ids = [i["config_base_id"] for i in data["items"]]
        assert FE_CONFIG_BASE_ID in ids
        assert 200001 not in ids

        # Net worth should be unchanged (hidden items still count)
        assert data["net_worth_fe"] == net_worth_before

    def test_hidden_items_exclude_from_net_worth(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        # Add a second item to slot state with known price
        repo = Repository(seeded_db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, "test_player_123")
        repo.upsert_slot_state(SlotState(
            page_id=102, slot_id=1, config_base_id=200001,
            num=10, updated_at=datetime.now(),
        ))

        # Hide the item
        client.put("/api/inventory/hidden", json={"hidden_ids": [200001]})

        # Default: hidden items still count toward net worth
        response = client.get("/api/inventory")
        data = response.json()
        net_worth_default = data["net_worth_fe"]
        assert net_worth_default > 500  # FE + item value

        # Enable exclude from net worth
        client.put(
            "/api/settings/hidden_items_exclude_worth",
            json={"value": "true"},
        )

        # Net worth should decrease (hidden item no longer counted)
        response = client.get("/api/inventory")
        data = response.json()
        assert data["net_worth_fe"] < net_worth_default
        assert data["net_worth_fe"] == 500.0  # Only FE remains

        # Disable the setting again
        client.put(
            "/api/settings/hidden_items_exclude_worth",
            json={"value": "false"},
        )

        # Net worth should be restored
        response = client.get("/api/inventory")
        data = response.json()
        assert data["net_worth_fe"] == net_worth_default

    def test_include_hidden_param(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        # Add item to slot state and hide it
        repo = Repository(seeded_db)
        repo.set_player_context(TEST_PLAYER_INFO.season_id, "test_player_123")
        repo.upsert_slot_state(SlotState(
            page_id=102, slot_id=1, config_base_id=200001,
            num=10, updated_at=datetime.now(),
        ))
        client.put("/api/inventory/hidden", json={"hidden_ids": [200001]})

        # Without include_hidden: item is filtered
        response = client.get("/api/inventory")
        ids = [i["config_base_id"] for i in response.json()["items"]]
        assert 200001 not in ids

        # With include_hidden=true: item is included
        response = client.get("/api/inventory?include_hidden=true")
        ids = [i["config_base_id"] for i in response.json()["items"]]
        assert 200001 in ids


class TestItemsEndpoints:
    def test_list_items_empty(self, client):
        response = client.get("/api/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    def test_list_items_with_data(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.get("/api/items")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    def test_search_items(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.get("/api/items?search=Flame")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name_en"] == "Flame Elementium"

    def test_get_item_by_id(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.get(f"/api/items/{FE_CONFIG_BASE_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["name_en"] == "Flame Elementium"

    def test_get_item_not_found(self, client):
        response = client.get("/api/items/999999")
        assert response.status_code == 404


class TestStatsEndpoints:
    def test_get_stats_history_empty(self, client):
        response = client.get("/api/stats/history")
        assert response.status_code == 200
        data = response.json()
        assert data["cumulative_value"] == []
        assert data["value_per_hour"] == []
        assert data["cumulative_fe"] == []

    def test_get_stats_history_with_data(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.get("/api/stats/history?hours=24")
        assert response.status_code == 200
        data = response.json()
        # Should have one data point from the seeded run
        assert len(data["cumulative_value"]) == 1
        assert data["cumulative_value"][0]["value"] == 100  # FE from seeded run (no prices)


class TestPricesEndpoints:
    def test_list_prices_empty(self, client):
        response = client.get("/api/prices")
        assert response.status_code == 200
        data = response.json()
        assert data["prices"] == []

    def test_list_prices_with_data(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.get("/api/prices")
        assert response.status_code == 200
        data = response.json()
        assert len(data["prices"]) == 1
        assert data["prices"][0]["price_fe"] == 10.5

    def test_get_price_not_found(self, client):
        response = client.get("/api/prices/999999")
        assert response.status_code == 404

    def test_update_price(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.put(
            "/api/prices/200001",
            json={"price_fe": 20.0, "source": "manual"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["price_fe"] == 20.0

        # Verify it was persisted
        response = client.get("/api/prices/200001")
        assert response.json()["price_fe"] == 20.0

    def test_create_price(self, seeded_db):
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)

        response = client.put(
            f"/api/prices/{FE_CONFIG_BASE_ID}",
            json={"price_fe": 1.0, "source": "default"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["price_fe"] == 1.0
        assert data["name"] == "Flame Elementium"


class TestActiveRunAggregation:
    """Test that active run aggregates loot from prior runs with same level_uid."""

    def test_active_run_no_subzone(self, db, repo):
        """Active run with no prior splits returns normal data."""
        now = datetime.now()
        repo.upsert_item(Item(
            config_base_id=FE_CONFIG_BASE_ID, name_en="Flame Elementium",
            name_cn=None, type_cn=None, icon_url=None, url_en=None, url_cn=None,
        ))

        # Single active run
        run_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone", start_ts=now - timedelta(minutes=3),
            is_hub=False, level_uid=100, level_type=3,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=50, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run_id, timestamp=now,
        ))

        app = create_app(db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)
        response = client.get("/api/runs/active")
        assert response.status_code == 200
        data = response.json()
        assert data["fe_gained"] == 50
        assert len(data["loot"]) == 1

    def test_active_run_aggregates_after_arcana(self, db, repo):
        """After returning from Arcana sub-zone, active run includes prior loot."""
        now = datetime.now()
        repo.upsert_item(Item(
            config_base_id=FE_CONFIG_BASE_ID, name_en="Flame Elementium",
            name_cn=None, type_cn=None, icon_url=None, url_en=None, url_cn=None,
        ))

        # Run part 1: in map before Arcana (completed)
        run1_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone",
            start_ts=now - timedelta(minutes=10), end_ts=now - timedelta(minutes=6),
            is_hub=False, level_uid=100, level_type=3,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=200, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run1_id, timestamp=now - timedelta(minutes=8),
        ))

        # Arcana sub-zone run (completed, different level_uid, level_type=19)
        repo.insert_run(Run(
            id=None, zone_signature="SuMingTaLuo",
            start_ts=now - timedelta(minutes=6), end_ts=now - timedelta(minutes=4),
            is_hub=False, level_uid=200, level_type=19,
        ))

        # Run part 2: back in map after Arcana (active)
        run3_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone",
            start_ts=now - timedelta(minutes=4),
            is_hub=False, level_uid=100, level_type=3,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=150, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run3_id, timestamp=now - timedelta(minutes=2),
        ))

        app = create_app(db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)
        response = client.get("/api/runs/active")
        assert response.status_code == 200
        data = response.json()

        # Should aggregate: 200 + 150 = 350 FE
        assert data["fe_gained"] == 350
        # Duration = part1 (4 min) + active elapsed (~4 min), excludes Arcana time
        assert 400 < data["duration_seconds"] < 550

    def test_active_run_aggregates_after_nightmare(self, db, repo):
        """After returning from Nightmare, active run includes prior loot."""
        now = datetime.now()
        repo.upsert_item(Item(
            config_base_id=FE_CONFIG_BASE_ID, name_en="Flame Elementium",
            name_cn=None, type_cn=None, icon_url=None, url_en=None, url_cn=None,
        ))

        # Run part 1: in map before Nightmare (completed)
        run1_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone",
            start_ts=now - timedelta(minutes=8), end_ts=now - timedelta(minutes=5),
            is_hub=False, level_uid=100, level_type=3,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=100, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run1_id, timestamp=now - timedelta(minutes=7),
        ))

        # Nightmare run (completed, same level_uid, level_type=11)
        nm_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone",
            start_ts=now - timedelta(minutes=5), end_ts=now - timedelta(minutes=3),
            is_hub=False, level_uid=100, level_type=11,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=75, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=nm_id, timestamp=now - timedelta(minutes=4),
        ))

        # Run part 2: back in map after Nightmare (active)
        run3_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone",
            start_ts=now - timedelta(minutes=3),
            is_hub=False, level_uid=100, level_type=3,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=50, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run3_id, timestamp=now - timedelta(minutes=1),
        ))

        app = create_app(db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)
        response = client.get("/api/runs/active")
        assert response.status_code == 200
        data = response.json()

        # Should aggregate normal runs only: 100 + 50 = 150 (Nightmare run excluded)
        assert data["fe_gained"] == 150
        # Duration = part1 (3 min) + active elapsed (~3 min), excludes Nightmare time
        assert 300 < data["duration_seconds"] < 420

    def test_active_run_no_level_uid(self, db, repo):
        """Active run without level_uid doesn't aggregate."""
        now = datetime.now()
        repo.upsert_item(Item(
            config_base_id=FE_CONFIG_BASE_ID, name_en="Flame Elementium",
            name_cn=None, type_cn=None, icon_url=None, url_en=None, url_cn=None,
        ))

        run_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone", start_ts=now - timedelta(minutes=2),
            is_hub=False, level_uid=None, level_type=3,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=30, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run_id, timestamp=now,
        ))

        app = create_app(db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)
        response = client.get("/api/runs/active")
        assert response.status_code == 200
        data = response.json()
        assert data["fe_gained"] == 30

    def test_active_subzone_shows_standalone(self, db, repo):
        """When inside Nightmare/Arcana, show only that sub-zone's data."""
        now = datetime.now()
        repo.upsert_item(Item(
            config_base_id=FE_CONFIG_BASE_ID, name_en="Flame Elementium",
            name_cn=None, type_cn=None, icon_url=None, url_en=None, url_cn=None,
        ))

        # Prior normal run (completed, same level_uid)
        run1_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone",
            start_ts=now - timedelta(minutes=8), end_ts=now - timedelta(minutes=5),
            is_hub=False, level_uid=100, level_type=3,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=200, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run1_id, timestamp=now - timedelta(minutes=7),
        ))

        # Currently inside Nightmare (active, same level_uid)
        nm_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone",
            start_ts=now - timedelta(minutes=2),
            is_hub=False, level_uid=100, level_type=11,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=25, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=nm_id, timestamp=now - timedelta(minutes=1),
        ))

        app = create_app(db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)
        response = client.get("/api/runs/active")
        assert response.status_code == 200
        data = response.json()

        # Should show only Nightmare loot, NOT aggregated with prior normal run
        assert data["fe_gained"] == 25
        # Duration should be ~2 minutes (just the Nightmare), not ~8
        assert data["duration_seconds"] < 180

    def test_active_run_not_aggregated_after_hub(self, db, repo):
        """Running the same zone twice with a hub visit in between should NOT aggregate."""
        now = datetime.now()
        repo.upsert_item(Item(
            config_base_id=FE_CONFIG_BASE_ID, name_en="Flame Elementium",
            name_cn=None, type_cn=None, icon_url=None, url_en=None, url_cn=None,
        ))

        # First run of zone (completed, level_uid=100)
        run1_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone",
            start_ts=now - timedelta(minutes=10), end_ts=now - timedelta(minutes=8),
            is_hub=False, level_uid=100, level_type=3,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=300, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run1_id, timestamp=now - timedelta(minutes=9),
        ))

        # Hub visit (completed)
        repo.insert_run(Run(
            id=None, zone_signature="Hideout",
            start_ts=now - timedelta(minutes=8), end_ts=now - timedelta(minutes=5),
            is_hub=True,
        ))

        # Second run of same zone (active, same level_uid=100)
        run2_id = repo.insert_run(Run(
            id=None, zone_signature="TestZone",
            start_ts=now - timedelta(minutes=2),
            is_hub=False, level_uid=100, level_type=3,
        ))
        repo.insert_delta(ItemDelta(
            page_id=102, slot_id=0, config_base_id=FE_CONFIG_BASE_ID,
            delta=40, context=EventContext.PICK_ITEMS, proto_name="PickItems",
            run_id=run2_id, timestamp=now - timedelta(minutes=1),
        ))

        app = create_app(db, player_info=TEST_PLAYER_INFO)
        client = TestClient(app)
        response = client.get("/api/runs/active")
        assert response.status_code == 200
        data = response.json()

        # Should show only the second run's loot (40 FE), not aggregated (340)
        assert data["fe_gained"] == 40
        # Duration should be ~2 minutes, not ~10
        assert data["duration_seconds"] < 180


class TestIconsEndpoint:
    def test_get_icon_no_item(self, client):
        """Test getting icon for non-existent item returns 404."""
        response = client.get("/api/icons/999999")
        assert response.status_code == 404

    def test_get_icon_no_url(self, seeded_db):
        """Test getting icon for item with no icon_url returns 404."""
        app = create_app(seeded_db, player_info=TEST_PLAYER_INFO)
        repo = Repository(seeded_db)

        # Add item without icon_url
        item = Item(
            config_base_id=999888,
            name_en="Test Item No Icon",
            name_cn=None,
            type_cn=None,
            icon_url=None,
            url_en=None,
            url_cn=None,
        )
        repo.upsert_item(item)

        client = TestClient(app)
        response = client.get("/api/icons/999888")
        assert response.status_code == 404
        assert "No icon available" in response.json()["detail"]
