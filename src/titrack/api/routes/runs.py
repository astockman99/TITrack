"""Runs API routes."""

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from titrack.api.schemas import (
    LootItem,
    RunListResponse,
    RunResponse,
    RunStatsResponse,
)
from titrack.core.models import Run
from titrack.data.zones import get_zone_display_name
from titrack.db.repository import Repository
from titrack.parser.patterns import FE_CONFIG_BASE_ID

router = APIRouter(prefix="/api/runs", tags=["runs"])

# Level type constants (from game logs)
LEVEL_TYPE_NORMAL = 3
LEVEL_TYPE_NIGHTMARE = 11


class ResetResponse(BaseModel):
    """Response model for reset endpoint."""

    success: bool
    runs_deleted: int
    message: str


def get_repository() -> Repository:
    """Dependency injection for repository - set by app factory."""
    raise NotImplementedError("Repository not configured")


def _build_loot(summary: dict[int, int], repo: Repository) -> list[LootItem]:
    """Build loot items from a run summary."""
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
    return sorted(loot, key=lambda x: abs(x.quantity), reverse=True)


def _consolidate_runs(all_runs_including_hubs: list[Run], repo: Repository) -> list[RunResponse]:
    """
    Consolidate runs from the same map instance.

    Runs are only consolidated if they:
    1. Have the same level_uid (same map instance)
    2. Are consecutive (no hub visit in between)

    Normal runs (level_type=3) are merged into one entry.
    Nightmare runs (level_type=11) are kept separate with is_nightmare=True.

    This handles the Twinightmare mechanic where entering nightmare
    creates a zone transition but it's part of the same map run.
    """
    # Sort all runs by start time (ascending) to detect consecutive runs
    sorted_runs = sorted(all_runs_including_hubs, key=lambda r: r.start_ts)

    # Build sessions: consecutive non-hub runs with same level_uid
    # A hub run breaks the session
    sessions: list[list[Run]] = []
    current_session: list[Run] = []
    current_uid: Optional[int] = None

    for run in sorted_runs:
        if run.is_hub:
            # Hub breaks the session
            if current_session:
                sessions.append(current_session)
                current_session = []
                current_uid = None
        else:
            # Non-hub run
            if run.level_uid is None:
                # No level_uid - treat as its own session
                if current_session:
                    sessions.append(current_session)
                sessions.append([run])
                current_session = []
                current_uid = None
            elif run.level_uid == current_uid:
                # Same level_uid, add to current session
                current_session.append(run)
            else:
                # Different level_uid, start new session
                if current_session:
                    sessions.append(current_session)
                current_session = [run]
                current_uid = run.level_uid

    # Don't forget the last session
    if current_session:
        sessions.append(current_session)

    result = []

    for session_runs in sessions:
        if not session_runs:
            continue

        # Separate nightmare runs from normal runs within the session
        normal_runs = [r for r in session_runs if r.level_type != LEVEL_TYPE_NIGHTMARE]
        nightmare_runs = [r for r in session_runs if r.level_type == LEVEL_TYPE_NIGHTMARE]

        # Consolidate normal runs into one entry
        if normal_runs:
            # Use the first run's metadata, but aggregate values
            first_run = min(normal_runs, key=lambda r: r.start_ts)
            last_run = max(normal_runs, key=lambda r: r.end_ts or r.start_ts)

            # Aggregate summaries
            combined_summary: dict[int, int] = defaultdict(int)
            total_fe = 0
            total_value = 0.0
            total_duration = 0.0
            run_ids = []

            for run in normal_runs:
                run_ids.append(run.id)
                summary = repo.get_run_summary(run.id)
                for config_id, qty in summary.items():
                    combined_summary[config_id] += qty
                fe, value = repo.get_run_value(run.id)
                total_fe += fe
                total_value += value
                if run.duration_seconds:
                    total_duration += run.duration_seconds

            result.append(
                RunResponse(
                    id=first_run.id,  # Use first run's ID as primary
                    zone_name=get_zone_display_name(first_run.zone_signature, first_run.level_id),
                    zone_signature=first_run.zone_signature,
                    start_ts=first_run.start_ts,
                    end_ts=last_run.end_ts,
                    duration_seconds=total_duration if total_duration > 0 else None,
                    is_hub=first_run.is_hub,
                    is_nightmare=False,
                    fe_gained=total_fe,
                    total_value=round(total_value, 2),
                    loot=_build_loot(dict(combined_summary), repo),
                    consolidated_run_ids=run_ids if len(run_ids) > 1 else None,
                )
            )

        # Keep nightmare runs separate
        for run in nightmare_runs:
            summary = repo.get_run_summary(run.id)
            fe_gained, total_value = repo.get_run_value(run.id)
            result.append(
                RunResponse(
                    id=run.id,
                    zone_name=get_zone_display_name(run.zone_signature, run.level_id) + " (Nightmare)",
                    zone_signature=run.zone_signature,
                    start_ts=run.start_ts,
                    end_ts=run.end_ts,
                    duration_seconds=run.duration_seconds,
                    is_hub=run.is_hub,
                    is_nightmare=True,
                    fe_gained=fe_gained,
                    total_value=round(total_value, 2),
                    loot=_build_loot(summary, repo),
                )
            )

    # Sort by start time descending
    result.sort(key=lambda r: r.start_ts, reverse=True)
    return result


@router.get("", response_model=RunListResponse)
def list_runs(
    page: int = 1,
    page_size: int = 20,
    exclude_hubs: bool = True,
    repo: Repository = Depends(get_repository),
) -> RunListResponse:
    """List recent runs with pagination and consolidation."""
    # Get more runs than needed to handle filtering and consolidation
    fetch_limit = page_size * 5
    offset = (page - 1) * page_size

    # Fetch all runs INCLUDING hubs for session detection
    all_runs = repo.get_recent_runs(limit=fetch_limit + offset * 2)

    # Consolidate runs (merges normal runs in same map instance, uses hubs to detect session breaks)
    # This function receives all runs including hubs but only returns non-hub consolidated results
    consolidated = _consolidate_runs(all_runs, repo)

    # Apply pagination to consolidated results
    paginated = consolidated[offset : offset + page_size]

    return RunListResponse(
        runs=paginated,
        total=len(consolidated),
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

    is_nightmare = run.level_type == LEVEL_TYPE_NIGHTMARE
    zone_name = get_zone_display_name(run.zone_signature, run.level_id)
    if is_nightmare:
        zone_name += " (Nightmare)"

    return RunResponse(
        id=run.id,
        zone_name=zone_name,
        zone_signature=run.zone_signature,
        start_ts=run.start_ts,
        end_ts=run.end_ts,
        duration_seconds=run.duration_seconds,
        is_hub=run.is_hub,
        is_nightmare=is_nightmare,
        fe_gained=fe_gained,
        total_value=round(total_value, 2),
        loot=_build_loot(summary, repo),
    )
