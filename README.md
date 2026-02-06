# TITrack - Torchlight Infinite Local Loot Tracker

A privacy-focused, fully local Windows desktop application that tracks loot from Torchlight Infinite by parsing game log files. Calculate profit per map run, track net worth, and analyze your farming efficiency.

Inspired by [WealthyExile](https://github.com/WealthyExile) for Path of Exile.

## Quick Start (Download)

**No installation required** - portable app, just extract and run.

### Recommended: Use Setup (Easiest)

1. Go to [Releases](https://github.com/astockman99/TITrack/releases/latest)
2. Download `TITrack-Setup.exe`
3. Run it, choose where to extract (e.g., `C:\TITrack`)
4. Click **Extract**, then **Open Folder**
5. Run `TITrack.exe` from the extracted folder
6. If this is your first time, log in to your character in Torchlight Infinite

The Setup downloads and extracts TITrack without Windows security restrictions that can cause issues with manual ZIP extraction.

### Alternative: Manual ZIP Download

1. Download `TITrack-x.x.x-windows.zip` from [Releases](https://github.com/astockman99/TITrack/releases/latest)
2. Extract to any folder
3. **Unblock the files** (see [Windows Defender / SmartScreen](#windows-defender--smartscreen) below)
4. Run `TITrack.exe`

The app opens in a native window. Your data is stored in a `data` folder beside the exe.

### Windows Defender / SmartScreen

Since TITrack is not code-signed, Windows may show security warnings:

- **SmartScreen warning**: Click "More info" → "Run anyway". This is normal for unsigned applications.
- **First run may fail**: Windows marks downloaded files as untrusted ("Mark of the Web"), which can prevent DLLs from loading. If the native window doesn't open, the app will fall back to browser mode.

**To enable native window mode**, unblock all extracted files using PowerShell:
```powershell
Get-ChildItem -Path "C:\path\to\TITrack" -Recurse | Unblock-File
```

Or right-click the folder → Properties → check "Unblock" (if available).

**Note:** Unblocking just the ZIP before extracting is not sufficient - Windows' built-in extractor still marks the extracted files. You must unblock after extracting.

If the app still won't start, check the log file at `data\titrack.log` (beside the EXE) for error details.

### First Time Setup

1. **Game Location**: TITrack auto-detects Steam and standalone client installations. If needed, it will prompt you to select the game folder
2. **Character Detection**: If you've played before with logging enabled, your character is detected automatically. Otherwise, log in with your character
3. **Inventory Sync**: Click the **Sort** button in your bag to capture your full inventory
4. **Learn Prices**: Search items on the in-game Exchange - prices are captured automatically

### Portable Mode

To keep all data beside the EXE (for USB drives, etc.):
```
TITrack.exe --portable
```

---

## Current Status: Phase 4 Complete ✓

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✓ Complete | Log parsing, delta tracking, run segmentation, CLI |
| Phase 2 | ✓ Complete | Web UI, REST API, charts, exchange price learning |
| Phase 3 | ✓ Complete | Cloud sync for crowd-sourced pricing (opt-in) |
| Phase 4 | ✓ Complete | PyInstaller portable EXE, native window, auto-update |

## Features

- **Native Window**: Runs in a standalone window (no browser needed)

- **Auto-Update**: Checks for updates on startup, download and install with one click

- **Mini-Overlay**: Compact always-on-top window for in-game stats:
  - Launch with `TITrack.exe --overlay` or click "Overlay" button in dashboard
  - True transparency with click-through data boxes (game clickable underneath)
  - Shows all key stats: Net Worth, Value/Hour, Value/Map, Runs, Avg Time, Total Time
  - Live loot tracking during active runs with zone, duration, and item drops
  - Scrollable loot list with slim dark scrollbar (scrollbar remains interactive)
  - Previous run preservation: when map ends, loot stays visible as "Previous Run"
  - Adjustable font size (A-/A+ buttons, 70%-160% range, setting persisted)
  - Hide loot pickups option in Settings for compact stats-only view
  - Draggable header, resizable, pin/unpin always-on-top

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

- **Real-Time Tracking** (Optional):
  - Toggle in Settings to use wall-clock time for Value/Hour and Total Time
  - Includes downtime between maps for realistic session productivity
  - Pause button to exclude breaks from calculations
  - Avg Run Time always uses in-map duration regardless of mode

- **Value Calculations**:
  - Run value = FE gained + (item quantity × item price) for all priced items
  - Value/Hour calculated from rolling 1-hour windows
  - Net worth = Total FE + valued inventory items

- **CLI Commands**: init, parse-file, tail, show-runs, show-state, serve

## Development Setup

> **Regular users**: See [Quick Start](#quick-start-download) above. This section is for developers only.

### Prerequisites

- Python 3.11 or higher
- Windows 10/11
- Torchlight Infinite (Steam or standalone client)

### Setup

```bash
# Clone the repository
git clone https://github.com/astockman99/TITrack.git
cd TITrack

# Install with dependencies
pip install -e ".[dev]"

# Initialize database and seed items
python -m titrack init --seed tlidb_items_seed_en.json
```

### Building the EXE

```bash
pip install pyinstaller

# Build WPF overlay first (requires .NET 8 SDK)
dotnet publish overlay/TITrackOverlay.csproj -c Release -o overlay/publish

# Build main application (includes overlay automatically)
pyinstaller ti_tracker.spec --noconfirm
```

The output is in `dist/TITrack/`. Zip this folder for distribution.

## Usage (Development Mode)

### Start the Web Dashboard

```bash
# Start server (opens browser automatically)
python -m titrack serve

# Options
python -m titrack serve --port 8080        # Custom port
python -m titrack serve --no-browser       # Don't open browser
```

**Note**: If you've played before with logging enabled, TITrack detects your character automatically on startup. Otherwise, log in with your character for detection to begin.

**Custom Install Location**: TITrack auto-detects common Steam and standalone client installation paths. If your game is installed elsewhere, TITrack will prompt you to enter the game directory. The setting is saved and persists across restarts.

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
| `POST /api/runs/pause` | Toggle realtime tracking pause |
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
| `GET /api/update/status` | Current version and update status |
| `POST /api/update/check` | Check for available updates |
| `POST /api/update/download` | Download available update |
| `POST /api/update/install` | Install and restart (exits app) |

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
│   ├── updater/                # Auto-update system
│   │   ├── github_client.py    # GitHub Releases API
│   │   ├── manager.py          # Update orchestration
│   │   └── installer.py        # Download and apply updates
│   ├── db/                     # SQLite layer
│   ├── collector/              # Main collection loop
│   ├── config/                 # Settings
│   └── cli/                    # CLI commands
├── overlay/                    # WPF overlay application (.NET 8)
│   ├── TITrackOverlay.csproj
│   ├── MainWindow.xaml         # UI layout
│   └── MainWindow.xaml.cs      # Overlay logic
├── setup/                      # TITrack-Setup.exe (portable extractor)
├── supabase/migrations/        # Supabase schema
├── tests/                      # 118 tests
├── pyproject.toml
└── tlidb_items_seed_en.json    # 1,811 items
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
