"""Cloud sync API routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from titrack.db.repository import Repository
from titrack.sync.manager import SyncManager, SyncStatus

router = APIRouter(prefix="/api/cloud", tags=["cloud"])


def get_repository() -> Repository:
    """Dependency injection for repository - set by app factory."""
    raise NotImplementedError("Repository not configured")


def get_sync_manager(request: Request) -> Optional[SyncManager]:
    """Get sync manager from app state."""
    return getattr(request.app.state, "sync_manager", None)


class CloudStatusResponse(BaseModel):
    """Cloud sync status information."""

    status: str
    enabled: bool
    upload_enabled: bool
    download_enabled: bool
    queue_pending: int
    queue_failed: int
    last_upload: Optional[str] = None
    last_download: Optional[str] = None
    last_error: Optional[str] = None
    cloud_available: bool


class CloudToggleRequest(BaseModel):
    """Request to enable/disable cloud sync."""

    enabled: bool


class CloudToggleResponse(BaseModel):
    """Response for toggle operation."""

    success: bool
    enabled: bool
    error: Optional[str] = None


class CloudSyncResponse(BaseModel):
    """Response for manual sync trigger."""

    success: bool
    uploaded: int = 0
    downloaded: int = 0
    error: Optional[str] = None


class CloudPriceResponse(BaseModel):
    """A single cloud price entry."""

    config_base_id: int
    season_id: int
    price_fe_median: float
    price_fe_p10: Optional[float] = None
    price_fe_p90: Optional[float] = None
    submission_count: Optional[int] = None
    unique_devices: Optional[int] = None
    cloud_updated_at: Optional[str] = None
    cached_at: Optional[str] = None


class CloudPriceListResponse(BaseModel):
    """List of cloud prices."""

    prices: list[CloudPriceResponse]
    total: int


class PriceHistoryPoint(BaseModel):
    """A single price history point."""

    hour_bucket: str
    price_fe_median: float
    price_fe_p10: Optional[float] = None
    price_fe_p90: Optional[float] = None
    submission_count: Optional[int] = None


class CloudPriceHistoryResponse(BaseModel):
    """Price history for an item."""

    config_base_id: int
    season_id: int
    history: list[PriceHistoryPoint]


@router.get("/status", response_model=CloudStatusResponse)
def get_cloud_status(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> CloudStatusResponse:
    """Get current cloud sync status."""
    sync_manager = get_sync_manager(request)

    if sync_manager is None:
        # No sync manager - return disabled status
        return CloudStatusResponse(
            status="disabled",
            enabled=False,
            upload_enabled=True,
            download_enabled=True,
            queue_pending=0,
            queue_failed=0,
            cloud_available=False,
        )

    info = sync_manager.get_status_info()

    return CloudStatusResponse(
        status=info.status.value,
        enabled=info.enabled,
        upload_enabled=info.upload_enabled,
        download_enabled=info.download_enabled,
        queue_pending=info.queue_pending,
        queue_failed=info.queue_failed,
        last_upload=info.last_upload.isoformat() if info.last_upload else None,
        last_download=info.last_download.isoformat() if info.last_download else None,
        last_error=info.last_error,
        cloud_available=info.cloud_available,
    )


@router.post("/toggle", response_model=CloudToggleResponse)
def toggle_cloud_sync(
    request_body: CloudToggleRequest,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> CloudToggleResponse:
    """Enable or disable cloud sync."""
    sync_manager = get_sync_manager(request)

    if sync_manager is None:
        return CloudToggleResponse(
            success=False,
            enabled=False,
            error="Cloud sync not available",
        )

    if request_body.enabled:
        success = sync_manager.enable()
        if not success:
            return CloudToggleResponse(
                success=False,
                enabled=False,
                error=sync_manager.get_status_info().last_error or "Failed to enable",
            )
        return CloudToggleResponse(success=True, enabled=True)
    else:
        sync_manager.disable()
        return CloudToggleResponse(success=True, enabled=False)


@router.post("/sync", response_model=CloudSyncResponse)
def trigger_sync(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> CloudSyncResponse:
    """Trigger an immediate sync."""
    sync_manager = get_sync_manager(request)

    if sync_manager is None:
        return CloudSyncResponse(success=False, error="Cloud sync not available")

    if not sync_manager.is_enabled:
        return CloudSyncResponse(success=False, error="Cloud sync not enabled")

    result = sync_manager.trigger_sync()

    return CloudSyncResponse(
        success=result.get("success", False),
        uploaded=result.get("uploaded", 0),
        downloaded=result.get("downloaded", 0),
        error=result.get("error"),
    )


@router.get("/prices", response_model=CloudPriceListResponse)
def get_cloud_prices(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> CloudPriceListResponse:
    """Get cached cloud prices."""
    sync_manager = get_sync_manager(request)

    if sync_manager is None:
        return CloudPriceListResponse(prices=[], total=0)

    # Get season from repository context
    season_id = repo._current_season_id

    prices = sync_manager.get_cached_cloud_prices(season_id)

    return CloudPriceListResponse(
        prices=[
            CloudPriceResponse(
                config_base_id=p["config_base_id"],
                season_id=p["season_id"],
                price_fe_median=p["price_fe_median"],
                price_fe_p10=p.get("price_fe_p10"),
                price_fe_p90=p.get("price_fe_p90"),
                submission_count=p.get("submission_count"),
                unique_devices=p.get("unique_devices"),
                cloud_updated_at=p.get("cloud_updated_at"),
                cached_at=p.get("cached_at"),
            )
            for p in prices
        ],
        total=len(prices),
    )


@router.get("/prices/{config_base_id}/history", response_model=CloudPriceHistoryResponse)
def get_cloud_price_history(
    config_base_id: int,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> CloudPriceHistoryResponse:
    """Get price history for an item (for sparklines and charts)."""
    sync_manager = get_sync_manager(request)

    season_id = repo._current_season_id or 0

    if sync_manager is None:
        return CloudPriceHistoryResponse(
            config_base_id=config_base_id,
            season_id=season_id,
            history=[],
        )

    history = sync_manager.get_cached_price_history(config_base_id, season_id)

    return CloudPriceHistoryResponse(
        config_base_id=config_base_id,
        season_id=season_id,
        history=[
            PriceHistoryPoint(
                hour_bucket=h["hour_bucket"],
                price_fe_median=h["price_fe_median"],
                price_fe_p10=h.get("price_fe_p10"),
                price_fe_p90=h.get("price_fe_p90"),
                submission_count=h.get("submission_count"),
            )
            for h in history
        ],
    )
