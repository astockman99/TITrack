"""CLI commands for testing and manual operation."""

import argparse
import json
import signal
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

from titrack.collector.collector import Collector
from titrack.config.logging import setup_logging, get_logger
from titrack.config.settings import Settings, find_log_file
from titrack.core.models import Item, ItemDelta, Price, Run
from titrack.data.zones import get_zone_display_name
from titrack.db.connection import Database
from titrack.db.repository import Repository
from titrack.parser.patterns import FE_CONFIG_BASE_ID
from titrack.parser.player_parser import get_enter_log_path, get_effective_player_id, parse_enter_log, parse_game_log, PlayerInfo
from titrack.sync.manager import SyncManager


def print_delta(delta: ItemDelta, repo: Repository) -> None:
    """Print a delta to console."""
    item_name = repo.get_item_name(delta.config_base_id)
    sign = "+" if delta.delta > 0 else ""
    context_str = f"[{delta.context.name}]" if delta.proto_name else ""
    print(f"  {sign}{delta.delta} {item_name} {context_str}")


def print_run_start(run: Run) -> None:
    """Print run start to console."""
    hub_str = " (hub)" if run.is_hub else ""
    zone_name = get_zone_display_name(run.zone_signature, run.level_id)
    print(f"\n=== Entered: {zone_name}{hub_str} ===")


