# Changelog

All notable changes to TITrack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Gear tab allowlist**: Destiny items (Fates, Kismets), Prisms, and Divinity items (Pacts, Fragments, God Divinities) are now tracked from the Gear tab despite the general gear exclusion. These item types have stable, tradeable prices. Configured via `ALLOWED_GEAR_TYPE_CN` in `inventory.py` — 263 items across 14 type categories.
- **Deep Space zone names**: Boundless Hunting Ground, Core Mine, Desert Pasture, Barren Wilderness, Vast Wasteland
- **Hide Items search**: Search bar in the Hide Items modal to quickly filter items by name

### Fixed
- **Active run continuity across sub-zones**: When returning from Nightmare or Arcana (Fateful Contest) sub-zones, the Current Run panel now correctly resumes the original map's timer and loot instead of starting fresh. Timer only counts time in the normal map (excludes sub-zone time). Entering a sub-zone still shows it as a separate active run with its own timer and loot.
- **Active run timer not resetting between maps**: Running the same zone consecutively no longer carries over the previous run's timer into the new run

---

## [0.4.8] - 2026-02-13

### Added
- Abyssal Vault secret realm zone name
- **Economy button**: Opens titrack.ninja economy website from the dashboard header
- **Clickable item names**: Inventory and loot report item names now link to titrack.ninja/item/{id} for detailed price data
- **Ko-fi link**: Footer link to help cover server costs

### Changed
- Overlay no longer takes a separate slot in the Windows taskbar
- Sparkline clicks now open titrack.ninja item page in browser instead of local price history modal

### Removed
- Local price history modal (replaced by titrack.ninja economy website)

### Fixed
- Browser fallback crash when WebView2/EdgeChromium is unavailable (affected users with MOTW-blocked DLLs since v0.2.0)

---

## [0.4.7] - 2026-02-11

### Added
- **Cumulative Value stat**: New stat in the dashboard header between Net Worth and Value/Hour showing total loot value across all runs.
- **Exclude Hidden Items from Net Worth**: New toggle in the "Hide Items" modal lets you choose whether hidden items count toward net worth. Off by default (existing behavior preserved). When enabled, hidden items are excluded from net worth calculations.
- **Fateful Contest (Arcana)**: Added zone name translation for the Arcana league mechanic sub-zone (`SuMingTaLuo`). Entering Fateful Contest from within a map no longer splits the map into two separate runs — the surrounding map segments are recombined, matching existing Nightmare/Twinightmare behavior.
- **Path of the Brave support**: Runs now display as "Path of the Brave" instead of the boss arena name. Proof of the Brave item consumption is tracked as map costs (requires Map Costs setting enabled).
- **Trial of Divinity**: Added zone name translation for the Trial of Divinity (`KD_JuLiShiLian000`).

---

## [0.4.6] - 2026-02-10

### Added
- **Hide Items from Inventory**: New "Hide Items" button on the inventory panel lets you hide items you don't care about (e.g., beacons bought for mapping). Hidden items are removed from the inventory list but still count toward net worth. Per-character, persists across sessions.

### Fixed
- **Overlay Resize Snap-Back**: Fixed overlay window snapping back to its default size after the user resized it, caused by the hide-loot setting check resetting the height every 2 seconds
- **Zone Name**: Added translation for Secret Realm - Sea of Rites (`HD_EMengZhiXia`)
- **Auto-Updater File Lock**: Added retry loop to verify `TITrack.exe` is unlocked before overwriting during update, preventing potential update failures on slower systems

### Improved
- **Overlay Responsive Padding**: Overlay padding and margins now scale proportionally when the window is resized smaller, allowing a much more compact layout (minimum width reduced from 280px to 180px)

---

## [0.4.5] - 2026-02-08

