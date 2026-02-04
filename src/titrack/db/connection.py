"""SQLite connection management with WAL mode."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from titrack.db.schema import ALL_CREATE_STATEMENTS, SCHEMA_VERSION


class Database:
    """SQLite database connection manager with thread safety."""

    def __init__(self, db_path: Path, auto_seed: bool = True) -> None:
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
            auto_seed: If True, auto-seed items on first run. Set to False for tests.
        """
        self.db_path = db_path
        self._auto_seed = auto_seed
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        """Open database connection and initialize schema."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode for WAL
        )
        self._connection.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrent access
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        # Wait up to 30 seconds for locks instead of failing immediately
        # Higher timeout needed when running with pywebview (3 thread contexts)
        self._connection.execute("PRAGMA busy_timeout=30000")

        # Initialize schema
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        cursor = self._connection.cursor()
        for statement in ALL_CREATE_STATEMENTS:
            cursor.execute(statement)

        # Run migrations for existing databases
        self._run_migrations(cursor)

        # Store schema version
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )

        # Auto-seed items if table is empty (first run experience)
        if self._auto_seed:
            self._auto_seed_items(cursor)

    def _run_migrations(self, cursor: sqlite3.Cursor) -> None:
        """Run database migrations for schema changes."""
        # Check existing columns in runs table
        cursor.execute("PRAGMA table_info(runs)")
        runs_columns = [row[1] for row in cursor.fetchall()]

        if "level_id" not in runs_columns:
            cursor.execute("ALTER TABLE runs ADD COLUMN level_id INTEGER")
            print("Migration: Added level_id column to runs table")

        if "level_type" not in runs_columns:
            cursor.execute("ALTER TABLE runs ADD COLUMN level_type INTEGER")
            print("Migration: Added level_type column to runs table")

        if "level_uid" not in runs_columns:
            cursor.execute("ALTER TABLE runs ADD COLUMN level_uid INTEGER")
            print("Migration: Added level_uid column to runs table")

        # V2 migrations: season_id and player_id support
        if "season_id" not in runs_columns:
            cursor.execute("ALTER TABLE runs ADD COLUMN season_id INTEGER")
            print("Migration: Added season_id column to runs table")

        if "player_id" not in runs_columns:
            cursor.execute("ALTER TABLE runs ADD COLUMN player_id TEXT")
            print("Migration: Added player_id column to runs table")

        # Check item_deltas columns
        cursor.execute("PRAGMA table_info(item_deltas)")
        deltas_columns = [row[1] for row in cursor.fetchall()]

        if "season_id" not in deltas_columns:
            cursor.execute("ALTER TABLE item_deltas ADD COLUMN season_id INTEGER")
            print("Migration: Added season_id column to item_deltas table")

        if "player_id" not in deltas_columns:
            cursor.execute("ALTER TABLE item_deltas ADD COLUMN player_id TEXT")
            print("Migration: Added player_id column to item_deltas table")

        # Migrate prices table (PK change from config_base_id to config_base_id+season_id)
        cursor.execute("PRAGMA table_info(prices)")
        prices_columns = [row[1] for row in cursor.fetchall()]

        if "season_id" not in prices_columns:
            # Need to recreate table with new PK
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prices_new (
                    config_base_id INTEGER NOT NULL,
                    season_id INTEGER NOT NULL DEFAULT 0,
                    price_fe REAL NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'manual',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (config_base_id, season_id)
                )
            """)
            # Migrate existing data (season_id=0 means legacy/unknown)
            cursor.execute("""
                INSERT OR IGNORE INTO prices_new (config_base_id, season_id, price_fe, source, updated_at)
                SELECT config_base_id, 0, price_fe, source, updated_at FROM prices
            """)
            cursor.execute("DROP TABLE prices")
            cursor.execute("ALTER TABLE prices_new RENAME TO prices")
            print("Migration: Recreated prices table with season_id")

        # Migrate slot_state table (PK change to include player_id)
        cursor.execute("PRAGMA table_info(slot_state)")
        slot_columns = [row[1] for row in cursor.fetchall()]

        if "player_id" not in slot_columns:
            # Need to recreate table with new PK
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS slot_state_new (
                    player_id TEXT NOT NULL DEFAULT '',
                    page_id INTEGER NOT NULL,
                    slot_id INTEGER NOT NULL,
                    config_base_id INTEGER NOT NULL,
                    num INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (player_id, page_id, slot_id)
                )
            """)
            # Migrate existing data (player_id='' means legacy/unknown)
            cursor.execute("""
                INSERT OR IGNORE INTO slot_state_new (player_id, page_id, slot_id, config_base_id, num, updated_at)
                SELECT '', page_id, slot_id, config_base_id, num, updated_at FROM slot_state
            """)
            cursor.execute("DROP TABLE slot_state")
            cursor.execute("ALTER TABLE slot_state_new RENAME TO slot_state")
            print("Migration: Recreated slot_state table with player_id")

    def _auto_seed_items(self, cursor: sqlite3.Cursor) -> None:
        """
        Auto-seed items table on first run if empty.

        Loads items from bundled tlidb_items_seed_en.json for
        immediate item name display without manual seeding.
        """
        # Check if items table has any data
        result = cursor.execute("SELECT COUNT(*) FROM items").fetchone()
        if result[0] > 0:
            return  # Already seeded

        # Try to find and load the seed file
        try:
            from titrack.config.paths import get_items_seed_path

            seed_path = get_items_seed_path()
            if not seed_path.exists():
                print(f"Items seed file not found: {seed_path}")
                return

            with open(seed_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            items_data = data.get("items", [])
            if not items_data:
                print("No items found in seed file")
                return

            # Batch insert items
            insert_sql = """
                INSERT OR IGNORE INTO items
                (config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """

            items_to_insert = []
            for item in items_data:
                items_to_insert.append((
                    int(item["id"]),
                    item.get("name_en"),
                    item.get("name_cn"),
                    item.get("type_cn"),
                    item.get("img"),
                    item.get("url_en"),
                    item.get("url_cn"),
                ))

            cursor.executemany(insert_sql, items_to_insert)
            print(f"Seeded {len(items_to_insert)} items from {seed_path.name}")

        except Exception as e:
            print(f"Failed to auto-seed items: {e}")

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the database connection."""
        if self._connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager for database transactions.

        Usage:
            with db.transaction() as cursor:
                cursor.execute(...)

        Automatically commits on success, rolls back on exception.
        Thread-safe: holds the lock for the entire transaction duration.
        """
        with self._lock:
            cursor = self.connection.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                yield cursor
                cursor.execute("COMMIT")
            except Exception:
                cursor.execute("ROLLBACK")
                raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a single SQL statement."""
        with self._lock:
            return self.connection.execute(sql, params)

    def executemany(self, sql: str, params_seq: list[tuple]) -> sqlite3.Cursor:
        """Execute a SQL statement for each parameter set."""
        with self._lock:
            return self.connection.executemany(sql, params_seq)

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        """Execute SQL and fetch one row."""
        with self._lock:
            cursor = self.connection.execute(sql, params)
            return cursor.fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute SQL and fetch all rows."""
        with self._lock:
            cursor = self.connection.execute(sql, params)
            return cursor.fetchall()
