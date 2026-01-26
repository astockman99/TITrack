"""Pydantic schemas for API responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LootItem(BaseModel):
    """Single item in loot breakdown."""

    config_base_id: int
    name: str
    quantity: int
    icon_url: Optional[str] = None
    price_fe: Optional[float] = None  # Price per unit
    total_value_fe: Optional[float] = None  # quantity * price


class RunResponse(BaseModel):
    """Single run response."""

    id: int
    zone_name: str
    zone_signature: str
    start_ts: datetime
    end_ts: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    is_hub: bool
    fe_gained: int  # Raw FE currency gained
    total_value: float  # Total value including priced items
    loot: list[LootItem]


class RunListResponse(BaseModel):
    """Paginated list of runs."""

    runs: list[RunResponse]
    total: int
    page: int
    page_size: int


class RunStatsResponse(BaseModel):
    """Summary statistics for runs."""

    total_runs: int
    total_fe: int  # Raw FE gained
    total_value: float  # Total value including priced items
    avg_fe_per_run: float
    avg_value_per_run: float
    total_duration_seconds: float
    fe_per_hour: float  # Raw FE per hour
    value_per_hour: float  # Total value per hour


class InventoryItem(BaseModel):
    """Single item in inventory."""

    config_base_id: int
    name: str
    quantity: int
    icon_url: Optional[str] = None
    price_fe: Optional[float] = None
    total_value_fe: Optional[float] = None


class InventoryResponse(BaseModel):
    """Current inventory state."""

    items: list[InventoryItem]
    total_fe: int
    net_worth_fe: float


class ItemResponse(BaseModel):
    """Item metadata response."""

    config_base_id: int
    name_en: Optional[str] = None
    name_cn: Optional[str] = None
    type_cn: Optional[str] = None
    icon_url: Optional[str] = None
    url_en: Optional[str] = None
    url_cn: Optional[str] = None


class ItemListResponse(BaseModel):
    """List of items."""

    items: list[ItemResponse]
    total: int


class PriceResponse(BaseModel):
    """Price entry response."""

    config_base_id: int
    name: str
    price_fe: float
    source: str
    updated_at: datetime


class PriceListResponse(BaseModel):
    """List of prices."""

    prices: list[PriceResponse]
    total: int


class PriceUpdateRequest(BaseModel):
    """Request to update a price."""

    price_fe: float
    source: str = "manual"


class StatusResponse(BaseModel):
    """Server status response."""

    status: str
    collector_running: bool
    db_path: str
    log_path: Optional[str] = None
    item_count: int
    run_count: int