def print_run_end(run: Run, repo: Repository) -> None:
    """Print run end summary to console."""
    if run.is_hub:
        return

    duration = run.duration_seconds or 0
    minutes = int(duration // 60)
    seconds = int(duration % 60)

    print(f"\n--- Run ended: {minutes}m {seconds}s ---")

    # Get run summary
    summary = repo.get_run_summary(run.id)
    if summary:
        fe_gained = summary.get(FE_CONFIG_BASE_ID, 0)
        print(f"  FE gained: {fe_gained}")

        # Show other items
        for config_id, total in sorted(summary.items()):
            if config_id != FE_CONFIG_BASE_ID and total != 0:
                name = repo.get_item_name(config_id)
                sign = "+" if total > 0 else ""
                print(f"  {sign}{total} {name}")


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize database and optionally seed items and prices."""
    settings = Settings.from_args(
        db_path=args.db,
        portable=args.portable,
        seed_file=args.seed,
    )

    print(f"Initializing database at: {settings.db_path}")

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)

    # Seed items if provided
    if settings.seed_file:
        print(f"Seeding items from: {settings.seed_file}")
        count = seed_items(repo, settings.seed_file)
        print(f"  Loaded {count} items")
    else:
        existing = repo.get_item_count()
        print(f"  {existing} items in database")

    # Seed prices if provided
    prices_seed = getattr(args, 'prices_seed', None)
    if prices_seed:
        prices_path = Path(prices_seed)
        if prices_path.exists():
            print(f"Seeding prices from: {prices_path}")
            count = seed_prices(repo, prices_path)
            print(f"  Loaded {count} prices")
        else:
            print(f"  Warning: Price seed file not found: {prices_path}")
    else:
        existing = repo.get_price_count()
        print(f"  {existing} prices in database")

    db.close()
    print("Done.")
    return 0


def seed_items(repo: Repository, seed_file: Path) -> int:
    """Load items from seed file into database."""
    with open(seed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    items_data = data.get("items", [])
    items = []

    for item_data in items_data:
        item = Item(
            config_base_id=int(item_data["id"]),
            name_en=item_data.get("name_en"),
            name_cn=item_data.get("name_cn"),
            type_cn=item_data.get("type_cn"),
            icon_url=item_data.get("img"),
            url_en=item_data.get("url_en"),
            url_cn=item_data.get("url_cn"),
        )
        items.append(item)

    repo.upsert_items_batch(items)
    return len(items)


def seed_prices(repo: Repository, seed_file: Path) -> int:
    """Load prices from seed file into database."""
    with open(seed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    prices_data = data.get("prices", [])
    prices = []

    for price_data in prices_data:
        price = Price(
            config_base_id=int(price_data["id"]),
            price_fe=float(price_data["price_fe"]),
            source=price_data.get("source", "seed"),
            updated_at=datetime.now(),
        )
        prices.append(price)

    repo.upsert_prices_batch(prices)
    return len(prices)


def cmd_parse_file(args: argparse.Namespace) -> int:
    """Parse a log file (non-blocking)."""
    settings = Settings.from_args(
        log_path=args.file,
        db_path=args.db,
        portable=args.portable,
    )

    if not settings.log_path:
        print("Error: No log file specified and auto-detect failed")
        return 1

    if not settings.log_path.exists():
        print(f"Error: Log file not found: {settings.log_path}")
        return 1

    print(f"Parsing: {settings.log_path}")
    print(f"Database: {settings.db_path}")

    # Parse player info from enter log
    player_info = parse_enter_log(get_enter_log_path(settings.log_path))
    if player_info:
        print(f"Player: {player_info.name} ({player_info.season_name})")
    else:
        print("Warning: Could not detect player info")

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)
    collector = Collector(
        db=db,
        log_path=settings.log_path,
        on_delta=lambda d: print_delta(d, repo),
        on_run_start=print_run_start,
        on_run_end=lambda r: print_run_end(r, repo),
        player_info=player_info,
    )
    collector.initialize()

    from_beginning = args.from_beginning if hasattr(args, "from_beginning") else True
    line_count = collector.process_file(from_beginning=from_beginning)

    print(f"\nProcessed {line_count} lines")

    db.close()
    return 0


def cmd_tail(args: argparse.Namespace) -> int:
    """Live tail log file with delta output."""
    settings = Settings.from_args(
        log_path=args.file,
        db_path=args.db,
        portable=args.portable,
    )

    if not settings.log_path:
        print("Error: No log file specified and auto-detect failed")
        detected = find_log_file()
        if detected:
            print(f"  Detected: {detected}")
        return 1

    if not settings.log_path.exists():
        print(f"Error: Log file not found: {settings.log_path}")
        return 1

    print(f"Tailing: {settings.log_path}")
    print(f"Database: {settings.db_path}")

    # Parse player info from enter log
    player_info = parse_enter_log(get_enter_log_path(settings.log_path))
    if player_info:
        print(f"Player: {player_info.name} ({player_info.season_name})")
    else:
        print("Warning: Could not detect player info")

    print("Press Ctrl+C to stop\n")

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)
    collector = Collector(
        db=db,
        log_path=settings.log_path,
        on_delta=lambda d: print_delta(d, repo),
        on_run_start=print_run_start,
        on_run_end=lambda r: print_run_end(r, repo),
        player_info=player_info,
    )
    collector.initialize()

    def signal_handler(sig, frame):
        print("\nStopping...")
        collector.stop()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        collector.tail(poll_interval=settings.poll_interval)
    except KeyboardInterrupt:
        pass

    db.close()
    return 0


def cmd_show_state(args: argparse.Namespace) -> int:
    """Display current inventory state."""
    settings = Settings.from_args(
        db_path=args.db,
        portable=args.portable,
    )

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)
    states = repo.get_all_slot_states()

    if not states:
        print("No inventory state recorded")
        db.close()
        return 0

    # Aggregate by item
    totals: dict[int, int] = {}
    for state in states:
        if state.num > 0:
            totals[state.config_base_id] = totals.get(state.config_base_id, 0) + state.num

    print("Current Inventory:")
    print("-" * 40)

    # Sort by quantity descending
    for config_id, total in sorted(totals.items(), key=lambda x: -x[1]):
        name = repo.get_item_name(config_id)
        fe_marker = " (FE)" if config_id == FE_CONFIG_BASE_ID else ""
        print(f"  {total:>8} {name}{fe_marker}")

    print("-" * 40)
    print(f"Total item types: {len(totals)}")

    db.close()
    return 0


def cmd_show_runs(args: argparse.Namespace) -> int:
    """List recent runs."""
    settings = Settings.from_args(
        db_path=args.db,
        portable=args.portable,
    )

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)
    runs = repo.get_recent_runs(limit=args.limit)

    if not runs:
        print("No runs recorded")
        db.close()
        return 0

    print(f"Recent Runs (last {len(runs)}):")
    print("-" * 60)

    for run in runs:
        # Format duration
        if run.duration_seconds:
            minutes = int(run.duration_seconds // 60)
            seconds = int(run.duration_seconds % 60)
            duration_str = f"{minutes}m {seconds}s"
        else:
            duration_str = "active"

        # Get FE for run
        summary = repo.get_run_summary(run.id)
        fe_gained = summary.get(FE_CONFIG_BASE_ID, 0)

        hub_str = "[hub] " if run.is_hub else ""
        zone_name = get_zone_display_name(run.zone_signature, run.level_id)
        print(
            f"  #{run.id:3} {hub_str}{zone_name[:30]:<30} "
            f"{duration_str:>10} FE: {fe_gained:+d}"
        )

    print("-" * 60)

    db.close()
    return 0


def _check_instance_status(host: str, port: int) -> tuple[bool, bool]:
    """Check if port is available and if TITrack is running on it.

    Returns:
        (port_available, is_titrack) - port_available=True means we can start,
        is_titrack=True means an existing TITrack instance is using the port.
    """
    import socket
    import urllib.request
    import urllib.error

    # First check if port is in use
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
        return (True, False)  # Port available, no TITrack
    except OSError:
        pass  # Port in use, check if it's TITrack

    # Port is in use - check if it's TITrack by hitting the status endpoint
    try:
        url = f"http://{host}:{port}/api/status"
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                data = response.read().decode('utf-8')
                if 'titrack' in data.lower() or 'collector' in data.lower():
                    return (False, True)  # Port in use by TITrack
    except Exception:
        pass  # Request failed, not TITrack or not responding

    return (False, False)  # Port in use by something else


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the web server with optional background collector."""
    from titrack.config.paths import is_frozen
    from titrack.version import __version__

    # Check for existing instance BEFORE starting any services
    # This prevents duplicate collectors from processing the same log events
    host = getattr(args, 'host', '127.0.0.1')
    port = getattr(args, 'port', 8000)
    port_available, is_titrack = _check_instance_status(host, port)

    if not port_available:
        if is_titrack:
            error_msg = f"TITrack is already running on port {port}.\nPlease close the existing instance first."
        else:
            error_msg = f"Port {port} is already in use by another application.\nTry running with --port <number> to use a different port."

        if is_frozen():
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, error_msg, "TITrack", 0x10)  # MB_ICONERROR
            except Exception:
                print(error_msg)
        else:
            print(f"Error: {error_msg}")
        return 1

    # Set up logging early
    portable = getattr(args, 'portable', False) or is_frozen()
    # Show console output only in dev mode or when using --no-window
    console_output = not is_frozen() or getattr(args, 'no_window', False)
    logger = setup_logging(portable=portable, console=console_output)

    logger.info(f"TITrack v{__version__} starting...")

    # Import here to avoid loading FastAPI when not needed
    try:
        import uvicorn
        from titrack.api.app import create_app
    except ImportError:
        logger.error("FastAPI and Uvicorn are required for the serve command.")
        logger.error("Install with: pip install fastapi uvicorn[standard]")
        return 1

    settings = Settings.from_args(
        log_path=args.file,
        db_path=args.db,
        portable=args.portable,
    )

    logger.info(f"Database: {settings.db_path}")

    # Check for saved log_directory setting FIRST (user's explicit choice takes priority)
    # Only fall back to auto-detection if no saved setting exists
    temp_db = Database(settings.db_path)
    temp_db.connect()
    try:
        temp_repo = Repository(temp_db)
        saved_log_dir = temp_repo.get_setting("log_directory")
    finally:
        temp_db.close()

    if saved_log_dir:
        # User has explicitly configured a log directory - use it
        from titrack.config.settings import find_log_file
        found_path = find_log_file(custom_game_dir=saved_log_dir)
        if found_path and found_path.exists():
            settings.log_path = found_path
            logger.info(f"Using saved log directory: {saved_log_dir}")
        else:
            logger.warning(f"Saved log directory not found: {saved_log_dir}")
    # If no saved setting or saved path invalid, keep auto-detected path (if any)

    # Check if we should use native window mode
    use_window = is_frozen() and not getattr(args, 'no_window', False)

    # Check for overlay-only mode
    overlay_only = getattr(args, 'overlay_only', False)
    show_overlay = getattr(args, 'overlay', False) or overlay_only

    if use_window:
        # Try window mode - it will fall back to browser mode on failure
        return _serve_with_window(args, settings, logger, show_overlay=show_overlay, overlay_only=overlay_only)
    else:
        args.browser_mode = False
        return _serve_browser_mode(args, settings, logger, show_overlay=show_overlay)


