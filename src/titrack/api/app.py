"""FastAPI application factory."""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from titrack.api.routes import cloud, icons, inventory, items, prices, runs, settings, stats, update
from titrack.api.schemas import PlayerResponse, StatusResponse
from titrack.config.paths import get_static_dir
from titrack.db.connection import Database
from titrack.db.repository import Repository
from titrack.parser.player_parser import get_effective_player_id, PlayerInfo
from titrack.version import __version__


def create_app(
    db: Database,
    log_path: Optional[Path] = None,
    collector_running: bool = False,
    collector: Optional[object] = None,
    player_info: Optional[PlayerInfo] = None,
    sync_manager: Optional[object] = None,
    browser_mode: bool = False,
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        db: Database connection
        log_path: Path to log file being monitored
        collector_running: Whether the collector is actively running
        player_info: Current player info for data isolation

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="TITrack API",
        description="Torchlight Infinite Local Loot Tracker API",
        version=__version__,
    )

    # CORS middleware for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create repository with player context for filtering
    repo = Repository(db)
    if player_info:
        effective_id = get_effective_player_id(player_info)
        repo.set_player_context(player_info.season_id, effective_id)

    # Dependency override for repository injection
    def get_repository() -> Repository:
        return repo

    # Apply dependency overrides to all routers
    app.dependency_overrides[runs.get_repository] = get_repository
    app.dependency_overrides[inventory.get_repository] = get_repository
    app.dependency_overrides[items.get_repository] = get_repository
    app.dependency_overrides[prices.get_repository] = get_repository
    app.dependency_overrides[stats.get_repository] = get_repository
    app.dependency_overrides[icons.get_repository] = get_repository
    app.dependency_overrides[settings.get_repository] = get_repository
    app.dependency_overrides[cloud.get_repository] = get_repository

    # Include routers
    app.include_router(runs.router)
    app.include_router(inventory.router)
    app.include_router(items.router)
    app.include_router(prices.router)
    app.include_router(stats.router)
    app.include_router(icons.router)
    app.include_router(settings.router)
    app.include_router(cloud.router)
    app.include_router(update.router)

    # Initialize update manager
    try:
        from titrack.updater.manager import UpdateManager
        update_manager = UpdateManager()
        app.state.update_manager = update_manager
    except Exception as e:
        print(f"Failed to initialize update manager: {e}")
        app.state.update_manager = None

    # Store state for status endpoint and reset functionality
    app.state.db = db
    app.state.log_path = log_path
    app.state.collector_running = collector_running
    app.state.collector = collector
    app.state.repo = repo
    app.state.player_info = player_info
    app.state.sync_manager = sync_manager
    app.state.browser_mode = browser_mode

    @app.get("/api/status", response_model=StatusResponse, tags=["status"])
    def get_status() -> StatusResponse:
        """Get server status."""
        return StatusResponse(
            status="ok",
            collector_running=app.state.collector_running,
            db_path=str(db.db_path),
            log_path=str(log_path) if log_path else None,
            log_path_missing=log_path is None,
            item_count=repo.get_item_count(),
            run_count=len(repo.get_recent_runs(limit=10000)),
            awaiting_player=app.state.player_info is None,
        )

    @app.get("/api/browser-mode", tags=["status"])
    def get_browser_mode() -> dict:
        """Check if running in browser fallback mode."""
        return {"browser_mode": app.state.browser_mode}

    @app.post("/api/shutdown", tags=["status"])
    def shutdown_app() -> dict:
        """Shutdown the application (only available in browser mode)."""
        import os
        import threading

        if not app.state.browser_mode:
            return {"success": False, "message": "Shutdown only available in browser mode"}

        def delayed_shutdown():
            import time
            time.sleep(0.5)  # Give time for response to be sent
            os._exit(0)

        threading.Thread(target=delayed_shutdown, daemon=True).start()
        return {"success": True, "message": "Shutting down..."}

    @app.get("/api/player", response_model=Optional[PlayerResponse], tags=["player"])
    def get_player() -> Optional[PlayerResponse]:
        """Get current player/character information."""
        # Only return player info if detected from live log stream
        # Do NOT fall back to parsing log file - that would show stale data
        # from previous game sessions before user logs in
        pi = app.state.player_info
        if not pi:
            return None

        return PlayerResponse(
            name=pi.name,
            level=pi.level,
            season_id=pi.season_id,
            season_name=pi.season_name,
            hero_id=pi.hero_id,
            hero_name=pi.hero_name,
            player_id=pi.player_id,
        )

    # Mount static files (must be last to not override API routes)
    # Use paths module for proper frozen/source mode resolution
    static_dir = get_static_dir()
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
