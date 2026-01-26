"""FastAPI application factory."""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from titrack.api.routes import inventory, items, prices, runs, stats
from titrack.api.schemas import StatusResponse
from titrack.db.connection import Database
from titrack.db.repository import Repository


def create_app(
    db: Database,
    log_path: Optional[Path] = None,
    collector_running: bool = False,
    collector: Optional[object] = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        db: Database connection
        log_path: Path to log file being monitored
        collector_running: Whether the collector is actively running

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="TITrack API",
        description="Torchlight Infinite Local Loot Tracker API",
        version="0.2.0",
    )

    # CORS middleware for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create repository
    repo = Repository(db)

    # Dependency override for repository injection
    def get_repository() -> Repository:
        return repo

    # Apply dependency overrides to all routers
    app.dependency_overrides[runs.get_repository] = get_repository
    app.dependency_overrides[inventory.get_repository] = get_repository
    app.dependency_overrides[items.get_repository] = get_repository
    app.dependency_overrides[prices.get_repository] = get_repository
    app.dependency_overrides[stats.get_repository] = get_repository

    # Include routers
    app.include_router(runs.router)
    app.include_router(inventory.router)
    app.include_router(items.router)
    app.include_router(prices.router)
    app.include_router(stats.router)

    # Store state for status endpoint and reset functionality
    app.state.db = db
    app.state.log_path = log_path
    app.state.collector_running = collector_running
    app.state.collector = collector
    app.state.repo = repo

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
        )

    # Mount static files (must be last to not override API routes)
    static_dir = Path(__file__).parent.parent / "web" / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
