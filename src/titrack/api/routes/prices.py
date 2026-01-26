"""Prices API routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

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
    )
    repo.upsert_price(price)

    return PriceResponse(
        config_base_id=config_base_id,
        name=item.name_en if item else f"Unknown {config_base_id}",
        price_fe=price.price_fe,
        source=price.source,
        updated_at=price.updated_at,
    )