def _serve_browser_mode(args: argparse.Namespace, settings: Settings, logger, show_overlay: bool = False) -> int:
    """Run server in browser mode (original behavior)."""
    import uvicorn
    from titrack.api.app import create_app

    collector = None
    collector_thread = None
    collector_db = None
    player_info = None
    sync_manager = None
    api_db = None
    overlay_process = None

    try:
        # Start collector in background if log file is available
        if settings.log_path and settings.log_path.exists():
            logger.info(f"Log file: {settings.log_path}")

            # Try to detect player from existing log (reads backwards for most recent)
            player_info = parse_game_log(settings.log_path, from_end=True)
            if player_info:
                logger.info(f"Detected character from log: {player_info.name} ({player_info.season_name})")
            else:
                logger.info("Waiting for character login...")

            # Collector gets its own database connection
            collector_db = Database(settings.db_path)
            collector_db.connect()

            collector_repo = Repository(collector_db)

            # Initialize sync manager (uses collector's DB connection)
            # Don't set season context yet - wait for player detection from live log
            sync_manager = SyncManager(collector_db)
            sync_manager.initialize()

            # Set season context from pre-seeded player info so cloud sync
            # works even if the live log detects the same player (no callback fired)
            if player_info:
                sync_manager.set_season_context(player_info.season_id)

            def on_price_update(price):
                item_name = collector_repo.get_item_name(price.config_base_id)
                logger.info(f"[Price] {item_name}: {price.price_fe:.6f} FE")

            # Placeholder for player change callback (set after app is created)
            player_change_callback = [None]  # Use list to allow closure modification

            def on_player_change(new_player_info):
                logger.info(f"[Player] Switched to: {new_player_info.name} ({new_player_info.season_name})")
                # Update app state if callback is set
                if player_change_callback[0]:
                    player_change_callback[0](new_player_info)

            collector = Collector(
                db=collector_db,
                log_path=settings.log_path,
                on_delta=lambda d: None,  # Silent operation
                on_run_start=lambda r: None,
                on_run_end=lambda r: None,
                on_price_update=on_price_update,
                on_player_change=on_player_change,
                player_info=player_info,
                sync_manager=sync_manager,
            )
            collector.initialize()

            def run_collector():
                try:
                    collector.tail(poll_interval=settings.poll_interval)
                except Exception as e:
                    logger.error(f"Collector error: {e}")

            collector_thread = threading.Thread(target=run_collector, daemon=True)
            # Don't start yet - wait until callback is wired up
        else:
            logger.warning("No log file found - collector not started")
            if settings.log_path:
                logger.warning(f"Expected: {settings.log_path}")

        # API gets its own database connection
        api_db = Database(settings.db_path)
        api_db.connect()

        # Create FastAPI app
        app = create_app(
            db=api_db,
            log_path=settings.log_path,
            collector_running=collector is not None,
            collector=collector,
            player_info=player_info,
            sync_manager=sync_manager,
            browser_mode=getattr(args, 'browser_mode', False),
        )

        # Set up player change callback to update app state
        if collector is not None:
            def update_app_player(new_player_info):
                app.state.player_info = new_player_info
                # Also update the API repository context with effective player_id
                if hasattr(app.state, 'repo'):
                    effective_id = get_effective_player_id(new_player_info)
                    app.state.repo.set_player_context(
                        new_player_info.season_id,
                        effective_id
                    )
                # Update sync manager season context
                if hasattr(app.state, 'sync_manager') and app.state.sync_manager:
                    app.state.sync_manager.set_season_context(new_player_info.season_id)
            player_change_callback[0] = update_app_player

            # Start collector AFTER callback is wired up to avoid race condition
            collector_thread.start()
            logger.info("Collector started in background")

        # Set up graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutting down...")
            if collector:
                collector.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # Open browser unless disabled
        url = f"http://127.0.0.1:{args.port}"
        if not args.no_browser:
            logger.info(f"Opening browser at {url}")
            webbrowser.open(url)

        # Launch overlay if requested
        if show_overlay:
            overlay_process = _launch_overlay_process(url, logger)

        logger.info(f"Starting server on port {args.port}")

        # Run server (log_config=None to avoid frozen mode logging issues)
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="warning",
            log_config=None,
        )
    finally:
        # Clean up overlay subprocess
        if overlay_process is not None and overlay_process.poll() is None:
            logger.info("Terminating overlay subprocess...")
            overlay_process.terminate()
            try:
                overlay_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                overlay_process.kill()
        # Ensure proper cleanup of all resources
        if sync_manager:
            try:
                sync_manager.stop_background_sync()
            except Exception as e:
                logger.error(f"Error stopping sync manager: {e}")
        if collector:
            try:
                collector.stop()
            except Exception as e:
                logger.error(f"Error stopping collector: {e}")
        if collector_db:
            try:
                collector_db.close()
            except Exception as e:
                logger.error(f"Error closing collector DB: {e}")
        if api_db:
            try:
                api_db.close()
            except Exception as e:
                logger.error(f"Error closing API DB: {e}")

    return 0