### Fixed
- **Trade House Sales Counted as Map Loot**: Fixed collecting trade house (Exchange) sales while inside a map being counted as loot drops, skewing Value/Hour, Value/Map, and loot report stats. Events with proto names `Push2` and `XchgReceive` now update inventory (net worth) without creating deltas.
- **Item Recycling Counted as Map Loot**: Fixed recycling items (e.g., memories → Memory Thread) while inside a map being counted as loot drops. The `ExchangeItem` proto name is now excluded from delta tracking.
- **Broken Native Window Rendering**: Fixed pywebview silently falling back to MSHTML (Internet Explorer) when WebView2 is unavailable, rendering unstyled HTML with non-functional buttons. Now forces EdgeChromium and falls back to browser mode with a message box linking to the WebView2 Runtime download.
- **FE Price Spike in Sparklines**: Fixed bad cloud submissions for FE (Flame Elementium) causing price chart spikes. FE is the base currency (always 1:1) and is now excluded from cloud sync uploads, downloads, and history entirely.
- **Skill Item Names**: Fixed 543 skill items showing internal icon-filename placeholders (e.g., `SkillIcon_Support_ProtectWhenChanneling`) instead of proper English names (e.g., "Guard"). All 6 skill categories updated: Active, Support, Passive, Activation Medium, Magnificent, and Noble. Existing users get corrected names automatically on next launch.
- **Zone Names**: Added translations for Unholy Pedestal (Secret Realm) and Mistville (legacy league mechanic) zones that were showing internal Chinese names.

---

## [0.4.4] - 2026-02-07

### Fixed
- **Emoji Character Names**: Fixed game log switching to UTF-16 encoding when player names contain emoji characters, which broke log parsing entirely
- **Auto-Updater Skipping Overlay**: Fixed auto-updater failing to update TITrackOverlay.exe when the overlay was still running during update (Windows file lock). The updater now kills the overlay process before applying the update, with a fallback taskkill in the batch script.
- **Blank White Window on Startup**: Fixed native window sometimes showing all-white with no functional buttons, caused by pywebview opening before the server was ready. Replaced fixed 500ms sleep with a poll loop that waits for the server to be fully started (up to 10 seconds).
- **Map Cost Not Tracked When Last Item Consumed**: Fixed compass/beacon cost not being recorded when using the last one in a stack. The game logs `BagMgr@:RemoveBagItem` instead of the normal `Modfy BagItem` when a slot is fully emptied. Added a parser for this line format.

---

## [0.4.3] - 2026-02-06

### Added
- **Cloud Sync RPC Function**: Server-side function for efficient price history downloads, reducing bandwidth from ~38MB to ~1-2MB per sync
- **Cloud Sync Logging**: Sync operations now log to titrack.log for easier debugging

### Fixed
- **Character Detection on Startup**: Fixed race condition where collector thread started before player change callback was wired up, causing character detection to fail until app restart
- **Character Pre-Seeding**: App now detects character from existing log on startup instead of always waiting for a fresh login
- **Cloud Sync Price Download**: Fixed cloud prices not downloading when toggling sync on, caused by season context not being set from pre-seeded player info
- **Cloud Sync Data Truncation**: Fixed Supabase's 1000-row default limit silently truncating price and history downloads, causing missing prices and empty sparklines
- **Cloud Sync History Efficiency**: History downloads now only fetch data for items in the user's inventory instead of all community-priced items (~124 items vs ~1500+)
- **Large Log File Handling**: Fixed character detection failing on large game logs by reading last 5MB first with fallback to full scan

### Changed
- **Updated Instructions**: Help text and README updated to reflect automatic character detection from existing game logs (no relog required for returning users)

---

## [0.4.2] - 2026-02-06

### Added
- **Real-Time Tracking Mode**: Optional wall-clock time tracking for Value/Hour and Total Time
  - Toggle in Settings → "Real-Time Tracking"
  - When enabled, Total Time counts wall-clock elapsed time from first run start instead of summed in-map durations
  - Value/Hour reflects actual session productivity including town/hideout downtime
  - Avg Run Time always uses in-map duration regardless of mode
  - Value/Hour chart uses wall-clock window duration when enabled
- **Pause Button**: Pause/resume tracking during breaks (appears when Real-Time Tracking is enabled)
  - Shows next to Total Time in the dashboard header
  - Also available in the WPF overlay header
  - Paused time is excluded from all calculations
  - Pause state is cleared on stats reset
- **New API Endpoint**: `POST /api/runs/pause` - Toggle realtime tracking pause on/off
- **Overlay Settings Section**: New section in Settings modal for overlay-specific options
  - **Hide Loot Pickups**: Toggle to hide the loot section in the overlay for a compact stats-only view
  - Overlay auto-resizes to fit when loot is hidden
- **Auto-Update Check on Startup**: Silently checks for updates when the app launches and shows a notification modal if a new version is available
- **Discord Link**: Added Discord invite link in the dashboard footer

### Changed
- **Total Time Display**: Now shows seconds (e.g., "2h 15m 30s" instead of "2h 15m") in dashboard and overlay
- **Smooth Time Ticking**: Both dashboard and overlay count Total Time second-by-second locally without extra backend requests

