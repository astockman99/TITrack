"""Update API routes for auto-update functionality."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/update", tags=["update"])


class UpdateStatusResponse(BaseModel):
    """Update status response."""

    status: str  # idle, checking, available, downloading, ready, installing, error, up_to_date
    current_version: str
    latest_version: Optional[str] = None
    release_notes: Optional[str] = None
    release_url: Optional[str] = None
    download_url: Optional[str] = None
    download_size: Optional[int] = None
    download_progress: int = 0
    error_message: Optional[str] = None
    checked_at: Optional[datetime] = None
    can_update: bool = False
    install_path_warning: Optional[str] = None


class ActionResponse(BaseModel):
    """Generic action response."""

    success: bool
    message: str


def _get_update_manager(request: Request):
    """Get update manager from app state."""
    manager = getattr(request.app.state, "update_manager", None)
    if not manager:
        raise HTTPException(status_code=503, detail="Update manager not available")
    return manager


@router.get("/status", response_model=UpdateStatusResponse)
def get_update_status(request: Request) -> UpdateStatusResponse:
    """Get current update status and version information."""
    from titrack.config.paths import get_install_path_warning

    try:
        manager = _get_update_manager(request)
        info = manager.get_status()

        return UpdateStatusResponse(
            status=info.status.value,
            current_version=info.current_version,
            latest_version=info.latest_version,
            release_notes=info.release_notes,
            release_url=info.release_url,
            download_url=info.download_url,
            download_size=info.download_size,
            download_progress=info.download_progress,
            error_message=info.error_message,
            checked_at=info.checked_at,
            can_update=manager.can_update,
            install_path_warning=get_install_path_warning(),
        )
    except HTTPException:
        # If manager not available, return basic version info
        from titrack.version import __version__
        from titrack.config.paths import is_frozen

        return UpdateStatusResponse(
            status="idle",
            current_version=__version__,
            can_update=is_frozen(),
            install_path_warning=get_install_path_warning(),
        )


@router.post("/check", response_model=ActionResponse)
def check_for_updates(request: Request) -> ActionResponse:
    """Trigger an asynchronous check for updates."""
    manager = _get_update_manager(request)

    manager.check_for_updates(async_check=True)

    return ActionResponse(
        success=True,
        message="Update check started",
    )


@router.post("/download", response_model=ActionResponse)
def download_update(request: Request) -> ActionResponse:
    """Start downloading an available update."""
    manager = _get_update_manager(request)

    info = manager.get_status()
    if info.status.value != "available":
        return ActionResponse(
            success=False,
            message=f"Cannot download: status is {info.status.value}",
        )

    started = manager.download_update(async_download=True)

    if started:
        return ActionResponse(
            success=True,
            message="Download started",
        )
    else:
        return ActionResponse(
            success=False,
            message="Failed to start download",
        )


@router.post("/install", response_model=ActionResponse)
def install_update(request: Request) -> ActionResponse:
    """
    Install the downloaded update and restart.

    WARNING: This will cause the application to exit and restart!
    """
    manager = _get_update_manager(request)

    info = manager.get_status()
    if info.status.value != "ready":
        return ActionResponse(
            success=False,
            message=f"Cannot install: status is {info.status.value}",
        )

    if not manager.can_update:
        return ActionResponse(
            success=False,
            message="Updates not available in development mode",
        )

    # This will exit the application on success
    result = manager.install_update()

    # If we get here, installation failed
    return ActionResponse(
        success=False,
        message=info.error_message or "Installation failed",
    )


@router.post("/cancel", response_model=ActionResponse)
def cancel_update(request: Request) -> ActionResponse:
    """Cancel any ongoing update operation."""
    manager = _get_update_manager(request)

    manager.cancel()

    return ActionResponse(
        success=True,
        message="Update cancelled",
    )
