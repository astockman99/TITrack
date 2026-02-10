"""Database schema - DDL statements for SQLite."""

SCHEMA_VERSION = 4  # Bumped for hidden items support

# Settings table - key/value configuration
CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

# Runs table - map instances
CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_signature TEXT NOT NULL,
    start_ts TEXT NOT NULL,
    end_ts TEXT,
    is_hub INTEGER NOT NULL DEFAULT 0,
    level_id INTEGER,
    level_type INTEGER,
    level_uid INTEGER,
    season_id INTEGER,
    player_id TEXT
)
"""

CREATE_RUNS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_runs_start_ts ON runs(start_ts)
"""

# Item deltas - per-item changes
CREATE_ITEM_DELTAS = """
CREATE TABLE IF NOT EXISTS item_deltas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL,
    slot_id INTEGER NOT NULL,
    config_base_id INTEGER NOT NULL,
    delta INTEGER NOT NULL,
    context TEXT NOT NULL,
    proto_name TEXT,
    run_id INTEGER,
    timestamp TEXT NOT NULL,
    season_id INTEGER,
    player_id TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(id)
)
"""

CREATE_ITEM_DELTAS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_item_deltas_run_id ON item_deltas(run_id)
"""

CREATE_ITEM_DELTAS_CONFIG_INDEX = """
CREATE INDEX IF NOT EXISTS idx_item_deltas_config ON item_deltas(config_base_id)
"""

# Slot state - current inventory state (PK includes player_id for per-character isolation)
CREATE_SLOT_STATE = """
CREATE TABLE IF NOT EXISTS slot_state (
    player_id TEXT NOT NULL DEFAULT '',
    page_id INTEGER NOT NULL,
    slot_id INTEGER NOT NULL,
    config_base_id INTEGER NOT NULL,
    num INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (player_id, page_id, slot_id)
)
"""

# Items table - item metadata
CREATE_ITEMS = """
CREATE TABLE IF NOT EXISTS items (
    config_base_id INTEGER PRIMARY KEY,
    name_en TEXT,
    name_cn TEXT,
    type_cn TEXT,
    icon_url TEXT,
    url_en TEXT,
    url_cn TEXT
)
"""

# Prices table - item valuation (compound key: config_base_id + season_id)
CREATE_PRICES = """
CREATE TABLE IF NOT EXISTS prices (
    config_base_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL DEFAULT 0,
    price_fe REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (config_base_id, season_id)
)
"""

# Log position tracking - for resume on restart
CREATE_LOG_POSITION = """
CREATE TABLE IF NOT EXISTS log_position (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    file_path TEXT NOT NULL,
    position INTEGER NOT NULL,
    file_size INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

# Cloud sync queue - prices waiting to upload
CREATE_CLOUD_SYNC_QUEUE = """
CREATE TABLE IF NOT EXISTS cloud_sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_base_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    price_fe REAL NOT NULL,
    prices_array TEXT NOT NULL,
    queued_at TEXT NOT NULL DEFAULT (datetime('now')),
    attempts INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending'
)
"""

# Cloud price cache - downloaded aggregated prices
CREATE_CLOUD_PRICE_CACHE = """
CREATE TABLE IF NOT EXISTS cloud_price_cache (
    config_base_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    price_fe_median REAL NOT NULL,
    price_fe_p10 REAL,
    price_fe_p90 REAL,
    submission_count INTEGER,
    unique_devices INTEGER,
    cloud_updated_at TEXT,
    cached_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (config_base_id, season_id)
)
"""

# Cloud price history - for sparklines (72h cached locally)
CREATE_CLOUD_PRICE_HISTORY = """
CREATE TABLE IF NOT EXISTS cloud_price_history (
    config_base_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    hour_bucket TEXT NOT NULL,
    price_fe_median REAL NOT NULL,
    price_fe_p10 REAL,
    price_fe_p90 REAL,
    submission_count INTEGER,
    cached_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (config_base_id, season_id, hour_bucket)
)
"""

# Hidden items - items hidden from inventory display (per-player)
CREATE_HIDDEN_ITEMS = """
CREATE TABLE IF NOT EXISTS hidden_items (
    player_id TEXT NOT NULL DEFAULT '',
    config_base_id INTEGER NOT NULL,
    PRIMARY KEY (player_id, config_base_id)
)
"""

ALL_CREATE_STATEMENTS = [
    CREATE_SETTINGS,
    CREATE_RUNS,
    CREATE_RUNS_INDEX,
    CREATE_ITEM_DELTAS,
    CREATE_ITEM_DELTAS_INDEX,
    CREATE_ITEM_DELTAS_CONFIG_INDEX,
    CREATE_SLOT_STATE,
    CREATE_ITEMS,
    CREATE_PRICES,
    CREATE_LOG_POSITION,
    CREATE_CLOUD_SYNC_QUEUE,
    CREATE_CLOUD_PRICE_CACHE,
    CREATE_CLOUD_PRICE_HISTORY,
    CREATE_HIDDEN_ITEMS,
]