# Chroma key color for transparent overlay
# Used by CSS, WinForms TransparencyKey, and pywebview background_color
# Options: green (#00ff00) or magenta (#ff00ff) - magenta may work better with WebView2
# CHROMA_KEY_COLOR_RGB = (0, 255, 0)  # RGB tuple for green (#00ff00)
CHROMA_KEY_COLOR_RGB = (255, 0, 255)  # RGB tuple for magenta (#ff00ff) - try if green fails
CHROMA_KEY_COLOR_HEX = "#{:02x}{:02x}{:02x}".format(*CHROMA_KEY_COLOR_RGB)


def _find_webview2_control(root):
    """Recursively find Microsoft.Web.WebView2.WinForms.WebView2 control in a form."""
    try:
        type_name = root.GetType().FullName
        if "WebView2" in type_name:
            return root
    except Exception:
        pass

    try:
        for child in root.Controls:
            found = _find_webview2_control(child)
            if found is not None:
                return found
    except Exception:
        pass

    return None


def _get_winforms_form(window, logger=None):
    """Get the WinForms Form from a pywebview window.

    Tries multiple approaches since pywebview's internal structure varies.
    """
    def log(msg):
        if logger:
            logger.info(msg)

    # Try window.native (pywebview 5.x+)
    form = getattr(window, 'native', None)
    if form is not None:
        log("Found form via window.native")
        return form

    # Try window.gui.BrowserForm (older pywebview)
    gui = getattr(window, 'gui', None)
    if gui is not None:
        form = getattr(gui, 'BrowserForm', None)
        if form is not None:
            log("Found form via window.gui.BrowserForm")
            return form
        form = getattr(gui, 'form', None)
        if form is not None:
            log("Found form via window.gui.form")
            return form

    log("Could not find WinForms form")
    return None


