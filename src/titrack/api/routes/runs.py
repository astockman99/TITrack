"""Runs API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from titrack.api.schemas import (
    LootItem,
    RunListResponse,
    RunResponse,
    RunStatsResponse,
)
from titrack.data.zones import get_zone_display_name
from titrack.db.repository import Repository
from titrack.parser.patterns import FE_CONFIG_BASE_ID

router = APIRouter(prefix="/api/runs", tags=["runs"])


class ResetResponse(BaseModel):
    """Response model for reset endpoint."""

    success: bool
    runs_deleted: int
    message: str


def get_repository() -> Repository:
    """Dependency injection for repository - set by app factory."""
    raise NotImplementedError("Repository not configured")


@router.get("", response_model=RunListResponse)
def list_runs(
    page: int = 1,
    page_size: int = 20,
    exclude_hubs: bool = True,
    repo: Repository = Depends(get_repository),
) -> RunListResponse:
    """List recent runs with pagination."""
    # Get more runs than needed to handle hub filtering
    fetch_limit = page_size * 3 if exclude_hubs else page_size
    offset = (page - 1) * page_size

    all_runs = repo.get_recent_runs(limit=fetch_limit + offset)

    # Filter hubs if requested
    if exclude_hubs:
        all_runs = [r for r in all_runs if not r.is_hub]

    # Apply pagination
    runs = all_runs[offset : offset + page_size]

    # Build response
    run_responses = []
    for run in runs:
        summary = repo.get_run_summary(run.id)
        fe_gained, total_value = repo.get_run_value(run.id)

        loot = []
        for config_id, quantity in summary.items():
            if quantity != 0:
                item = repo.get_item(config_id)
                price = repo.get_price(config_id)
                item_price_fe = price.price_fe if price else None
                # FE currency is worth 1:1
                if config_id == FE_CONFIG_BASE_ID:
                    item_price_fe = 1.0
                item_total = item_price_fe * quantity if item_price_fe else None
                loot.append(
                    LootItem(
                        config_base_id=config_id,
                        name=item.name_en if item else f"Unknown {config_id}",
                        quantity=quantity,
                        icon_url=item.icon_url if item else None,
                        price_fe=item_price_fe,
                        total_value_fe=round(item_total, 2) if item_total else None,
                    )
                )

        run_responses.append(
            RunResponse(
                id=run.id,
                zone_name=get_zone_display_name(run.zone_signature, run.level_id),
                zone_signature=run.zone_signature,
                start_ts=run.start_ts,
                end_ts=run.end_ts,
                duration_seconds=run.duration_seconds,
                is_hub=run.is_hub,
                fe_gained=fe_gained,
                total_value=round(total_value, 2),
                loot=sorted(loot, key=lambda x: abs(x.quantity), reverse=True),
            )
        )

    return RunListResponse(
        runs=run_responses,
        total=len(all_runs),
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=RunStatsResponse)
def get_stats(
    exclude_hubs: bool = True,
    repo: Repository = Depends(get_repository),
) -> RunStatsResponse:
    """Get summary statistics for all runs."""
    all_runs = repo.get_recent_runs(limit=1000)

    if exclude_hubs:
        all_runs = [r for r in all_runs if not r.is_hub]

    total_fe = 0
    total_value = 0.0
    total_duration = 0.0

    for run in all_runs:
        fe_gained, run_value = repo.get_run_value(run.id)
        total_fe += fe_gained
        total_value += run_value
        if run.duration_seconds:
            total_duration += run.duration_seconds

    total_runs = len(all_runs)
    avg_fe = total_fe / total_runs if total_runs > 0 else 0
    avg_value = total_value / total_runs if total_runs > 0 else 0
    fe_per_hour = (total_fe / total_duration * 3600) if total_duration > 0 else 0
    value_per_hour = (total_value / total_duration * 3600) if total_duration > 0 else 0

    return RunStatsResponse(
        total_runs=total_runs,
        total_fe=total_fe,
        total_value=round(total_value, 2),
        avg_fe_per_run=round(avg_fe, 2),
        avg_value_per_run=round(avg_value, 2),
        total_duration_seconds=round(total_duration, 2),
        fe_per_hour=round(fe_per_hour, 2),
        value_per_hour=round(value_per_hour, 2),
    )


@router.post("/reset", response_model=ResetResponse)
def reset_stats(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> ResetResponse:
    """Reset all run tracking data (clears runs and item_deltas)."""
    # Use collector's database connection if available (ensures same connection)
    collector = getattr(request.app.state, 'collector', None)
    if collector is not None and hasattr(collector, 'clear_run_data'):
        runs_deleted = collector.clear_run_data()
    else:
        # Fallback to API's repository
        runs_deleted = repo.clear_run_data()

    return ResetResponse(
        success=True,
        runs_deleted=runs_deleted,
        message=f"Cleared {runs_deleted} runs and all associated loot data.",
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: int,
    repo: Repository = Depends(get_repository),
) -> RunResponse:
    """Get a single run by ID."""
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    summary = repo.get_run_summary(run.id)
    fe_gained, total_value = repo.get_run_value(run.id)

    loot = []
    for config_id, quantity in summary.items():
        if quantity != 0:
            item = repo.get_item(config_id)
            price = repo.get_price(config_id)
            item_price_fe = price.price_fe if price else None
            # FE currency is worth 1:1
            if config_id == FE_CONFIG_BASE_ID:
                item_price_fe = 1.0
            item_total = item_price_fe * quantity if item_price_fe else None
            loot.append(
                LootItem(
                    config_base_id=config_id,
                    name=item.name_en if item else f"Unknown {config_id}",
                    quantity=quantity,
                    icon_url=item.icon_url if item else None,
                    price_fe=item_price_fe,
                    total_value_fe=round(item_total, 2) if item_total else None,
                )
            )

    return RunResponse(
        id=run.id,
        zone_name=get_zone_display_name(run.zone_signature, run.level_id),
        zone_signature=run.zone_signature,
        start_ts=run.start_ts,
        end_ts=run.end_ts,
        duration_seconds=run.duration_seconds,
        is_hub=run.is_hub,
        fe_gained=fe_gained,
        total_value=round(total_value, 2),
        loot=sorted(loot, key=lambda x: abs(x.quantity), reverse=True),
    )
