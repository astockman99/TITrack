# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TITrack is a **Torchlight Infinite Local Loot Tracker** - a Windows desktop application that reads game log files to track loot, calculate profit per map run, and display net worth. Inspired by WealthyExile (Path of Exile tracker).

**Key constraints:**
- Fully local, no cloud/internet required
- Portable EXE distribution (no Python/Node install needed)
- Privacy-focused (all data stored locally)
- No cheating/hooking/memory reading - only parses log files

## Tech Stack

- **Language:** Python 3.11+
- **Backend:** FastAPI + Uvicorn
- **Database:** SQLite (WAL mode)
- **Frontend:** React (or HTML/HTMX for MVP)
- **Packaging:** PyInstaller (--onedir preferred)
- **Target:** Windows 10/11

## Build Commands (Planned)

```bash
# Testing
pytest tests/                    # Parser unit tests
pytest tests/e2e/               # End-to-end tests

# Building
pyinstaller ti_tracker.spec     # Build EXE

# Linting
black .
flake8 .
```

## Architecture

Five main components:

1. **Collector (Log Tailer + Parser)** - Watches TI log file, parses events, computes item deltas
2. **Local Database (SQLite)** - Stores runs, deltas, slot state, prices, settings
3. **Price Engine** - Maps ConfigBaseId to price_fe, supports manual edits and import/export
4. **Local Web UI** - FastAPI serves REST API + static files, opens in browser
5. **Packaged App** - PyInstaller EXE that starts all services

## Key Data Concepts

- **FE (Flame Elementium):** Primary valuation currency, ConfigBaseId = `100300`
- **ConfigBaseId:** Integer item type identifier from game logs
- **Delta tracking:** Logs report absolute stack totals (`Num=`), tracker computes changes vs previous state
- **Slot state:** Tracked per `(PageId, SlotId)` with current `(ConfigBaseId, Num)`

## Log Parsing

**Source:** `<SteamLibrary>\steamapps\common\Torchlight Infinite\UE_Game\Torchlight\Saved\Logs\UE_game.log`

**Key patterns to parse:**

```text
# Item pickup block
GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 671
GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end

# Inventory snapshot (triggered by sorting inventory in-game)
GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 609

# Map boundaries
LevelMgr@ EnterLevel ...
LevelMgr@ OpenLevel ...
```

**Parsing rules:**
- Incremental tail (handle log rotation)
- Delta = current `Num` - previous `Num` for same slot/item
- Tag changes inside PickItems block as "pickup-related"
- Handle unknown ConfigBaseIds gracefully (show as "Unknown <id>")
- `InitBagData` events update slot state but don't create deltas (used for inventory sync)

## Database Schema (Core Tables)

- `settings` - key/value config
- `runs` - map instances (start_ts, end_ts, zone_sig, level_id, level_type, level_uid)
- `item_deltas` - per-item changes with run_id, context, proto_name
- `slot_state` - current inventory state per (page_id, slot_id)
- `items` - item metadata (name, icon_url, category)
- `prices` - item valuation (price_fe, source, updated_ts)

## Item Database

`tlidb_items_seed_en.json` contains 1,811 items with:
- `id` (ConfigBaseId as string)
- `name_en`, `name_cn`
- `img` (icon URL)
- `url_en`, `url_cn` (TLIDB links)

Seeds the `items` table on first run.

## File Locations

| File | Purpose |
|------|---------|
| `TI_Local_Loot_Tracker_PRD.md` | Complete requirements document |
| `tlidb_items_seed_en.json` | Item database seed (1,811 items) |

## Storage Locations (Runtime)

- Default: `%LOCALAPPDATA%\TITracker\tracker.db`
- Portable mode: `.\data\tracker.db` beside exe

## MVP Requirements

1. Select & persist log file path
2. Tail log, parse PickItems + BagMgr updates
3. Compute deltas, store in DB
4. Segment runs (EnterLevel-based boundaries)
5. Display FE gained per run, profit/hr
6. Editable price list with import/export
7. Net worth from latest inventory
8. Packaged portable EXE