def _remove_chroma_key(window, logger=None) -> bool:
    """Remove chroma key transparency from a pywebview window on Windows.

    Resets the TransparencyKey to disable color keying.
    """
    def log(msg):
        if logger:
            logger.info(msg)
        else:
            print(msg)

    try:
        form = _get_winforms_form(window, logger)
        if form is None:
            log("Remove chroma key: Could not get WinForms form")
            return False

        try:
            from System.Drawing import Color
            from System import Action
        except ImportError as e:
            log(f"Remove chroma key: Could not import .NET types: {e}")
            return False

        # Marshal to UI thread using Invoke
        # Default dark background color for opaque mode
        default_bg = Color.FromArgb(255, 26, 26, 46)  # #1a1a2e from overlay.css

        def do_remove():
            # Reset both BackColor and TransparencyKey
            form.BackColor = default_bg
            form.TransparencyKey = Color.Empty

        if form.InvokeRequired:
            form.Invoke(Action(do_remove))
        else:
            do_remove()

        log("Remove chroma key: Reset BackColor and TransparencyKey")
        return True

    except Exception as e:
        log(f"Remove chroma key: Exception - {e}")
        import traceback
        traceback.print_exc()
        return False


def _apply_chroma_key(window, logger=None) -> bool:
    """Apply chroma key (color key) transparency to a pywebview window on Windows.

    This makes the green color (#00ff00) fully transparent while preserving
    mouse input on non-transparent areas.

    Uses WinForms TransparencyKey combined with WebView2.DefaultBackgroundColor
    to achieve true transparency with the EdgeChromium backend.
    """
    def log(msg):
        if logger:
            logger.info(msg)
        else:
            print(msg)

    try:
        form = _get_winforms_form(window, logger)
        if form is None:
            log("Chroma key: Could not get WinForms form")
            return False

        # Import .NET types via pythonnet
        try:
            from System.Drawing import Color
            from System import Action
        except ImportError as e:
            log(f"Chroma key: Could not import .NET types: {e}")
            return False

        # Create the chroma key color (green #00ff00)
        r, g, b = CHROMA_KEY_COLOR_RGB
        key_color = Color.FromArgb(255, r, g, b)

        # Marshal to UI thread using Invoke
        def do_apply():
            # Set both BackColor and TransparencyKey for proper chroma key transparency
            # BackColor ensures the form paints the key color where WebView2 doesn't render
            # TransparencyKey tells Windows to make that color transparent
            form.BackColor = key_color
            form.TransparencyKey = key_color

        if form.InvokeRequired:
            log("Chroma key: Marshaling to UI thread via Invoke")
            form.Invoke(Action(do_apply))
        else:
            do_apply()

        log(f"Chroma key: Set form.BackColor and TransparencyKey to ({r}, {g}, {b})")
        return True

    except Exception as e:
        log(f"Chroma key: Exception - {e}")
        import traceback
        traceback.print_exc()
        return False


def _find_overlay_executable() -> Optional[Path]:
    """Find the TITrackOverlay.exe relative to the main executable."""
    from titrack.config.paths import is_frozen

    if is_frozen():
        # When packaged, look beside the main exe or in overlay subfolder
        import sys
        exe_dir = Path(sys.executable).parent
        candidates = [
            exe_dir / "TITrackOverlay.exe",
            exe_dir / "overlay" / "TITrackOverlay.exe",
        ]
    else:
        # Development mode - look in the overlay/publish folder
        project_root = Path(__file__).parent.parent.parent.parent
        candidates = [
            project_root / "overlay" / "publish" / "TITrackOverlay.exe",
            project_root / "overlay" / "bin" / "Release" / "net8.0-windows" / "win-x64" / "TITrackOverlay.exe",
        ]

    for path in candidates:
        if path.exists():
            return path

    return None