### Fixed
- **Fluorescent Memory Items**: Fixed 17 items showing untranslated placeholder names
- **Cloud Price Downloads**: Fixed cloud prices not downloading immediately on fresh install

---

## [0.4.1] - 2026-02-05

### Added

#### Overlay Improvements
- **Font Scaling**: A-/A+ buttons to adjust text size (70%-160% range)
  - Setting is persisted and restored when overlay reopens
- **Scrollable Loot List**: Slim dark-themed scrollbar for long loot lists
  - Scrollbar remains interactive while loot content is click-through
- **High-Quality Icons**: Improved bitmap scaling for sharper item icons

#### Setup.exe Improvements
- **Auto-Detect Existing Installation**: When updating via Setup.exe, it now checks common locations and desktop shortcuts for existing TITrack installations and defaults to that path to preserve user data

### Changed
- **Cloud Oasis**: Changed from hub zone back to normal trackable zone (Sandlord content where players earn FE)

### Fixed
- **Settings Persistence After Auto-Update**: Fixed database path resolution using `cwd()` instead of app directory, which caused settings (trade tax, map costs) to be lost after updates
- **Database Migration**: Added migration logic to find and recover databases from legacy locations when updating from older versions
- **Log Directory Priority**: Saved log directory setting now takes priority over auto-detection (fixes F: drive and non-standard install locations)
- **Log Path Capitalization**: Added alternate path pattern for different folder capitalizations (TorchLight vs Torchlight)
- **Trade Tax on Map Costs**: Fixed trade tax being incorrectly applied to consumed items (compass/beacon costs)

---

## [0.4.0] - 2026-02-04

### Added

#### WPF Overlay Enhancements
- **Previous Run Preservation**: When a map ends, the overlay now keeps showing the loot and "This Run" value instead of clearing. The label changes to "Previous Run" and the timer stops at the final duration.
- **Click-Through Data Boxes**: Stats grid and loot section are now click-through, allowing interaction with the game underneath. Header (drag), buttons, and resize grip remain interactive.

#### New Zone Translations
- **Rusted Abyss**: Boss zone (`YJ_XiuShiShenYuan`)
- **Cloud Oasis**: Season 10 hub zone (`YunDuanLvZhou`) - now properly detected as hub
- **Ruins of Aeterna: Boundless**: Season 10 content (`CC1_SiWangMiCheng`)
- **The Frozen Canvas**: Season 10 content (`XueYuRongLu`)

### Changed

#### Overlay Display Improvements
- **FE Values**: Now display with 2 decimal places (e.g., "1,234.56") to match main app precision
- **Net Worth**: Rounded to whole number for cleaner display
- **Color Swap**: FE value column is now green, quantity column is gray (swapped for better visual hierarchy)

#### Zone Detection Fixes
- **Demiman Village**: Fixed suffix from 36 to 02, now correctly shows "Glacial Abyss - Demiman Village" at all Timemark levels

### Fixed

- **Trade Tax Calculation Bug**: Individual loot item values now include trade tax when enabled, matching the gross total. Previously items showed pre-tax values but the total was post-tax, causing apparent math errors.
- **Database Locking Crash**: Fixed race condition where concurrent database access from overlay polling and collector writes could cause "database locked" errors. All transactions now properly coordinate through a single threading lock.

---

## [Unreleased]

### Added

#### Cloud Sync (Opt-in Crowd-Sourced Pricing)
- Anonymous device-based identification using UUIDs
- Background sync threads for uploads (60s) and downloads (5min)
- Local queue for offline operation with automatic retry
- Anti-poisoning protection: median aggregation requiring 3+ unique contributors
- Price history with 72-hour local caching for sparklines
- Cloud sync toggle in dashboard header with status indicator
- New `src/titrack/sync/` module:
  - `device.py` - UUID generation and validation
  - `client.py` - Supabase client wrapper
  - `manager.py` - Sync orchestration with background threads

#### New API Endpoints
- `GET /api/cloud/status` - Sync status, queue counts, last sync times
- `POST /api/cloud/toggle` - Enable/disable cloud sync
- `POST /api/cloud/sync` - Trigger manual sync
- `GET /api/cloud/prices` - Cached community prices
- `GET /api/cloud/prices/{id}/history` - Price history for sparklines
- `GET /api/settings/{key}` - Read whitelisted settings
- `PUT /api/settings/{key}` - Update whitelisted settings

