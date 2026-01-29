"""Settings API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
