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
- `runs` - map instances (start_ts, end_ts, zone_sig)
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
- `GET /api/prices` - List all prices
- `GET /api/prices/export` - Export prices as seed-compatible JSON
- `GET /api/prices/{id}` - Get price for item
- `PUT /api/prices/{id}` - Update price

### Stats
- `GET /api/stats/history` - Time-series data for charts
- `GET /api/stats/zones` - List all zones encountered (for translation)

### Icons
- `GET /api/icons/{id}` - Proxy icon from CDN (handles headers server-side, caches results)

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

## Known Limitations / TODO

- **Timemark level not tracked**: The game log zone paths are identical regardless of Timemark level (e.g., 7-0 vs 8-0). Runs of the same zone are grouped together. To support per-Timemark tracking, would need to find another log line that indicates the Timemark level (possibly when selecting beacon or starting map) or add manual run tagging in the UI.
