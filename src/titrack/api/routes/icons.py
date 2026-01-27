"""Icon proxy routes - fetches icons from CDN with proper headers."""

import urllib.request
import urllib.error
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import Response as FastAPIResponse

from titrack.db.repository import Repository


def get_repository() -> Repository:
    """Dependency injection for repository - set by app factory."""
    raise NotImplementedError("Repository not configured")

router = APIRouter(prefix="/api/icons", tags=["icons"])

# In-memory cache for icons (icon_url -> bytes)
# In production, consider using a disk cache or Redis
_icon_cache: dict[str, bytes] = {}
_failed_urls: set[str] = set()

# CDN request headers
CDN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://tlidb.com/",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}


def fetch_icon(url: str) -> Optional[bytes]:
    """Fetch icon from CDN with proper headers."""
    if url in _failed_urls:
        return None

    if url in _icon_cache:
        return _icon_cache[url]

    try:
        req = urllib.request.Request(url, headers=CDN_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            _icon_cache[url] = data
            return data
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        _failed_urls.add(url)
        return None


@router.get("/{config_base_id}")
def get_icon(config_base_id: int, repo: Repository = Depends(get_repository)) -> Response:
    """
    Proxy icon for an item.

    Fetches the icon from the CDN with proper headers and caches it.
    Returns 404 if no icon URL exists or the CDN returns an error.
    """
    # Look up item to get icon URL
    item = repo.get_item(config_base_id)
    if not item or not item.icon_url:
        raise HTTPException(status_code=404, detail="No icon available")

    # Fetch from CDN (with caching)
    icon_data = fetch_icon(item.icon_url)
    if icon_data is None:
        raise HTTPException(status_code=404, detail="Icon not available from CDN")

    # Determine content type from URL
    content_type = "image/webp"
    if item.icon_url.endswith(".png"):
        content_type = "image/png"
    elif item.icon_url.endswith(".jpg") or item.icon_url.endswith(".jpeg"):
        content_type = "image/jpeg"

    return FastAPIResponse(
        content=icon_data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
        },
    )
