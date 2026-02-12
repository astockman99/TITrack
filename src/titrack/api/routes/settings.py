"""Settings API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from titrack.config.settings import validate_game_directory
from titrack.db.repository import Repository

router = APIRouter(prefix="/api/settings", tags=["settings"])


def get_repository() -> Repository:
    """Dependency injection for repository - set by app factory."""
    raise NotImplementedError("Repository not configured")


# Whitelist of settings that can be read/written via API
ALLOWED_SETTINGS = {
    "cloud_sync_enabled",
    "cloud_upload_enabled",
    "cloud_download_enabled",
    "log_directory",
    "trade_tax_enabled",
    "map_costs_enabled",
    "overlay_transparent",
    "overlay_font_scale",
    "overlay_hide_loot",
    "realtime_tracking_enabled",
    "hidden_items_exclude_worth",
}

# Settings that are read-only via API (can be read but not written)
READONLY_SETTINGS = {
    "cloud_device_id",
    "cloud_last_price_sync",
    "cloud_last_history_sync",
}


class SettingResponse(BaseModel):
    """Response for a single setting."""

    key: str
    value: str | None


class SettingUpdateRequest(BaseModel):
    """Request to update a setting."""

    value: str


@router.get("/{key}", response_model=SettingResponse)
def get_setting(
    key: str,
    repo: Repository = Depends(get_repository),
) -> SettingResponse:
    """
    Get a setting value.

    Only whitelisted settings can be retrieved via API.
    """
    if key not in ALLOWED_SETTINGS and key not in READONLY_SETTINGS:
        raise HTTPException(status_code=403, detail="Setting not accessible")

    value = repo.get_setting(key)
    return SettingResponse(key=key, value=value)


@router.put("/{key}", response_model=SettingResponse)
def update_setting(
    key: str,
    request: SettingUpdateRequest,
    repo: Repository = Depends(get_repository),
) -> SettingResponse:
    """
    Update a setting value.

    Only whitelisted settings can be modified via API.
    """
    if key not in ALLOWED_SETTINGS:
        raise HTTPException(status_code=403, detail="Setting not modifiable")

    repo.set_setting(key, request.value)
    return SettingResponse(key=key, value=request.value)


class LogDirectoryValidateRequest(BaseModel):
    """Request to validate a game directory."""

    path: str


class LogDirectoryValidateResponse(BaseModel):
    """Response for log directory validation."""

    valid: bool
    log_path: str | None
    error: str | None


@router.post("/log-directory/validate", response_model=LogDirectoryValidateResponse)
def validate_log_directory(
    request: LogDirectoryValidateRequest,
) -> LogDirectoryValidateResponse:
    """
    Validate that a directory contains the game log file.

    Returns whether the path is valid and the full log file path if found.
    """
    is_valid, log_path = validate_game_directory(request.path)

    if is_valid:
        return LogDirectoryValidateResponse(
            valid=True,
            log_path=str(log_path),
            error=None,
        )
    else:
        return LogDirectoryValidateResponse(
            valid=False,
            log_path=None,
            error="Log file not found. You can point to the game folder, the Logs folder, or the UE_game.log file directly.",
        )
