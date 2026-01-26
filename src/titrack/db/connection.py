"""SQLite connection management with WAL mode."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from titrack.db.schema import ALL_CREATE_STATEMENTS, SCHEMA_VERSION


class Database:
    """SQLite database connection manager with thread safety."""

    def __init__(self, db_path: Path) -> None:
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
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

        # Initialize schema
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        cursor = self._connection.cursor()
        for statement in ALL_CREATE_STATEMENTS:
            cursor.execute(statement)

        # Store schema version
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )

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
        """
        cursor = self.connection.cursor()
        cursor.execute("BEGIN")
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