## API Endpoints

### Runs
- `GET /api/runs` - List recent runs with pagination
- `GET /api/runs/stats` - Summary statistics (value/hour, avg per run, etc.)
- `GET /api/runs/{run_id}` - Get single run details
- `POST /api/runs/reset` - Clear all run tracking data (preserves prices, items, settings)

### Items
- `GET /api/items` - List items (with search)
- `GET /api/items/{id}` - Get item by ConfigBaseId
- `PATCH /api/items/{id}` - Update item name

### Prices
- `GET /api/prices` - List all prices (filtered by current season)
- `GET /api/prices/export` - Export prices as seed-compatible JSON
- `POST /api/prices/migrate-legacy` - Migrate legacy prices (season_id=0) to current season
- `GET /api/prices/{id}` - Get price for item
- `PUT /api/prices/{id}` - Update price

### Stats
- `GET /api/stats/history` - Time-series data for charts
- `GET /api/stats/zones` - List all zones encountered (for translation)

### Icons
- `GET /api/icons/{id}` - Proxy icon from CDN (handles headers server-side, caches results)

### Player
- `GET /api/player` - Current player/character info (name, season)

### Other
- `GET /api/inventory` - Current inventory state
- `GET /api/status` - Server status

## Dashboard Features

- **Stats Header**: Net Worth, Value/Hour, Value/Map, Runs, Avg Run Time, Prices count
- **Charts**: Cumulative Value, Value/Hour (rolling)
- **Recent Runs**: Zone, duration, value with details modal
- **Current Inventory**: Sortable by quantity or value
- **Controls**: Reset Stats, Edit Items, Export Prices, Auto-refresh toggle

## Zone Translation

Zone names are mapped in `src/titrack/data/zones.py`. The `ZONE_NAMES` dictionary maps internal zone path patterns to English display names. Use `/api/stats/zones` to see all encountered zones and identify which need translation.

## Price Seeding

Prices can be seeded on init: `titrack init --seed items.json --prices-seed prices.json`

Export current prices via the UI "Export Prices" button or `GET /api/prices/export`.

## Zone Differentiation

Some zones share the same internal path across different areas (e.g., "Grimwind Woods" appears in both Glacial Abyss and Voidlands with the same path `YL_BeiFengLinDi201`).

These are differentiated using `LevelId` from the game logs:
- The `LevelMgr@ LevelUid, LevelType, LevelId` line is parsed before zone transitions
- `LEVEL_ID_ZONES` in `src/titrack/data/zones.py` maps specific LevelIds to zone names
- LevelId lookup takes priority over path-based lookup

To add a new ambiguous zone:
1. Run the zone and check the console for `(LevelId=XXXX)`
2. Add the mapping to `LEVEL_ID_ZONES` in `zones.py`

## Inventory Sync

To sync your full inventory with the tracker, use the **Sort** button in-game:
1. Open your inventory (bag)
2. Click the Sort/Arrange button (auto-organizes items)
3. The game logs `BagMgr@:InitBagData` lines for every slot
4. TITrack captures these and updates slot state without creating deltas

This is useful when:
- Starting the tracker for the first time (existing inventory not tracked)
- Inventory state gets out of sync
- You want to ensure accurate net worth calculation

## Player Info & Multi-Character Support

Player/character information is parsed from the main game log (`UE_game.log`). The parser looks for lines containing `+player+Name`, `+player+SeasonId`, etc.

- **Name**: Player's character name
- **SeasonId**: League/season identifier (mapped to display name in `player_parser.py`)

The dashboard displays the character name and season name in the header.

### Automatic Character Detection

When you switch characters in-game, TITrack automatically detects the change by monitoring player data lines in the log stream:

1. Player data lines (`+player+Name`, `+player+SeasonId`, etc.) are parsed as they appear
2. When a different character is detected, the collector switches context
3. Inventories, runs, and prices are isolated per character/season

### Data Isolation