def _launch_overlay_process(url: str, logger) -> Optional[subprocess.Popen]:
    """Launch the WPF overlay as a subprocess.

    Returns the subprocess.Popen object if successful, None otherwise.
    """
    overlay_exe = _find_overlay_executable()

    if overlay_exe is None:
        logger.warning("TITrackOverlay.exe not found - overlay unavailable")
        return None

    try:
        logger.info(f"Launching overlay: {overlay_exe}")
        # Pass the API URL so the overlay knows where to connect
        process = subprocess.Popen(
            [str(overlay_exe), f"--url={url}"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        logger.info(f"Overlay launched (PID: {process.pid})")
        return process
    except Exception as e:
        logger.error(f"Failed to launch overlay: {e}")
        return None


def _serve_with_window(args: argparse.Namespace, settings: Settings, logger, show_overlay: bool = False, overlay_only: bool = False) -> int:
    """Run server with native window using pywebview."""
    # Test pywebview/pythonnet availability early, before starting any resources
    try:
        import webview
        # Try to initialize the CLR/pythonnet which pywebview uses on Windows
        # This triggers the "Failed to resolve Python.Runtime.Loader.Initialize" error
        # if .NET components are missing, before we start any other resources
        try:
            import clr_loader
            clr_loader.get_coreclr()
        except Exception:
            # clr_loader not available or failed - try direct pythonnet
            try:
                import clr
            except Exception:
                pass  # If both fail, webview.start() will give a clearer error
    except ImportError as e:
        logger.warning(f"pywebview not available: {e}")
        logger.warning("Falling back to browser mode...")
        logger.info("Tip: Install .NET Desktop Runtime or Visual C++ Redistributable for native window mode")
        args.no_browser = False
        args.browser_mode = True  # Flag for UI to show Exit button
        return _serve_browser_mode(args, settings, logger)

    import uvicorn
    from titrack.api.app import create_app

    collector = None
    collector_thread = None
    collector_db = None
    player_info = None
    sync_manager = None
    api_db = None
    server_thread = None
    shutdown_event = threading.Event()

    def cleanup():
        """Clean up all resources."""
        logger.info("Cleaning up resources...")
        shutdown_event.set()

        if sync_manager:
            try:
                sync_manager.stop_background_sync()
            except Exception as e:
                logger.error(f"Error stopping sync manager: {e}")
        if collector:
            try:
                collector.stop()
            except Exception as e:
                logger.error(f"Error stopping collector: {e}")
        if collector_db:
            try:
                collector_db.close()
            except Exception as e:
                logger.error(f"Error closing collector DB: {e}")
        if api_db:
            try:
                api_db.close()
            except Exception as e:
                logger.error(f"Error closing API DB: {e}")

    try:
        # Start collector in background if log file is available
        if settings.log_path and settings.log_path.exists():
            logger.info(f"Log file: {settings.log_path}")

            # Try to detect player from existing log (reads backwards for most recent)
            player_info = parse_game_log(settings.log_path, from_end=True)
            if player_info:
                logger.info(f"Detected character from log: {player_info.name} ({player_info.season_name})")
            else:
                logger.info("Waiting for character login...")

            collector_db = Database(settings.db_path)
            collector_db.connect()

            collector_repo = Repository(collector_db)

            sync_manager = SyncManager(collector_db)
            sync_manager.initialize()

            # Set season context from pre-seeded player info so cloud sync
            # works even if the live log detects the same player (no callback fired)
            if player_info:
                sync_manager.set_season_context(player_info.season_id)

            def on_price_update(price):
                item_name = collector_repo.get_item_name(price.config_base_id)
                logger.info(f"[Price] {item_name}: {price.price_fe:.6f} FE")

            player_change_callback = [None]

            def on_player_change(new_player_info):
                logger.info(f"[Player] Switched to: {new_player_info.name} ({new_player_info.season_name})")
                if player_change_callback[0]:
                    player_change_callback[0](new_player_info)

            collector = Collector(
                db=collector_db,
                log_path=settings.log_path,
                on_delta=lambda d: None,
                on_run_start=lambda r: None,
                on_run_end=lambda r: None,
                on_price_update=on_price_update,
                on_player_change=on_player_change,
                player_info=player_info,
                sync_manager=sync_manager,
            )
            collector.initialize()

            def run_collector():
                try:
                    collector.tail(poll_interval=settings.poll_interval)
                except Exception as e:
                    logger.error(f"Collector error: {e}")

            collector_thread = threading.Thread(target=run_collector, daemon=True)
            # Don't start yet - wait until callback is wired up
        else:
            logger.warning("No log file found - collector not started")
            if settings.log_path:
                logger.warning(f"Expected: {settings.log_path}")

        # API gets its own database connection
        api_db = Database(settings.db_path)
        api_db.connect()

        # Create FastAPI app (window mode, not browser fallback)
        app = create_app(
            db=api_db,
            log_path=settings.log_path,
            collector_running=collector is not None,
            collector=collector,
            player_info=player_info,
            sync_manager=sync_manager,
            browser_mode=False,
        )

        # Set up player change callback
        if collector is not None:
            def update_app_player(new_player_info):
                app.state.player_info = new_player_info
                if hasattr(app.state, 'repo'):
                    effective_id = get_effective_player_id(new_player_info)
                    app.state.repo.set_player_context(
                        new_player_info.season_id,
                        effective_id
                    )
                if hasattr(app.state, 'sync_manager') and app.state.sync_manager:
                    app.state.sync_manager.set_season_context(new_player_info.season_id)
            player_change_callback[0] = update_app_player

            # Start collector AFTER callback is wired up to avoid race condition
            collector_thread.start()
            logger.info("Collector started in background")

        # Start uvicorn in a background thread
        url = f"http://127.0.0.1:{args.port}"

        class Server(uvicorn.Server):
            def install_signal_handlers(self):
                # Don't install signal handlers - we handle shutdown via window close
                pass

        config = uvicorn.Config(
            app,
            host=args.host,
            port=args.port,
            log_level="warning",
            log_config=None,  # Disable uvicorn's logging config for frozen mode
        )
        server = Server(config)

        def run_server():
            try:
                server.run()
            except Exception as e:
                logger.error(f"Server error: {e}")

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # Wait for server to be ready before opening the window
        import time
        for _ in range(100):  # Up to 10 seconds
            if server.started or server.should_exit:
                break
            time.sleep(0.1)

        if not server.started:
            logger.warning("Server did not start within 10 seconds")

        logger.info(f"Server started on port {args.port}")

        # Create and run the native window
        def on_closing():
            logger.info("Window closed, initiating shutdown...")
            # Close overlay subprocess if running
            if overlay_ref[0] is not None:
                process = overlay_ref[0]
                if process.poll() is None:  # Still running
                    logger.info("Terminating overlay subprocess...")
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                overlay_ref[0] = None
            server.should_exit = True
            cleanup()

        # JavaScript API for native dialogs
        class Api:
            def __init__(self, window_ref, overlay_ref):
                self._window = window_ref
                self._overlay = overlay_ref

            def browse_folder(self):
                """Open a folder browser dialog and return the selected path."""
                try:
                    result = self._window[0].create_file_dialog(
                        webview.FOLDER_DIALOG,
                        directory='',
                        allow_multiple=False
                    )
                    if result and len(result) > 0:
                        return result[0]
                    return None
                except Exception as e:
                    logger.error(f"Browse dialog error: {e}")
                    return None

            def browse_file(self):
                """Open a file browser dialog for log files."""
                try:
                    result = self._window[0].create_file_dialog(
                        webview.OPEN_DIALOG,
                        directory='',
                        allow_multiple=False,
                        file_types=('Log files (*.log)', 'All files (*.*)')
                    )
                    if result and len(result) > 0:
                        return result[0]
                    return None
                except Exception as e:
                    logger.error(f"Browse dialog error: {e}")
                    return None

            def launch_overlay(self):
                """Launch the WPF overlay as a subprocess."""
                try:
                    # Check if overlay process is already running
                    if self._overlay[0] is not None:
                        # Check if process is still alive
                        if self._overlay[0].poll() is None:
                            logger.info("Overlay already running")
                            return True
                        else:
                            # Process ended, clear the reference
                            self._overlay[0] = None

                    # Launch the WPF overlay
                    process = _launch_overlay_process(url, logger)
                    if process is not None:
                        self._overlay[0] = process
                        return True
                    return False
                except Exception as e:
                    logger.error(f"Error launching overlay: {e}")
                    return False

            def close_overlay(self):
                """Close the overlay subprocess."""
                try:
                    if self._overlay[0] is not None:
                        process = self._overlay[0]
                        if process.poll() is None:  # Still running
                            process.terminate()
                            try:
                                process.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                process.kill()
                        self._overlay[0] = None
                        logger.info("Overlay closed")
                        return True
                    return False
                except Exception as e:
                    logger.error(f"Error closing overlay: {e}")
                    return False

        # Use lists to allow the API to reference windows after creation
        window_ref = [None]
        overlay_ref = [None]
        api = Api(window_ref, overlay_ref)

        logger.info("Opening native window...")
        try:
            # Create main window unless overlay-only mode
            if not overlay_only:
                window = webview.create_window(
                    "TITrack - Torchlight Infinite Loot Tracker",
                    url,
                    width=1280,
                    height=800,
                    min_size=(800, 600),
                    js_api=api,
                )
                window_ref[0] = window
                window.events.closing += on_closing

            # Launch WPF overlay subprocess if requested
            if show_overlay:
                overlay_process = _launch_overlay_process(url, logger)
                overlay_ref[0] = overlay_process

            # If overlay-only mode, wait for overlay to exit instead of starting pywebview
            if overlay_only:
                if overlay_ref[0] is not None:
                    logger.info("Running in overlay-only mode. Waiting for overlay to close...")
                    try:
                        overlay_ref[0].wait()
                    except KeyboardInterrupt:
                        if overlay_ref[0].poll() is None:
                            overlay_ref[0].terminate()
                    logger.info("Overlay closed, shutting down...")
                    on_closing()
                else:
                    logger.error("Overlay failed to launch - no window to display")
                    on_closing()
                    return 1
            else:
                # This blocks until main window is closed
                # Force EdgeChromium (WebView2) to prevent silent fallback to
                # MSHTML (IE11) which can't render modern CSS/JS properly.
                # If WebView2 is unavailable, this raises an exception caught
                # below, triggering a browser mode fallback instead.
                webview.start(gui='edgechromium')

            logger.info("Application shutdown complete")
            return 0
        except Exception as webview_error:
            # pywebview/EdgeChromium failed - fall back to browser mode
            # Common causes: WebView2 runtime not installed, MOTW blocking DLLs,
            # or .NET components missing. Browser mode works identically.
            logger.warning(f"Native window failed (WebView2/EdgeChromium): {webview_error}")
            logger.info("Falling back to browser mode...")

            # Show a message box pointing users to the WebView2 download
            if is_frozen():
                try:
                    import ctypes
                    msg = (
                        "Native window mode requires the Microsoft Edge WebView2 Runtime.\n\n"
                        "TITrack will open in your browser instead (works identically).\n\n"
                        "To use native window mode, install WebView2 from:\n"
                        "https://developer.microsoft.com/en-us/microsoft-edge/webview2/"
                    )
                    ctypes.windll.user32.MessageBoxW(0, msg, "TITrack", 0x40)  # MB_ICONINFORMATION
                except Exception:
                    pass

            # Enable browser mode in app so UI shows Exit button
            app.state.browser_mode = True

            # Open browser since window mode failed
            import webbrowser
            webbrowser.open(url)

            # Keep server running until shutdown is triggered (via UI Exit button or interrupt)
            logger.info("Running in browser mode. Use Exit button in UI to close.")
            try:
                shutdown_event.wait()
            except KeyboardInterrupt:
                pass

            server.should_exit = True
            cleanup()
            return 0

    except Exception as e:
        logger.error(f"Error in window mode: {e}")
        cleanup()
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="titrack",
        description="Torchlight Infinite Local Loot Tracker",
    )
    parser.add_argument(
        "--db",
        type=str,
        help="Database file path",
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Use portable mode (data beside exe)",
    )
    # Top-level flags for frozen exe mode (no subcommand needed)
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="Open mini-overlay window alongside main window",
    )
    parser.add_argument(
        "--overlay-only",
        action="store_true",
        help="Open only the mini-overlay window (no main dashboard)",
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="Run in browser mode instead of native window",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.add_argument(
        "--seed",
        type=str,
        help="Path to item seed JSON file",
    )
    init_parser.add_argument(
        "--prices-seed",
        type=str,
        help="Path to price seed JSON file",
    )

    # parse-file command
    parse_parser = subparsers.add_parser("parse-file", help="Parse a log file")
    parse_parser.add_argument(
        "file",
        type=str,
        nargs="?",
        help="Log file to parse (auto-detects if not specified)",
    )
    parse_parser.add_argument(
        "--from-beginning",
        action="store_true",
        default=True,
        help="Parse from beginning (default)",
    )
    parse_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last position",
    )

    # tail command
    tail_parser = subparsers.add_parser("tail", help="Live tail log file")
    tail_parser.add_argument(
        "file",
        type=str,
        nargs="?",
        help="Log file to tail (auto-detects if not specified)",
    )

    # show-state command
    subparsers.add_parser("show-state", help="Display current inventory")

    # show-runs command
    runs_parser = subparsers.add_parser("show-runs", help="List recent runs")
    runs_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of runs to show (default: 20)",
    )

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start web server")
    serve_parser.add_argument(
        "file",
        type=str,
        nargs="?",
        help="Log file to monitor (auto-detects if not specified)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run server on (default: 8000)",
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )
    serve_parser.add_argument(
        "--no-window",
        action="store_true",
        help="Run in browser mode instead of native window (useful for debugging)",
    )
    serve_parser.add_argument(
        "--overlay",
        action="store_true",
        help="Open mini-overlay window alongside main window",
    )
    serve_parser.add_argument(
        "--overlay-only",
        action="store_true",
        help="Open only the mini-overlay window (no main dashboard)",
    )

    return parser


