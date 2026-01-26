"""Inventory API routes."""

from enum import Enum

from fastapi import APIRouter, Depends, Query

from titrack.api.schemas import InventoryItem, InventoryResponse
from titrack.db.repository import Repository
from titrack.parser.patterns import FE_CONFIG_BASE_ID

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


class SortField(str, Enum):
    """Inventory sort fields."""
    QUANTITY = "quantity"
    VALUE = "value"
    NAME = "name"


class SortOrder(str, Enum):
    """Sort order."""
    ASC = "asc"
    DESC = "desc"


def get_repository() -> Repository:
    """Dependency injection for repository - set by app factory."""
    raise NotImplementedError("Repository not configured")


@router.get("", response_model=InventoryResponse)
def get_inventory(
    sort_by: SortField = Query(SortField.VALUE, description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order"),
    repo: Repository = Depends(get_repository),
) -> InventoryResponse:
    """Get current inventory state."""
    states = repo.get_all_slot_states()

    # Aggregate by item
    totals: dict[int, int] = {}
    for state in states:
        if state.num > 0:
            totals[state.config_base_id] = totals.get(state.config_base_id, 0) + state.num

    # Build response with prices
    items = []
    total_fe = totals.get(FE_CONFIG_BASE_ID, 0)
    net_worth = float(total_fe)

    for config_id, quantity in totals.items():
        item = repo.get_item(config_id)
        price = repo.get_price(config_id)

        price_fe = price.price_fe if price else None
        # FE currency is worth 1:1
        if config_id == FE_CONFIG_BASE_ID:
            price_fe = 1.0
        total_value = price_fe * quantity if price_fe else None

        if total_value and config_id != FE_CONFIG_BASE_ID:
            net_worth += total_value

        items.append(
            InventoryItem(
                config_base_id=config_id,
                name=item.name_en if item else f"Unknown {config_id}",
                quantity=quantity,
                icon_url=item.icon_url if item else None,
                price_fe=price_fe,
                total_value_fe=total_value,
            )
        )

    # Sort based on parameters
    reverse = sort_order == SortOrder.DESC

    if sort_by == SortField.VALUE:
        # Sort by value, items without price go to end
        items.sort(
            key=lambda x: (
                x.config_base_id != FE_CONFIG_BASE_ID,  # FE always first
                x.total_value_fe is None,  # Items without price last
                -(x.total_value_fe or 0) if reverse else (x.total_value_fe or 0),
            )
        )
    elif sort_by == SortField.QUANTITY:
        items.sort(
            key=lambda x: (
                x.config_base_id != FE_CONFIG_BASE_ID,  # FE always first
                -x.quantity if reverse else x.quantity,
            )
        )
    elif sort_by == SortField.NAME:
        items.sort(
            key=lambda x: (
                x.config_base_id != FE_CONFIG_BASE_ID,  # FE always first
                x.name.lower() if not reverse else "",
            ),
            reverse=reverse if sort_by == SortField.NAME else False,
        )

    return InventoryResponse(
        items=items,
        total_fe=total_fe,
        net_worth_fe=round(net_worth, 2),
    )