Each character has isolated data using an **effective player ID**:
- If the log contains a `PlayerId`, that is used
- Otherwise, `{season_id}_{name}` is used as the identifier (e.g., `1301_MyChar`)

This ensures:
- **Inventory**: Each character has separate slot states
- **Runs/Deltas**: Tagged with season_id and player_id
- **Prices**: Isolated per season (seasonal vs permanent economies are separate)

### Migrating Legacy Prices

If you have prices from before multi-season support was added, they may be stored with `season_id=0`. To migrate them to your current season:

```bash
curl -X POST http://127.0.0.1:8000/api/prices/migrate-legacy
```

Run this while logged in as the character whose economy should receive the prices.

## Inventory Tab Filtering

The game inventory has 4 tabs identified by PageId:
- **PageId 100**: Gear (equipment) - **EXCLUDED from tracking**
- **PageId 101**: Skill
- **PageId 102**: Commodity (currency, crafting materials)
- **PageId 103**: Misc

The Gear tab is excluded because gear prices are too dependent on specific affixes to be reliably tracked. This filtering is defined in `src/titrack/data/inventory.py` and applied at:
- Collector level (bag events from excluded pages are skipped)
- Repository queries (slot states and deltas filtered by default)

To modify which tabs are tracked, edit `EXCLUDED_PAGES` in `src/titrack/data/inventory.py`.

## Cloud Sync (Crowd-Sourced Pricing)

TITrack supports opt-in cloud sync to share and receive community pricing data.

### Features

- **Anonymous**: Uses device-based UUIDs, no user accounts required
- **Opt-in**: Disabled by default, toggle in the UI header
- **Offline-capable**: Works fully offline, syncs when connected
- **Anti-poisoning**: Uses median aggregation with minimum 3 unique contributors

### How It Works

1. When you search an item in the in-game Exchange, TITrack captures the prices
2. If cloud sync is enabled, the price data is queued for upload
3. Background threads upload your submissions and download community prices
4. Community prices show as sparklines in the inventory table

### API Endpoints

- `GET /api/cloud/status` - Sync status, queue counts, last sync times
- `POST /api/cloud/toggle` - Enable/disable cloud sync
- `POST /api/cloud/sync` - Manual sync trigger
- `GET /api/cloud/prices` - Cached community prices
- `GET /api/cloud/prices/{id}/history` - Price history for sparklines

### Settings API

- `GET /api/settings/{key}` - Get setting (whitelisted keys only)
- `PUT /api/settings/{key}` - Update setting

### Database Tables (Cloud Sync)

- `cloud_sync_queue` - Prices waiting to upload
- `cloud_price_cache` - Downloaded community prices
- `cloud_price_history` - Hourly price snapshots for sparklines

### Settings Keys

| Key | Default | Description |
|-----|---------|-------------|
| `cloud_sync_enabled` | `"false"` | Master toggle |
| `cloud_device_id` | (generated) | Anonymous device UUID |
| `cloud_upload_enabled` | `"true"` | Upload prices to cloud |
| `cloud_download_enabled` | `"true"` | Download prices from cloud |

### Supabase Backend (Not Configured)

Cloud sync requires a Supabase backend. The backend is NOT configured by default. To enable:

1. Create a Supabase project
2. Run the SQL migrations to create tables and functions
3. Set environment variables:
   - `TITRACK_SUPABASE_URL` - Your project URL
   - `TITRACK_SUPABASE_KEY` - Your anon key
4. Or update the defaults in `src/titrack/sync/client.py`

Install the Supabase SDK: `pip install titrack[cloud]`

## Known Limitations / TODO

- **Timemark level not tracked**: The game log zone paths are identical regardless of Timemark level (e.g., 7-0 vs 8-0). Runs of the same zone are grouped together. To support per-Timemark tracking, would need to find another log line that indicates the Timemark level (possibly when selecting beacon or starting map) or add manual run tagging in the UI.
- **Cloud sync backend not configured**: The Supabase backend URLs/keys need to be configured before cloud sync will work.