def main() -> int:
    """Main entry point."""
    from titrack.config.paths import is_frozen
    from titrack.version import __version__

    parser = create_parser()
    args = parser.parse_args()

    # Default to serve mode when running as frozen exe with no command
    if args.command is None:
        if is_frozen():
            # Running as packaged EXE - default to serve with portable mode and native window
            args.command = "serve"
            args.file = None
            args.port = getattr(args, 'port', 8000) or 8000
            args.host = getattr(args, 'host', '127.0.0.1') or '127.0.0.1'
            args.no_browser = True  # Window mode handles its own display
            args.no_window = getattr(args, 'no_window', False)
            args.portable = True  # Force portable mode for frozen exe
            # Preserve --overlay and --overlay-only flags from command line
            args.overlay = getattr(args, 'overlay', False)
            args.overlay_only = getattr(args, 'overlay_only', False)
        else:
            parser.print_help()
            return 0

    commands = {
        "init": cmd_init,
        "parse-file": cmd_parse_file,
        "tail": cmd_tail,
        "show-state": cmd_show_state,
        "show-runs": cmd_show_runs,
        "serve": cmd_serve,
    }

    cmd_func = commands.get(args.command)
    if cmd_func is None:
        print(f"Unknown command: {args.command}")
        return 1

    return cmd_func(args)


if __name__ == "__main__":
    sys.exit(main())
