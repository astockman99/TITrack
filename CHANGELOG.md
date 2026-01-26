# Changelog

All notable changes to TITrack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Phase 3: Manual price editing UI, import/export
- Phase 4: PyInstaller portable EXE packaging

## [0.2.0] - 2026-01-26

### Added

#### Web Dashboard
- FastAPI backend with REST API
- Browser-based dashboard at `http://localhost:8000`
- Real-time stats display: Total FE, Net Worth, Value/Hour, Runs, Prices
- Interactive charts using Chart.js:
  - Cumulative Value over time
  - Value/Hour over time (rolling 1-hour window)
- Recent Runs table with total loot value per run
- Run details modal showing loot breakdown with quantities and FE values
- Sortable inventory panel (click Qty/Value headers to sort)
- Auto-refresh every 5 seconds (toggleable)
- Dark theme matching game aesthetic

#### Exchange Price Learning
- `ExchangeMessageParser` for multi-line exchange protocol messages
- Parses `XchgSearchPrice` send/receive messages from game logs
- Correlates requests (item searched) with responses (price listings)
- Extracts FE-denominated prices from exchange responses
- Calculates reference price using 10th percentile of listings
- Stores learned prices with `source="exchange"`
- Console output when prices are learned: `[Price] Item Name: 0.021000 FE`

#### Value-Based Calculations
- Run value = raw FE + sum(item_qty × item_price) for priced items
- Value/Hour stat using total loot value instead of raw FE
- Net worth = Total FE + valued inventory items
- Loot details show both quantity and FE value per item
- Items without prices show "no price" indicator

#### API Endpoints
- `GET /api/status` - Server status, collector state, counts
- `GET /api/runs` - Paginated runs with `total_value` field
- `GET /api/runs/{id}` - Single run with loot breakdown
- `GET /api/runs/stats` - Aggregated stats with `value_per_hour`
- `GET /api/inventory` - Inventory with sort params (`sort_by`, `sort_order`)
- `GET /api/items` - Item database with search
- `GET /api/prices` - All learned prices
- `PUT /api/prices/{id}` - Update/create price
- `GET /api/stats/history` - Time-series data for charts

#### CLI
- `serve` command to start web server with background collector
- Options: `--port`, `--host`, `--no-browser`
- Graceful shutdown with Ctrl+C

#### Infrastructure
- Thread-safe database connections with locking
- Separate DB connections for collector and API
- Pydantic schemas for API request/response validation
- CORS middleware for local development
- Static file serving for dashboard

### Changed
- Dependencies: Added `fastapi>=0.109.0`, `uvicorn[standard]>=0.27.0`
- Collector now accepts `on_price_update` callback
- Repository adds `get_run_value()` method for value calculations

### Fixed
- Variable shadowing bug in runs API that caused runs to disappear
- FE currency now correctly valued at 1:1 in inventory and loot displays

### Technical
- 118 tests passing (85 Phase 1 + 20 API + 13 exchange parser)
- Thread-safe SQLite access with `threading.Lock`

## [0.1.1] - 2026-01-26

### Fixed
- Level transition pattern updated to match actual game log format
  - Changed from `LevelMgr@ EnterLevel` to `SceneLevelMgr@ OpenMainWorld END!`
- Hub zone detection patterns expanded to include:
  - `/01SD/` (Ember's Rest hideout path)
  - `YuJinZhiXiBiNanSuo` (Ember's Rest Chinese name)

### Added
- Zone name mapping system (`data/zones.py`)
  - Maps internal Chinese pinyin zone names to English display names
  - `get_zone_display_name()` function for lookups
  - Extensible dictionary for user-added mappings
- CLI now displays English zone names in `show-runs` and `tail` output

### Verified
- Real-world testing with live game data
- Successfully tracked multiple map runs with accurate FE and loot tallies
- Run duration timing working correctly

## [0.1.0] - 2026-01-26

### Added

#### Core Infrastructure
- Project structure with `src/titrack/` layout
- `pyproject.toml` with dev dependencies (pytest, black, ruff)
- Comprehensive `.gitignore` for Python projects

#### Domain Models (`core/models.py`)
- `SlotKey` - Unique identifier for inventory slots
- `SlotState` - Current state of an inventory slot
- `ItemDelta` - Computed change in item quantity
- `Run` - Map/zone run with timestamps
- `Item` - Item metadata from database
- `Price` - Item valuation in FE
- `ParsedBagEvent` - Parsed BagMgr modification
- `ParsedContextMarker` - Parsed ItemChange start/end
- `ParsedLevelEvent` - Parsed level transition
- `EventContext` enum - PICK_ITEMS vs OTHER

#### Log Parser (`parser/`)
- `patterns.py` - Compiled regex for BagMgr, ItemChange, LevelMgr
- `log_parser.py` - Parse single lines to typed events
- `log_tailer.py` - Incremental file reading with:
  - Position tracking for resume
  - Log rotation detection
  - Partial line buffering

#### Delta Calculator (`core/delta_calculator.py`)
- Pure function computing deltas from state + events
- Handles new slots, quantity updates, item swaps
- In-memory state with load/save capability

#### Run Segmenter (`core/run_segmenter.py`)
- State machine tracking active run
- Hub zone detection (hideout, town, hub, lobby, social)
- EnterLevel triggers run transitions

#### Database Layer (`db/`)
- `schema.py` - DDL for 7 tables:
  - settings, runs, item_deltas, slot_state
  - items, prices, log_position
- `connection.py` - SQLite with WAL mode, transaction support
- `repository.py` - Full CRUD for all entities

#### Collector (`collector/collector.py`)
- Main orchestration loop
- Context tracking (inside PickItems block or not)
- Callbacks for deltas, run start/end
- File processing and live tailing modes

#### Configuration (`config/settings.py`)
- Auto-detect log file in common Steam locations
- Default DB path: `%LOCALAPPDATA%\TITrack\tracker.db`
- Portable mode support

#### CLI (`cli/commands.py`)
- `init` - Initialize database, optionally seed items
- `parse-file` - Parse log file (non-blocking)
- `tail` - Live tail with delta output
- `show-runs` - List recent runs with FE totals
- `show-state` - Display current inventory

#### Item Database
- `tlidb_items_seed_en.json` with 1,811 items
- Includes name_en, name_cn, icon URLs, TLIDB links

#### Test Suite (85 tests)
- Unit tests for all modules
- Integration tests for full collector workflow
- Sample log fixture for testing

### Technical Details
- Python 3.11+ required
- Zero runtime dependencies for Phase 1 (stdlib only)
- SQLite WAL mode for concurrent access
- Position persistence for resume after restart