#### New Database Tables
- `cloud_sync_queue` - Prices waiting to upload
- `cloud_price_cache` - Downloaded community prices
- `cloud_price_history` - Hourly price snapshots for sparklines

#### Dashboard Updates
- Cloud Sync toggle with connection status indicator
- Instructions modal updated with Cloud Sync documentation
- Sparkline column in inventory (when cloud sync enabled)

#### Supabase Backend
- `supabase/migrations/001_initial_schema.sql` with:
  - Tables: `device_registry`, `price_submissions`, `aggregated_prices`, `price_history`
  - RPC function: `submit_price()` with rate limiting (100/device/hour)
  - Scheduled functions: `aggregate_prices()`, `snapshot_price_history()`, `cleanup_old_submissions()`
  - Row-level security policies for public read access

### Changed
- Collector now accepts optional `sync_manager` parameter
- Database schema version bumped to 3
- Added `supabase` as optional dependency (`pip install titrack[cloud]`)

### Planned
- Phase 3: Manual price editing UI, import/export
- Phase 4: PyInstaller portable EXE packaging

## [0.2.7] - 2026-02-01

### Added
- **Loot Report**: New cumulative loot statistics feature accessible via "Report" button in Recent Runs section
  - Summary stats: Gross Value, Map Costs (if enabled), Profit, Runs, Total Time, Profit/Hour, Profit/Map, Unique Items
  - Doughnut chart visualization showing top 10 items by value with "Other" category
  - Scrollable table with all items: Icon, Name, Quantity, Unit Price, Total Value, Percentage
  - CSV export with native "Save As" dialog for choosing file location
  - Only includes items picked up during map runs (excludes trade house purchases)
- **New API Endpoints**:
  - `GET /api/runs/report` - Cumulative loot statistics across all runs
  - `GET /api/runs/report/csv` - Export loot report as CSV file

### Changed
- Loot report respects trade tax and map cost settings when calculating values

## [0.2.6] - 2026-01-31

### Added
- **Map Cost Tracking**: Optional feature to track compass/beacon consumption when opening maps
  - Enable via Settings modal (gear icon) → "Map Costs" toggle
  - Captures `Spv3Open` events and associates costs with the next map run
  - Run values show net profit (gross loot value minus map costs)
  - Hover over cost values to see breakdown of consumed items
  - Warning indicator when some cost items have unknown prices
  - Affects stats: Value/Hour and Value/Map reflect net values
- **Unified Settings Modal**: New settings panel accessed via gear icon
  - Trade Tax toggle (moved from header)
  - Map Costs toggle
  - Game Directory configuration (moved from separate modal)

### Changed
- Run details modal now sorts items by FE value (highest first) instead of quantity
- Run details modal now shows FE value as the primary number, quantity as secondary
- Trade Tax toggle moved from header to Settings modal

## [0.2.5] - 2026-01-31

### Added
- **Trade Tax Toggle**: Option to calculate item values with 12.5% trade house tax applied
  - Toggle in dashboard header applies tax to non-FE items
  - Affects all value displays: runs, inventory net worth, value/hour
  - Setting persists across sessions
- **Live Drops Display**: Real-time loot tracking during active map runs
  - "Current Run" panel shows zone name, duration, and running value total
  - Items appear as they're picked up, sorted by value (highest first)
  - Panel clears when returning to hub, run moves to Recent Runs
  - Pulsing green indicator shows when a run is active
- New API endpoint: `GET /api/runs/active` - Returns current active run with live loot

### Changed
- Disabled UPX compression in PyInstaller build to avoid Windows Defender false positives
- Recent Runs list now filters by completion status (only shows runs with end_ts)
- Rebuilt PyInstaller from source for fresh bootloader signature

### Fixed
- Active run panel properly clears when returning to hub zone
- Value display in Current Run panel now renders HTML correctly

## [0.2.4] - 2026-01-30

### Fixed
- Version display now shows correct version (was stuck at 0.2.0)
- Demiman Village zone now correctly shows as "Glacial Abyss - Demiman Village" (fixed suffix 36)
- Zone names now work correctly at all Timemark levels (refactored to suffix-based lookup)

### Changed
- Updated README and help modals to clarify users must NOT close the game when relogging
- Zone lookup uses `level_id % 100` suffix for ambiguous zones instead of exact LevelId matching

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
