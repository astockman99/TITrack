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
    is_nightmare: bool = False  # True if this is a nightmare run (Twinightmare)
    fe_gained: int  # Raw FE currency gained
    total_value: float  # Total value including priced items (gross)
    loot: list[LootItem]
    consolidated_run_ids: Optional[list[int]] = None  # IDs of runs merged into this one
    # Map cost tracking fields (only populated when map_costs_enabled)
    map_cost_items: Optional[list[LootItem]] = None  # Items consumed (each item has price_fe=None if unknown)
    map_cost_fe: Optional[float] = None  # Sum of priced items only
    map_cost_has_unpriced: bool = False  # True if any items have unknown price
    net_value_fe: Optional[float] = None  # total_value - map_cost_fe


class RunListResponse(BaseModel):
    """Paginated list of runs."""

    runs: list[RunResponse]
    total: int
    page: int
    page_size: int


class ActiveRunResponse(BaseModel):
    """Currently active run with live loot drops."""

    id: int
    zone_name: str
    zone_signature: str
    start_ts: datetime
    duration_seconds: float  # Time since run started
    fe_gained: int  # Raw FE currency gained so far
    total_value: float  # Total value including priced items (gross)
    loot: list[LootItem]  # Items picked up so far
    # Map cost tracking fields (only populated when map_costs_enabled)
    map_cost_items: Optional[list[LootItem]] = None  # Items consumed (each item has price_fe=None if unknown)
    map_cost_fe: Optional[float] = None  # Sum of priced items only
    map_cost_has_unpriced: bool = False  # True if any items have unknown price
    net_value_fe: Optional[float] = None  # total_value - map_cost_fe


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
    realtime_tracking: bool = False  # Is realtime tracking mode on?
    realtime_paused: bool = False  # Is the timer currently paused?
    map_duration_seconds: float = 0.0  # Always the sum of in-map time


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


class ItemUpdateRequest(BaseModel):
    """Request to update an item's name."""

    name_en: Optional[str] = None


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
    log_path_missing: bool = False
    item_count: int
    run_count: int
    awaiting_player: bool = False


class PlayerResponse(BaseModel):
    """Player/character information."""

    name: str
    level: int
    season_id: int
    season_name: str
    hero_id: int
    hero_name: str
    player_id: Optional[str] = None


class LootReportItem(BaseModel):
    """Single item in loot report."""

    config_base_id: int
    name: str
    quantity: int
    icon_url: Optional[str] = None
    price_fe: Optional[float] = None  # Price per unit
    total_value_fe: Optional[float] = None  # quantity * price
    percentage: Optional[float] = None  # Percentage of total value


class LootReportResponse(BaseModel):
    """Cumulative loot report across all runs."""

    items: list[LootReportItem]
    total_value_fe: float  # Gross value of all loot
    total_map_cost_fe: float  # Total map costs (if enabled)
    profit_fe: float  # total_value_fe - total_map_cost_fe
    total_items: int  # Count of unique item types
    run_count: int
    total_duration_seconds: float  # Total time spent in maps
    profit_per_hour: float  # Profit per hour of map time
    profit_per_map: float  # Average profit per map
    map_costs_enabled: bool  # Whether map costs are being tracked
