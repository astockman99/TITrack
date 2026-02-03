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
