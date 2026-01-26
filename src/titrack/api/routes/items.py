"""Items API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from titrack.api.schemas import ItemListResponse, ItemResponse, ItemUpdateRequest
from titrack.db.repository import Repository

router = APIRouter(prefix="/api/items", tags=["items"])


def get_repository() -> Repository:
    """Dependency injection for repository - set by app factory."""
    raise NotImplementedError("Repository not configured")


@router.get("", response_model=ItemListResponse)
def list_items(
    search: str = Query(None, description="Search by name"),
    limit: int = Query(100, le=1000),
    repo: Repository = Depends(get_repository),
) -> ItemListResponse:
    """List all items, optionally filtered by search term."""
    all_items = repo.get_all_items()

    # Filter by search if provided
    if search:
        search_lower = search.lower()
        all_items = [
            i
            for i in all_items
            if (i.name_en and search_lower in i.name_en.lower())
            or (i.name_cn and search_lower in i.name_cn)
        ]

    # Sort by name
    all_items.sort(key=lambda x: x.name_en or "")

    # Apply limit
    items = all_items[:limit]

    return ItemListResponse(
        items=[
            ItemResponse(
                config_base_id=i.config_base_id,
                name_en=i.name_en,
                name_cn=i.name_cn,
                type_cn=i.type_cn,
                icon_url=i.icon_url,
                url_en=i.url_en,
                url_cn=i.url_cn,
            )
            for i in items
        ],
        total=len(all_items),
    )


@router.get("/{config_base_id}", response_model=ItemResponse)
def get_item(
    config_base_id: int,
    repo: Repository = Depends(get_repository),
) -> ItemResponse:
    """Get a single item by ConfigBaseId."""
    item = repo.get_item(config_base_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return ItemResponse(
        config_base_id=item.config_base_id,
        name_en=item.name_en,
        name_cn=item.name_cn,
        type_cn=item.type_cn,
        icon_url=item.icon_url,
        url_en=item.url_en,
        url_cn=item.url_cn,
    )


@router.patch("/{config_base_id}", response_model=ItemResponse)
def update_item(
    config_base_id: int,
    request: ItemUpdateRequest,
    repo: Repository = Depends(get_repository),
) -> ItemResponse:
    """Update an item's name."""
    item = repo.get_item(config_base_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if request.name_en is not None:
        repo.update_item_name(config_base_id, request.name_en)
        item = repo.get_item(config_base_id)

    return ItemResponse(
        config_base_id=item.config_base_id,
        name_en=item.name_en,
        name_cn=item.name_cn,
        type_cn=item.type_cn,
        icon_url=item.icon_url,
        url_en=item.url_en,
        url_cn=item.url_cn,
    )
