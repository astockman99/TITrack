"""Prices API routes."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from titrack.api.schemas import PriceListResponse, PriceResponse, PriceUpdateRequest
from titrack.core.models import Price
from titrack.db.repository import Repository

router = APIRouter(prefix="/api/prices", tags=["prices"])


def get_repository() -> Repository:
    """Dependency injection for repository - set by app factory."""
    raise NotImplementedError("Repository not configured")


@router.get("", response_model=PriceListResponse)
def list_prices(
    repo: Repository = Depends(get_repository),
) -> PriceListResponse:
    """List all item prices."""
    all_prices = repo.get_all_prices()

    prices = []
    for price in all_prices:
        item = repo.get_item(price.config_base_id)
        prices.append(
            PriceResponse(
                config_base_id=price.config_base_id,
                name=item.name_en if item else f"Unknown {price.config_base_id}",
                price_fe=price.price_fe,
                source=price.source,
                updated_at=price.updated_at,
            )
        )

    # Sort by name
    prices.sort(key=lambda x: x.name)

    return PriceListResponse(
        prices=prices,
        total=len(prices),
    )


@router.get("/export")
def export_prices(
    repo: Repository = Depends(get_repository),
) -> JSONResponse:
    """Export all prices as a seed-compatible JSON file."""
    all_prices = repo.get_all_prices()

    prices_data = []
    for price in all_prices:
        item = repo.get_item(price.config_base_id)
        prices_data.append({
            "id": str(price.config_base_id),
            "name_en": item.name_en if item else None,
            "price_fe": price.price_fe,
            "source": price.source,
        })

    # Sort by name for readability
    prices_data.sort(key=lambda x: x.get("name_en") or "")

    export_data: dict[str, Any] = {
        "meta": {
            "exported_at_utc": datetime.utcnow().isoformat() + "Z",
            "count": len(prices_data),
            "notes": [
                "Price seed file for TITrack.",
                "Prices are in FE (Flame Elementium).",
                "These values will be overwritten when users search the AH.",
            ],
        },
        "prices": prices_data,
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": "attachment; filename=titrack_prices_seed.json"
        },
    )


class MigratePricesResponse(PriceListResponse):
    """Response for migrate prices endpoint."""
    migrated: int


@router.post("/migrate-legacy", response_model=MigratePricesResponse)
def migrate_legacy_prices(
    repo: Repository = Depends(get_repository),
) -> MigratePricesResponse:
    """
    Migrate legacy prices (season_id=0) to the current season.

    Use this to recover prices that were saved before multi-season support.
    """
    if repo._current_season_id is None:
        raise HTTPException(
            status_code=400,
            detail="No season context set. Please ensure a character is detected."
        )

    # Migrate legacy prices
    migrated = repo.migrate_legacy_prices(repo._current_season_id)

    # Return updated price list
    all_prices = repo.get_all_prices()
    prices = []
    for price in all_prices:
        item = repo.get_item(price.config_base_id)
        prices.append(
            PriceResponse(
                config_base_id=price.config_base_id,
                name=item.name_en if item else f"Unknown {price.config_base_id}",
                price_fe=price.price_fe,
                source=price.source,
                updated_at=price.updated_at,
            )
        )
    prices.sort(key=lambda x: x.name)

    return MigratePricesResponse(
        prices=prices,
        total=len(prices),
        migrated=migrated,
    )


@router.get("/{config_base_id}", response_model=PriceResponse)
def get_price(
    config_base_id: int,
    repo: Repository = Depends(get_repository),
) -> PriceResponse:
    """Get price for a specific item."""
    price = repo.get_price(config_base_id)
    if not price:
        raise HTTPException(status_code=404, detail="Price not found")

    item = repo.get_item(config_base_id)

    return PriceResponse(
        config_base_id=price.config_base_id,
        name=item.name_en if item else f"Unknown {price.config_base_id}",
        price_fe=price.price_fe,
        source=price.source,
        updated_at=price.updated_at,
    )


@router.put("/{config_base_id}", response_model=PriceResponse)
def update_price(
    config_base_id: int,
    request: PriceUpdateRequest,
    repo: Repository = Depends(get_repository),
) -> PriceResponse:
    """Update or create a price for an item."""
    # Verify item exists (optional, allows pricing unknown items)
    item = repo.get_item(config_base_id)

    price = Price(
        config_base_id=config_base_id,
        price_fe=request.price_fe,
        source=request.source,
        updated_at=datetime.now(),
        season_id=repo._current_season_id,  # Tag with current season
    )
    repo.upsert_price(price)

    return PriceResponse(
        config_base_id=config_base_id,
        name=item.name_en if item else f"Unknown {config_base_id}",
        price_fe=price.price_fe,
        source=price.source,
        updated_at=price.updated_at,
    )