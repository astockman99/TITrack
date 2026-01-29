# TITrack - Torchlight Infinite Local Loot Tracker

A privacy-focused, fully local Windows desktop application that tracks loot from Torchlight Infinite by parsing game log files. Calculate profit per map run, track net worth, and analyze your farming efficiency.

Inspired by [WealthyExile](https://github.com/WealthyExile) for Path of Exile.

## Current Status: Phase 3 Complete ✓

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✓ Complete | Log parsing, delta tracking, run segmentation, CLI |
| Phase 2 | ✓ Complete | Web UI, REST API, charts, exchange price learning |
| Phase 3 | ✓ Complete | Cloud sync for crowd-sourced pricing (opt-in) |
| Phase 4 | Planned | PyInstaller portable EXE packaging |

### What Works Now

- **Web Dashboard** at `http://localhost:8000` with:
  - Real-time stats: Total FE, Net Worth, Value/Hour, Run Count, Prices Learned
  - Interactive charts: Cumulative Value and Value/Hour over time
  - Recent Runs table with total loot value per run
  - Sortable Inventory panel (by value or quantity)
  - Run details modal showing loot breakdown with values
  - Auto-refresh every 5 seconds

- **Exchange Price Learning**:
  - Automatically captures prices when you search items on the in-game exchange
  - Parses `XchgSearchPrice` messages from game logs
  - Calculates reference price (10th percentile of listings)
  - Updates inventory valuations and run values automatically

- **Cloud Sync** (Optional):
  - Share and receive community pricing data anonymously
  - Toggle on/off in the dashboard header
  - Background sync: uploads every 60s, downloads every 5min
  - Anti-poisoning: median aggregation requiring 3+ contributors
  - Works offline with local caching
  - Only Exchange prices are shared (never manual edits)

- **Value Calculations**:
  - Run value = FE gained + (item quantity × item price) for all priced items
  - Value/Hour calculated from rolling 1-hour windows
  - Net worth = Total FE + valued inventory items

- **CLI Commands**: init, parse-file, tail, show-runs, show-state, serve

## Installation

### Prerequisites

- Python 3.11 or higher
- Windows 10/11
- Torchlight Infinite installed via Steam

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd TITrack

# Install with dependencies
pip install -e ".[dev]"

# Initialize database and seed items
python -m titrack init --seed tlidb_items_seed_en.json
```

## Usage

### Start the Web Dashboard

```bash
# Start server (opens browser automatically)
python -m titrack serve

# Options
python -m titrack serve --port 8080        # Custom port
python -m titrack serve --no-browser       # Don't open browser
```

**Important**: After starting the tracker, you must **log in (or relog) your character** in-game for tracking to begin. The dashboard will show "Waiting for character login..." until a character is detected.

**Custom Install Location**: If Torchlight Infinite is installed in a non-standard location, TITrack will prompt you to enter the game directory. The setting is saved and persists across restarts.

The dashboard shows:
- **Header Stats**: Total FE, Net Worth, Value/Hour, Runs, Learned Prices
- **Charts**: Cumulative value and value/hour over time
- **Recent Runs**: Click "Details" to see loot breakdown with values
- **Inventory**: Sortable by Value or Quantity (click column headers)

### Learn Item Prices

1. Start the tracker: `python -m titrack serve`
2. In game, open the Exchange and search for any item
3. The tracker captures the price automatically
4. Console shows: `[Price] Item Name: 0.021000 FE`
5. All values update to reflect the new price

### Sync Full Inventory

The tracker only sees items when they change in the game log. To sync your full current inventory:

1. Open your bag in game
2. Click the **Sort** button (auto-organizes items)
3. The tracker captures a full inventory snapshot

This is useful when starting the tracker for the first time or if inventory state gets out of sync.

### CLI Commands

```bash
# Initialize database (first time setup)
python -m titrack init --seed tlidb_items_seed_en.json

# Start web server with live tracking
python -m titrack serve

# Live tail the log file (CLI mode)
python -m titrack tail

# Show recent runs
python -m titrack show-runs

# Show current inventory
python -m titrack show-state
```

### Options

```bash
--db PATH       # Custom database path (default: %LOCALAPPDATA%\TITrack\tracker.db)
--portable      # Use portable mode (data stored beside executable)
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | Server status and counts |
| `GET /api/runs` | List runs with values and loot |
| `GET /api/runs/{id}` | Single run details |
| `GET /api/runs/stats` | Aggregated statistics |
| `GET /api/inventory` | Current inventory (sortable) |
| `GET /api/items` | Item database |
| `GET /api/prices` | Learned prices |
| `PUT /api/prices/{id}` | Update a price |
| `GET /api/stats/history` | Time-series data for charts |
| `GET /api/cloud/status` | Cloud sync status |
| `POST /api/cloud/toggle` | Enable/disable cloud sync |
| `POST /api/cloud/sync` | Trigger manual sync |
| `GET /api/cloud/prices` | Cached community prices |
| `GET /api/cloud/prices/{id}/history` | Price history for sparklines |

## Project Structure

```
TITrack/
├── src/titrack/
│   ├── api/                    # FastAPI backend
│   │   ├── app.py              # App factory
│   │   ├── schemas.py          # Pydantic models
│   │   └── routes/             # API endpoints
│   ├── web/static/             # Dashboard frontend
│   │   ├── index.html
│   │   ├── app.js
│   │   └── style.css
│   ├── core/                   # Domain logic
│   ├── parser/                 # Log parsing
│   │   ├── log_parser.py
│   │   ├── log_tailer.py
│   │   └── exchange_parser.py  # Price message parsing
│   ├── sync/                   # Cloud sync module
│   │   ├── client.py           # Supabase client
│   │   ├── device.py           # Device UUID management
│   │   └── manager.py          # Sync orchestration
│   ├── db/                     # SQLite layer
│   ├── collector/              # Main collection loop
│   ├── config/                 # Settings
│   └── cli/                    # CLI commands
├── supabase/migrations/        # Supabase schema
├── tests/                      # 118 tests
├── pyproject.toml
├── tlidb_items_seed_en.json    # 1,811 items
└── CLAUDE.md
```

## Architecture

### Data Flow

```
Game Log File
      │
      ▼
┌─────────────────┐
│   Log Tailer    │ ← Incremental reading
└─────────────────┘
      │
      ├─────────────────────────┐
      ▼                         ▼
┌─────────────────┐   ┌─────────────────────┐
│   Log Parser    │   │  Exchange Parser    │
│  (game events)  │   │  (price messages)   │
└─────────────────┘   └─────────────────────┘
      │                         │
      └───────────┬─────────────┘
                  ▼
           ┌─────────────┐
           │  Collector  │ ← Orchestration
           └─────────────┘
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│  Delta   │ │   Run    │ │  Price   │
│Calculator│ │Segmenter │ │ Storage  │
└──────────┘ └──────────┘ └──────────┘
      │           │           │
      └───────────┴───────────┘
                  ▼
           ┌─────────────┐
           │  SQLite DB  │
           └─────────────┘
                  │
                  ▼
           ┌─────────────┐
           │ FastAPI +   │
           │ Web Dashboard│
           └─────────────┘
```

### Key Concepts

- **Flame Elementium (FE)**: Primary currency, ConfigBaseId = `100300`
- **ConfigBaseId**: Integer item type identifier from game logs
- **Delta**: Change in quantity (current - previous) for a slot
- **Run Value**: FE gained + sum(item_qty × item_price) for priced items
- **Reference Price**: 10th percentile of exchange listings

## Development

### Running Tests

```bash
# Run all 118 tests
pytest tests/

# Run with coverage
pytest tests/ --cov=titrack --cov-report=html

# Run specific test file
pytest tests/unit/test_exchange_parser.py -v
```

### Code Quality

```bash
black .
ruff check .
```

## Design Principles

1. **Privacy First**: All data stored locally by default
2. **No Cheating**: Only reads log files, no memory hooks
3. **Passive Price Learning**: Prices learned from your own exchange searches
4. **Pure Core**: Domain logic has no I/O, easy to test
5. **Incremental Processing**: Resume from last position, handle log rotation
6. **Opt-in Cloud**: Cloud sync is optional, anonymous, and transparent

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please:
1. Run tests before submitting PRs
2. Follow existing code style (black, ruff)
3. Add tests for new functionality
