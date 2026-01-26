"""CLI commands for testing and manual operation."""

import argparse
import json
import signal
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

from titrack.collector.collector import Collector
from titrack.config.settings import Settings, find_log_file
from titrack.core.models import Item, ItemDelta, Run
from titrack.data.zones import get_zone_display_name
from titrack.db.connection import Database
from titrack.db.repository import Repository
from titrack.parser.patterns import FE_CONFIG_BASE_ID


def print_delta(delta: ItemDelta, repo: Repository) -> None:
    """Print a delta to console."""
    item_name = repo.get_item_name(delta.config_base_id)
    sign = "+" if delta.delta > 0 else ""
    context_str = f"[{delta.context.name}]" if delta.proto_name else ""
    print(f"  {sign}{delta.delta} {item_name} {context_str}")


def print_run_start(run: Run) -> None:
    """Print run start to console."""
    hub_str = " (hub)" if run.is_hub else ""
    zone_name = get_zone_display_name(run.zone_signature)
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
    """Initialize database and optionally seed items."""
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

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)
    collector = Collector(
        db=db,
        log_path=settings.log_path,
        on_delta=lambda d: print_delta(d, repo),
        on_run_start=print_run_start,
        on_run_end=lambda r: print_run_end(r, repo),
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
        zone_name = get_zone_display_name(run.zone_signature)
        print(
            f"  #{run.id:3} {hub_str}{zone_name[:30]:<30} "
            f"{duration_str:>10} FE: {fe_gained:+d}"
        )

    print("-" * 60)

    db.close()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the web server with optional background collector."""
    # Import here to avoid loading FastAPI when not needed
    try:
        import uvicorn
        from titrack.api.app import create_app
    except ImportError:
        print("Error: FastAPI and Uvicorn are required for the serve command.")
        print("Install with: pip install fastapi uvicorn[standard]")
        return 1

    settings = Settings.from_args(
        log_path=args.file,
        db_path=args.db,
        portable=args.portable,
    )

    print(f"Database: {settings.db_path}")

    collector = None
    collector_thread = None
    collector_db = None

    # Start collector in background if log file is available
    if settings.log_path and settings.log_path.exists():
        print(f"Log file: {settings.log_path}")

        # Collector gets its own database connection
        collector_db = Database(settings.db_path)
        collector_db.connect()

        collector_repo = Repository(collector_db)

        def on_price_update(price):
            item_name = collector_repo.get_item_name(price.config_base_id)
            print(f"  [Price] {item_name}: {price.price_fe:.6f} FE")

        collector = Collector(
            db=collector_db,
            log_path=settings.log_path,
            on_delta=lambda d: None,  # Silent operation
            on_run_start=lambda r: None,
            on_run_end=lambda r: None,
            on_price_update=on_price_update,
        )
        collector.initialize()

        def run_collector():
            try:
                collector.tail(poll_interval=settings.poll_interval)
            except Exception as e:
                print(f"Collector error: {e}")

        collector_thread = threading.Thread(target=run_collector, daemon=True)
        collector_thread.start()
        print("Collector started in background")
    else:
        print("No log file found - collector not started")
        if settings.log_path:
            print(f"  Expected: {settings.log_path}")

    # API gets its own database connection
    api_db = Database(settings.db_path)
    api_db.connect()

    # Create FastAPI app
    app = create_app(
        db=api_db,
        log_path=settings.log_path,
        collector_running=collector is not None,
    )

    # Set up graceful shutdown
    def signal_handler(sig, frame):
        print("\nShutting down...")
        if collector:
            collector.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Open browser unless disabled
    url = f"http://127.0.0.1:{args.port}"
    if not args.no_browser:
        print(f"Opening browser at {url}")
        webbrowser.open(url)

    print(f"Starting server on port {args.port}")
    print("Press Ctrl+C to stop\n")

    # Run server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="warning",
    )

    if collector:
        collector.stop()
    if collector_db:
        collector_db.close()
    api_db.close()
    return 0


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

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.add_argument(
        "--seed",
        type=str,
        help="Path to item seed JSON file",
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

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
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
