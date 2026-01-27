"""Repository - CRUD operations for all entities."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from titrack.core.models import (
    EventContext,
    Item,
    ItemDelta,
    Price,
    Run,
    SlotState,
)
from titrack.db.connection import Database


class Repository:
    """Data access layer for all entities."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # --- Settings ---

    def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value by key."""
        row = self.db.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        self.db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat()),
        )

    # --- Runs ---

    def insert_run(self, run: Run) -> int:
        """Insert a new run and return its ID."""
        cursor = self.db.execute(
            "INSERT INTO runs (zone_signature, start_ts, end_ts, is_hub, level_id) VALUES (?, ?, ?, ?, ?)",
            (
                run.zone_signature,
                run.start_ts.isoformat(),
                run.end_ts.isoformat() if run.end_ts else None,
                1 if run.is_hub else 0,
                run.level_id,
            ),
        )
        return cursor.lastrowid

    def update_run_end(self, run_id: int, end_ts: datetime) -> None:
        """Update a run's end timestamp."""
        self.db.execute(
            "UPDATE runs SET end_ts = ? WHERE id = ?",
            (end_ts.isoformat(), run_id),
        )

    def get_run(self, run_id: int) -> Optional[Run]:
        """Get a run by ID."""
        row = self.db.fetchone("SELECT * FROM runs WHERE id = ?", (run_id,))
        if not row:
            return None
        return self._row_to_run(row)

    def get_active_run(self) -> Optional[Run]:
        """Get the currently active (non-ended) run."""
        row = self.db.fetchone(
            "SELECT * FROM runs WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1"
        )
        if not row:
            return None
        return self._row_to_run(row)

    def get_recent_runs(self, limit: int = 20) -> list[Run]:
        """Get recent runs ordered by start time descending."""
        rows = self.db.fetchall(
            "SELECT * FROM runs ORDER BY start_ts DESC LIMIT ?", (limit,)
        )
        return [self._row_to_run(row) for row in rows]

    def get_max_run_id(self) -> int:
        """Get the maximum run ID."""
        row = self.db.fetchone("SELECT MAX(id) as max_id FROM runs")
        return row["max_id"] or 0

    def get_unique_zones(self) -> list[str]:
        """Get all unique zone signatures from runs."""
        rows = self.db.fetchall(
            "SELECT DISTINCT zone_signature FROM runs ORDER BY zone_signature"
        )
        return [row["zone_signature"] for row in rows]

    def _row_to_run(self, row) -> Run:
        # Handle level_id which may not exist in older databases
        level_id = row["level_id"] if "level_id" in row.keys() else None
        return Run(
            id=row["id"],
            zone_signature=row["zone_signature"],
            start_ts=datetime.fromisoformat(row["start_ts"]),
            end_ts=datetime.fromisoformat(row["end_ts"]) if row["end_ts"] else None,
            is_hub=bool(row["is_hub"]),
            level_id=level_id,
        )

    # --- Item Deltas ---

    def insert_delta(self, delta: ItemDelta) -> int:
        """Insert an item delta and return its ID."""
        cursor = self.db.execute(
            """INSERT INTO item_deltas
               (page_id, slot_id, config_base_id, delta, context, proto_name, run_id, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                delta.page_id,
                delta.slot_id,
                delta.config_base_id,
                delta.delta,
                delta.context.name,
                delta.proto_name,
                delta.run_id,
                delta.timestamp.isoformat(),
            ),
        )
        return cursor.lastrowid

    def get_deltas_for_run(self, run_id: int) -> list[ItemDelta]:
        """Get all deltas for a run."""
        rows = self.db.fetchall(
            "SELECT * FROM item_deltas WHERE run_id = ? ORDER BY timestamp",
            (run_id,),
        )
        return [self._row_to_delta(row) for row in rows]

    def get_run_summary(self, run_id: int) -> dict[int, int]:
        """
        Get aggregated delta per item for a run.

        Returns:
            Dict mapping config_base_id -> total delta
        """
        rows = self.db.fetchall(
            """SELECT config_base_id, SUM(delta) as total_delta
               FROM item_deltas WHERE run_id = ?
               GROUP BY config_base_id""",
            (run_id,),
        )
        return {row["config_base_id"]: row["total_delta"] for row in rows}

    def _row_to_delta(self, row) -> ItemDelta:
        return ItemDelta(
            page_id=row["page_id"],
            slot_id=row["slot_id"],
            config_base_id=row["config_base_id"],
            delta=row["delta"],
            context=EventContext[row["context"]],
            proto_name=row["proto_name"],
            run_id=row["run_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    # --- Slot State ---

    def upsert_slot_state(self, state: SlotState) -> None:
        """Insert or update slot state."""
        self.db.execute(
            """INSERT OR REPLACE INTO slot_state
               (page_id, slot_id, config_base_id, num, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                state.page_id,
                state.slot_id,
                state.config_base_id,
                state.num,
                state.updated_at.isoformat(),
            ),
        )

    def get_all_slot_states(self) -> list[SlotState]:
        """Get all slot states."""
        rows = self.db.fetchall("SELECT * FROM slot_state")
        return [self._row_to_slot_state(row) for row in rows]

    def get_slot_state(self, page_id: int, slot_id: int) -> Optional[SlotState]:
        """Get state for a specific slot."""
        row = self.db.fetchone(
            "SELECT * FROM slot_state WHERE page_id = ? AND slot_id = ?",
            (page_id, slot_id),
        )
        if not row:
            return None
        return self._row_to_slot_state(row)

    def _row_to_slot_state(self, row) -> SlotState:
        return SlotState(
            page_id=row["page_id"],
            slot_id=row["slot_id"],
            config_base_id=row["config_base_id"],
            num=row["num"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # --- Items ---

    def upsert_item(self, item: Item) -> None:
        """Insert or update item metadata."""
        self.db.execute(
            """INSERT OR REPLACE INTO items
               (config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                item.config_base_id,
                item.name_en,
                item.name_cn,
                item.type_cn,
                item.icon_url,
                item.url_en,
                item.url_cn,
            ),
        )

    def upsert_items_batch(self, items: list[Item]) -> None:
        """Insert or update multiple items."""
        self.db.executemany(
            """INSERT OR REPLACE INTO items
               (config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    item.config_base_id,
                    item.name_en,
                    item.name_cn,
                    item.type_cn,
                    item.icon_url,
                    item.url_en,
                    item.url_cn,
                )
                for item in items
            ],
        )

    def get_item(self, config_base_id: int) -> Optional[Item]:
        """Get item by ConfigBaseId."""
        row = self.db.fetchone(
            "SELECT * FROM items WHERE config_base_id = ?", (config_base_id,)
        )
        if not row:
            return None
        return self._row_to_item(row)

    def get_item_name(self, config_base_id: int) -> str:
        """Get item name, falling back to Unknown <id> if not found."""
        item = self.get_item(config_base_id)
        if item and item.name_en:
            return item.name_en
        return f"Unknown {config_base_id}"

    def get_all_items(self) -> list[Item]:
        """Get all items."""
        rows = self.db.fetchall("SELECT * FROM items")
        return [self._row_to_item(row) for row in rows]

    def get_item_count(self) -> int:
        """Get total number of items in database."""
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM items")
        return row["cnt"] if row else 0

    def update_item_name(self, config_base_id: int, name_en: str) -> None:
        """Update an item's English name."""
        self.db.execute(
            "UPDATE items SET name_en = ? WHERE config_base_id = ?",
            (name_en, config_base_id),
        )

    def _row_to_item(self, row) -> Item:
        return Item(
            config_base_id=row["config_base_id"],
            name_en=row["name_en"],
            name_cn=row["name_cn"],
            type_cn=row["type_cn"],
            icon_url=row["icon_url"],
            url_en=row["url_en"],
            url_cn=row["url_cn"],
        )

    # --- Prices ---

    def upsert_price(self, price: Price) -> None:
        """Insert or update a price entry."""
        self.db.execute(
            """INSERT OR REPLACE INTO prices
               (config_base_id, price_fe, source, updated_at)
               VALUES (?, ?, ?, ?)""",
            (
                price.config_base_id,
                price.price_fe,
                price.source,
                price.updated_at.isoformat(),
            ),
        )

    def get_price(self, config_base_id: int) -> Optional[Price]:
        """Get price for an item."""
        row = self.db.fetchone(
            "SELECT * FROM prices WHERE config_base_id = ?", (config_base_id,)
        )
        if not row:
            return None
        return self._row_to_price(row)

    def get_all_prices(self) -> list[Price]:
        """Get all prices."""
        rows = self.db.fetchall("SELECT * FROM prices")
        return [self._row_to_price(row) for row in rows]

    def get_price_count(self) -> int:
        """Get total number of prices in database."""
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM prices")
        return row["cnt"] if row else 0

    def upsert_prices_batch(self, prices: list[Price]) -> None:
        """Insert or update multiple prices."""
        self.db.executemany(
            """INSERT OR REPLACE INTO prices
               (config_base_id, price_fe, source, updated_at)
               VALUES (?, ?, ?, ?)""",
            [
                (
                    price.config_base_id,
                    price.price_fe,
                    price.source,
                    price.updated_at.isoformat(),
                )
                for price in prices
            ],
        )

    def _row_to_price(self, row) -> Price:
        return Price(
            config_base_id=row["config_base_id"],
            price_fe=row["price_fe"],
            source=row["source"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_run_value(self, run_id: int) -> tuple[int, float]:
        """
        Calculate total value of a run's loot.

        Returns:
            Tuple of (raw_fe_gained, total_value_fe)
            - raw_fe_gained: Just the FE currency picked up
            - total_value_fe: FE + value of other items based on prices
        """
        from titrack.parser.patterns import FE_CONFIG_BASE_ID

        summary = self.get_run_summary(run_id)
        raw_fe = summary.get(FE_CONFIG_BASE_ID, 0)
        total_value = float(raw_fe)

        for config_id, quantity in summary.items():
            if config_id == FE_CONFIG_BASE_ID:
                continue
            if quantity <= 0:
                continue
            price = self.get_price(config_id)
            if price and price.price_fe > 0:
                total_value += price.price_fe * quantity

        return raw_fe, total_value

    # --- Data Management ---

    def clear_run_data(self) -> int:
        """
        Clear all run tracking data (runs and item_deltas).

        Preserves: items, prices, settings, slot_state, log_position.

        Returns:
            Number of runs deleted.
        """
        # Get count before deletion
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM runs")
        run_count = row["cnt"] if row else 0

        # Get raw connection for direct control
        conn = self.db.connection

        # Use explicit transaction for deletion
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Delete item_deltas first (foreign key reference)
            conn.execute("DELETE FROM item_deltas")
            # Delete runs
            conn.execute("DELETE FROM runs")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        # Force WAL checkpoint to ensure changes are written to main database
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        return run_count

    # --- Log Position ---

    def save_log_position(self, file_path: Path, position: int, file_size: int) -> None:
        """Save current log file position for resume."""
        # Guard against oversized integers (SQLite max is 2^63-1)
        MAX_SQLITE_INT = 9223372036854775807
        if position > MAX_SQLITE_INT or file_size > MAX_SQLITE_INT:
            print(f"WARNING: Log position overflow - position={position}, file_size={file_size}")
            # Clamp to max value to avoid crash
            position = min(position, MAX_SQLITE_INT)
            file_size = min(file_size, MAX_SQLITE_INT)

        conn = self.db.connection
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """INSERT OR REPLACE INTO log_position
                   (id, file_path, position, file_size, updated_at)
                   VALUES (1, ?, ?, ?, ?)""",
                (str(file_path), position, file_size, datetime.now().isoformat()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        # Force checkpoint
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def get_log_position(self) -> Optional[tuple[Path, int, int]]:
        """
        Get saved log position.

        Returns:
            Tuple of (file_path, position, file_size) or None
        """
        row = self.db.fetchone("SELECT * FROM log_position WHERE id = 1")
        if not row:
            return None
        return (Path(row["file_path"]), row["position"], row["file_size"])
