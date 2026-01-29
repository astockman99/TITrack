"""FastAPI application factory."""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from titrack.api.routes import cloud, icons, inventory, items, prices, runs, settings, stats
from titrack.api.schemas import PlayerResponse, StatusResponse
from titrack.db.connection import Database
from titrack.db.repository import Repository
from titrack.parser.player_parser import get_enter_log_path, get_effective_player_id, parse_enter_log, PlayerInfo


def create_app(
    db: Database,
    log_path: Optional[Path] = None,
    collector_running: bool = False,
    collector: Optional[object] = None,
    player_info: Optional[PlayerInfo] = None,
    sync_manager: Optional[object] = None,
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
        version="0.3.0",  # Bumped for multi-season support
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

    # Store state for status endpoint and reset functionality
    app.state.db = db
    app.state.log_path = log_path
    app.state.collector_running = collector_running
    app.state.collector = collector
    app.state.repo = repo
    app.state.player_info = player_info
    app.state.sync_manager = sync_manager

    @app.get("/api/status", response_model=StatusResponse, tags=["status"])
    def get_status() -> StatusResponse:
        """Get server status."""
        return StatusResponse(
            status="ok",
            collector_running=app.state.collector_running,
            db_path=str(db.db_path),
            log_path=str(log_path) if log_path else None,
            item_count=repo.get_item_count(),
            run_count=len(repo.get_recent_runs(limit=10000)),
            awaiting_player=app.state.player_info is None,
        )

    @app.get("/api/player", response_model=Optional[PlayerResponse], tags=["player"])
    def get_player() -> Optional[PlayerResponse]:
        """Get current player/character information."""
        # Use cached player_info if available (from startup)
        pi = app.state.player_info
        if pi:
            return PlayerResponse(
                name=pi.name,
                level=pi.level,
                season_id=pi.season_id,
                season_name=pi.season_name,
                hero_id=pi.hero_id,
                hero_name=pi.hero_name,
                player_id=pi.player_id,
            )

        # Fall back to parsing enter log
        if not log_path:
            return None

        enter_log = get_enter_log_path(log_path)
        parsed_info = parse_enter_log(enter_log)

        if not parsed_info:
            return None

        return PlayerResponse(
            name=parsed_info.name,
            level=parsed_info.level,
            season_id=parsed_info.season_id,
            season_name=parsed_info.season_name,
            hero_id=parsed_info.hero_id,
            hero_name=parsed_info.hero_name,
            player_id=parsed_info.player_id,
        )

    # Mount static files (must be last to not override API routes)
    static_dir = Path(__file__).parent.parent / "web" / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
