"""Runs API routes."""

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from datetime import date

from titrack.api.schemas import (
    ActiveRunResponse,
    LootItem,
    LootReportItem,
    LootReportResponse,
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
# Sub-zone level types: zones entered from within a map that shouldn't break the session.
# These are kept as separate run entries but the surrounding map runs are recombined.
SUB_ZONE_LEVEL_TYPES = {19}  # 19 = Fateful Contest (Arcana mechanic)


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
    tax_multiplier = repo.get_trade_tax_multiplier()

    for config_id, quantity in summary.items():
        if quantity != 0:
            item = repo.get_item(config_id)

            # Use effective price (cloud-first, local overrides if newer)
            item_price_fe = repo.get_effective_price(config_id)

            # FE currency is worth 1:1 and not taxed
            if config_id == FE_CONFIG_BASE_ID:
                item_price_fe = 1.0
                item_total = item_price_fe * quantity if item_price_fe else None
            else:
                # Apply trade tax to non-FE items (consistent with get_run_value)
                item_total = item_price_fe * quantity * tax_multiplier if item_price_fe else None

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


def _build_cost_items(cost_summary: dict[int, int], repo: Repository) -> list[LootItem]:
    """Build cost items from a run's map cost summary."""
    cost_items = []

    for config_id, quantity in cost_summary.items():
        if quantity != 0:
            item = repo.get_item(config_id)
            item_price_fe = repo.get_effective_price(config_id)
            # Use absolute quantity for display (costs are negative)
            abs_qty = abs(quantity)
            # No tax on consumed items - you paid full price when buying them
            item_total = item_price_fe * abs_qty if item_price_fe else None
            cost_items.append(
                LootItem(
                    config_base_id=config_id,
                    name=item.name_en if item else f"Unknown {config_id}",
                    quantity=quantity,  # Keep negative to indicate consumption
                    icon_url=item.icon_url if item else None,
                    price_fe=item_price_fe,
                    total_value_fe=round(item_total, 2) if item_total else None,
                )
            )
    return sorted(cost_items, key=lambda x: abs(x.total_value_fe or 0), reverse=True)


def _consolidate_runs(
    all_runs_including_hubs: list[Run],
    repo: Repository,
    map_costs_enabled: bool = False,
) -> list[RunResponse]:
    """
    Consolidate runs from the same map instance.

    Runs are only consolidated if they:
    1. Have the same level_uid (same map instance)
    2. Are consecutive (no hub visit in between)

    Normal runs (level_type=3) are merged into one entry.
    Sub-zone runs (nightmare level_type=11, fateful contest level_type=19, etc.)
    are kept separate with is_nightmare=True.

    Sub-zone runs with different level_uids (e.g., Fateful Contest) don't break
    the session, so the surrounding map parts are recombined.
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
        elif run.level_type in SUB_ZONE_LEVEL_TYPES:
            # Sub-zone run (e.g., Fateful Contest) - save separately,
            # don't break current session so surrounding map runs recombine
            sessions.append([run])
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

        # Separate sub-zone runs (nightmare, fateful contest, etc.) from normal runs
        normal_runs = [
            r for r in session_runs
            if r.level_type != LEVEL_TYPE_NIGHTMARE and r.level_type not in SUB_ZONE_LEVEL_TYPES
        ]
        sub_zone_runs = [
            r for r in session_runs
            if r.level_type == LEVEL_TYPE_NIGHTMARE or r.level_type in SUB_ZONE_LEVEL_TYPES
        ]

        # Consolidate normal runs into one entry
        if normal_runs:
            # Use the first run's metadata, but aggregate values
            first_run = min(normal_runs, key=lambda r: r.start_ts)
            last_run = max(normal_runs, key=lambda r: r.end_ts or r.start_ts)

            # Aggregate summaries
            combined_summary: dict[int, int] = defaultdict(int)
            combined_cost_summary: dict[int, int] = defaultdict(int)
            total_fe = 0
            total_value = 0.0
            total_cost = 0.0
            total_duration = 0.0
            run_ids = []
            has_unpriced_costs = False

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

                # Aggregate costs if enabled
                if map_costs_enabled:
                    cost_summary, cost_value, unpriced = repo.get_run_cost(run.id)
                    for config_id, qty in cost_summary.items():
                        combined_cost_summary[config_id] += qty
                    total_cost += cost_value
                    if unpriced:
                        has_unpriced_costs = True

            # Build cost items if enabled
            cost_items = None
            cost_fe = None
            net_value = None
            if map_costs_enabled and combined_cost_summary:
                cost_items = _build_cost_items(dict(combined_cost_summary), repo)
                cost_fe = round(total_cost, 2)
                net_value = round(total_value - total_cost, 2)

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
                    map_cost_items=cost_items,
                    map_cost_fe=cost_fe,
                    map_cost_has_unpriced=has_unpriced_costs,
                    net_value_fe=net_value,
                )
            )

        # Keep sub-zone runs (nightmare, fateful contest, etc.) separate
        for run in sub_zone_runs:
            summary = repo.get_run_summary(run.id)
            fe_gained, total_value = repo.get_run_value(run.id)

            # Get costs if enabled
            cost_items = None
            cost_fe = None
            net_value = None
            has_unpriced_costs = False
            if map_costs_enabled:
                cost_summary, cost_value, unpriced = repo.get_run_cost(run.id)
                if cost_summary:
                    cost_items = _build_cost_items(cost_summary, repo)
                    cost_fe = round(cost_value, 2)
                    net_value = round(total_value - cost_value, 2)
                    has_unpriced_costs = bool(unpriced)

            zone_name = get_zone_display_name(run.zone_signature, run.level_id)
            if run.level_type == LEVEL_TYPE_NIGHTMARE:
                zone_name += " (Nightmare)"

            result.append(
                RunResponse(
                    id=run.id,
                    zone_name=zone_name,
                    zone_signature=run.zone_signature,
                    start_ts=run.start_ts,
                    end_ts=run.end_ts,
                    duration_seconds=run.duration_seconds,
                    is_hub=run.is_hub,
                    is_nightmare=True,
                    fe_gained=fe_gained,
                    total_value=round(total_value, 2),
                    loot=_build_loot(summary, repo),
                    map_cost_items=cost_items,
                    map_cost_fe=cost_fe,
                    map_cost_has_unpriced=has_unpriced_costs,
                    net_value_fe=net_value,
                )
            )

    # Sort by start time descending
    result.sort(key=lambda r: r.start_ts, reverse=True)
    return result


# Validation limits
MAX_PAGE_SIZE = 100
MAX_PAGE = 10000


@router.get("", response_model=RunListResponse)
def list_runs(
    page: int = 1,
    page_size: int = 20,
    exclude_hubs: bool = True,
    repo: Repository = Depends(get_repository),
) -> RunListResponse:
    """List recent runs with pagination and consolidation."""
    # Validate pagination parameters
    if page < 1:
        page = 1
    if page > MAX_PAGE:
        raise HTTPException(status_code=400, detail=f"page cannot exceed {MAX_PAGE}")
    if page_size < 1:
        page_size = 1
    if page_size > MAX_PAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"page_size cannot exceed {MAX_PAGE_SIZE}")

    # Get more runs than needed to handle filtering and consolidation
    fetch_limit = page_size * 5
    offset = (page - 1) * page_size

    # Check if map costs are enabled
    map_costs_enabled = repo.get_setting("map_costs_enabled") == "true"

    # Fetch all runs INCLUDING hubs for session detection
    all_runs = repo.get_recent_runs(limit=fetch_limit + offset * 2)

    # Consolidate runs (merges normal runs in same map instance, uses hubs to detect session breaks)
    # This function receives all runs including hubs but only returns non-hub consolidated results
    consolidated = _consolidate_runs(all_runs, repo, map_costs_enabled=map_costs_enabled)

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
    from datetime import datetime

    # Check if map costs are enabled
    map_costs_enabled = repo.get_setting("map_costs_enabled") == "true"

    all_runs = repo.get_recent_runs(limit=1000)

    if exclude_hubs:
        all_runs = [r for r in all_runs if not r.is_hub]

    total_fe = 0
    total_value = 0.0
    total_cost = 0.0
    total_duration = 0.0

    for run in all_runs:
        fe_gained, run_value = repo.get_run_value(run.id)
        total_fe += fe_gained
        total_value += run_value
        if run.duration_seconds:
            total_duration += run.duration_seconds

        # Subtract costs if enabled
        if map_costs_enabled:
            _, cost_value, _ = repo.get_run_cost(run.id)
            total_cost += cost_value

    # Use net value if costs are enabled
    net_value = total_value - total_cost if map_costs_enabled else total_value

    # Keep map_duration as the sum of in-map time (always)
    map_duration = total_duration

    # Check realtime tracking mode
    realtime_enabled = repo.get_setting("realtime_tracking_enabled") == "true"
    realtime_paused = repo.get_setting("realtime_paused") == "true"

    if realtime_enabled and all_runs:
        # Compute wall-clock elapsed time from first run start to now
        first_run_start = min(r.start_ts for r in all_runs)
        now = datetime.now()
        elapsed = (now - first_run_start).total_seconds()

        # Subtract accumulated paused time
        paused_seconds_str = repo.get_setting("realtime_total_paused_seconds") or "0"
        try:
            paused_seconds = float(paused_seconds_str)
        except (ValueError, TypeError):
            paused_seconds = 0.0

        # If currently paused, also subtract time since pause started
        if realtime_paused:
            pause_start_str = repo.get_setting("realtime_pause_start") or ""
            if pause_start_str:
                try:
                    pause_start = datetime.fromisoformat(pause_start_str)
                    paused_seconds += (now - pause_start).total_seconds()
                except (ValueError, TypeError):
                    pass

        total_duration = max(elapsed - paused_seconds, 0.0)

    total_runs = len(all_runs)
    avg_fe = total_fe / total_runs if total_runs > 0 else 0
    avg_value = net_value / total_runs if total_runs > 0 else 0
    fe_per_hour = (total_fe / total_duration * 3600) if total_duration > 0 else 0
    value_per_hour = (net_value / total_duration * 3600) if total_duration > 0 else 0

    return RunStatsResponse(
        total_runs=total_runs,
        total_fe=total_fe,
        total_value=round(net_value, 2),
        avg_fe_per_run=round(avg_fe, 2),
        avg_value_per_run=round(avg_value, 2),
        total_duration_seconds=round(total_duration, 2),
        fe_per_hour=round(fe_per_hour, 2),
        value_per_hour=round(value_per_hour, 2),
        realtime_tracking=realtime_enabled,
        realtime_paused=realtime_paused,
        map_duration_seconds=round(map_duration, 2),
    )


@router.get("/active", response_model=Optional[ActiveRunResponse])
def get_active_run(
    repo: Repository = Depends(get_repository),
) -> Optional[ActiveRunResponse]:
    """Get the currently active run with live loot drops."""
    from datetime import datetime

    active_run = repo.get_active_run()

    if not active_run:
        return None

    # Skip hub runs - only show active map runs
    if active_run.is_hub:
        return None

    # Check if map costs are enabled
    map_costs_enabled = repo.get_setting("map_costs_enabled") == "true"

    # Get loot for this run
    summary = repo.get_run_summary(active_run.id)
    fe_gained, total_value = repo.get_run_value(active_run.id)

    # Get costs if enabled
    cost_items = None
    cost_fe = None
    net_value = None
    has_unpriced_costs = False
    if map_costs_enabled:
        cost_summary, cost_value, unpriced = repo.get_run_cost(active_run.id)
        if cost_summary:
            cost_items = _build_cost_items(cost_summary, repo)
            cost_fe = round(cost_value, 2)
            net_value = round(total_value - cost_value, 2)
            has_unpriced_costs = bool(unpriced)

    # Calculate duration since run started (use naive datetime to match DB)
    now = datetime.now()
    duration = (now - active_run.start_ts).total_seconds()

    zone_name = get_zone_display_name(active_run.zone_signature, active_run.level_id)

    return ActiveRunResponse(
        id=active_run.id,
        zone_name=zone_name,
        zone_signature=active_run.zone_signature,
        start_ts=active_run.start_ts,
        duration_seconds=round(duration, 1),
        fe_gained=fe_gained,
        total_value=round(total_value, 2),
        loot=_build_loot(summary, repo),
        map_cost_items=cost_items,
        map_cost_fe=cost_fe,
        map_cost_has_unpriced=has_unpriced_costs,
        net_value_fe=net_value,
    )


class PauseResponse(BaseModel):
    """Response model for pause endpoint."""

    paused: bool


@router.post("/pause", response_model=PauseResponse)
def toggle_pause(
    repo: Repository = Depends(get_repository),
) -> PauseResponse:
    """Toggle realtime tracking pause on/off."""
    from datetime import datetime

    # Only effective when realtime tracking is enabled
    realtime_enabled = repo.get_setting("realtime_tracking_enabled") == "true"
    if not realtime_enabled:
        raise HTTPException(status_code=400, detail="Realtime tracking is not enabled")

    currently_paused = repo.get_setting("realtime_paused") == "true"

    if not currently_paused:
        # Pause: record the pause start time
        repo.set_setting("realtime_paused", "true")
        repo.set_setting("realtime_pause_start", datetime.now().isoformat())
        return PauseResponse(paused=True)
    else:
        # Unpause: compute elapsed pause and add to total
        now = datetime.now()
        pause_start_str = repo.get_setting("realtime_pause_start") or ""
        elapsed_pause = 0.0
        if pause_start_str:
            try:
                pause_start = datetime.fromisoformat(pause_start_str)
                elapsed_pause = (now - pause_start).total_seconds()
            except (ValueError, TypeError):
                pass

        # Add to accumulated paused seconds
        total_paused_str = repo.get_setting("realtime_total_paused_seconds") or "0"
        try:
            total_paused = float(total_paused_str)
        except (ValueError, TypeError):
            total_paused = 0.0
        total_paused += elapsed_pause

        repo.set_setting("realtime_total_paused_seconds", str(total_paused))
        repo.set_setting("realtime_paused", "false")
        repo.set_setting("realtime_pause_start", "")
        return PauseResponse(paused=False)


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

    # Clear pause state
    repo.set_setting("realtime_paused", "false")
    repo.set_setting("realtime_total_paused_seconds", "0")
    repo.set_setting("realtime_pause_start", "")

    return ResetResponse(
        success=True,
        runs_deleted=runs_deleted,
        message=f"Cleared {runs_deleted} runs and all associated loot data.",
    )


@router.get("/report", response_model=LootReportResponse)
def get_loot_report(
    repo: Repository = Depends(get_repository),
) -> LootReportResponse:
    """Get cumulative loot statistics across all runs since last reset."""
    # Get aggregated loot data
    cumulative_loot = repo.get_cumulative_loot()

    # Check if map costs are enabled
    map_costs_enabled = repo.get_setting("map_costs_enabled") == "true"

    # Get trade tax multiplier
    tax_multiplier = repo.get_trade_tax_multiplier()

    # Build report items with pricing
    items: list[LootReportItem] = []
    total_value = 0.0

    for loot in cumulative_loot:
        config_id = loot["config_base_id"]
        quantity = loot["total_quantity"]

        # Get item metadata
        item = repo.get_item(config_id)

        # Get price (FE is worth 1:1)
        if config_id == FE_CONFIG_BASE_ID:
            price_fe = 1.0
            item_total = float(quantity)  # FE is not taxed
        else:
            price_fe = repo.get_effective_price(config_id)
            if price_fe and price_fe > 0:
                item_total = price_fe * quantity * tax_multiplier
            else:
                item_total = None

        if item_total:
            total_value += item_total

        items.append(
            LootReportItem(
                config_base_id=config_id,
                name=item.name_en if item else f"Unknown {config_id}",
                quantity=quantity,
                icon_url=item.icon_url if item else None,
                price_fe=price_fe,
                total_value_fe=round(item_total, 2) if item_total else None,
                percentage=None,  # Will be calculated after total is known
            )
        )

    # Calculate percentages now that we have total_value
    if total_value > 0:
        for item in items:
            if item.total_value_fe is not None:
                item.percentage = round((item.total_value_fe / total_value) * 100, 2)

    # Sort by total value (highest first), unpriced items at the end
    items.sort(key=lambda x: (x.total_value_fe is None, -(x.total_value_fe or 0)))

    # Get run stats
    run_count = repo.get_completed_run_count()
    total_duration = repo.get_total_run_duration()

    # Get map costs if enabled
    total_map_cost = repo.get_total_map_costs() if map_costs_enabled else 0.0

    # Calculate profit
    profit = total_value - total_map_cost

    # Calculate rates
    profit_per_hour = (profit / total_duration * 3600) if total_duration > 0 else 0.0
    profit_per_map = profit / run_count if run_count > 0 else 0.0

    return LootReportResponse(
        items=items,
        total_value_fe=round(total_value, 2),
        total_map_cost_fe=round(total_map_cost, 2),
        profit_fe=round(profit, 2),
        total_items=len(items),
        run_count=run_count,
        total_duration_seconds=round(total_duration, 2),
        profit_per_hour=round(profit_per_hour, 2),
        profit_per_map=round(profit_per_map, 2),
        map_costs_enabled=map_costs_enabled,
    )


@router.get("/report/csv")
def export_loot_report_csv(
    repo: Repository = Depends(get_repository),
) -> Response:
    """Export loot report as CSV file."""
    # Get the report data (reuse the same logic)
    report = get_loot_report(repo)

    # Build CSV content
    lines = []
    lines.append("Item Name,Config ID,Quantity,Unit Price (FE),Total Value (FE),Percentage")

    for item in report.items:
        name = f'"{item.name.replace(chr(34), chr(34)+chr(34))}"'  # Escape quotes
        config_id = item.config_base_id
        quantity = item.quantity
        unit_price = f"{item.price_fe:.2f}" if item.price_fe is not None else ""
        total_value = f"{item.total_value_fe:.2f}" if item.total_value_fe is not None else ""
        percentage = f"{item.percentage:.2f}" if item.percentage is not None else ""
        lines.append(f"{name},{config_id},{quantity},{unit_price},{total_value},{percentage}")

    # Summary section
    lines.append("")
    lines.append("Summary")
    lines.append(f"Gross Value (FE),{report.total_value_fe:.2f}")
    if report.map_costs_enabled:
        lines.append(f"Map Costs (FE),{report.total_map_cost_fe:.2f}")
    lines.append(f"Profit (FE),{report.profit_fe:.2f}")
    lines.append(f"Runs,{report.run_count}")
    lines.append(f"Total Time (seconds),{report.total_duration_seconds:.0f}")
    lines.append(f"Profit/Hour (FE),{report.profit_per_hour:.2f}")
    lines.append(f"Profit/Map (FE),{report.profit_per_map:.2f}")
    lines.append(f"Unique Items,{report.total_items}")

    csv_content = "\n".join(lines)
    filename = f"titrack-loot-report-{date.today().isoformat()}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
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

    # Check if map costs are enabled
    map_costs_enabled = repo.get_setting("map_costs_enabled") == "true"

    summary = repo.get_run_summary(run.id)
    fe_gained, total_value = repo.get_run_value(run.id)

    # Get costs if enabled
    cost_items = None
    cost_fe = None
    net_value = None
    has_unpriced_costs = False
    if map_costs_enabled:
        cost_summary, cost_value, unpriced = repo.get_run_cost(run.id)
        if cost_summary:
            cost_items = _build_cost_items(cost_summary, repo)
            cost_fe = round(cost_value, 2)
            net_value = round(total_value - cost_value, 2)
            has_unpriced_costs = bool(unpriced)

    is_nightmare = (
        run.level_type == LEVEL_TYPE_NIGHTMARE
        or run.level_type in SUB_ZONE_LEVEL_TYPES
    )
    zone_name = get_zone_display_name(run.zone_signature, run.level_id)
    if run.level_type == LEVEL_TYPE_NIGHTMARE:
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
        map_cost_items=cost_items,
        map_cost_fe=cost_fe,
        map_cost_has_unpriced=has_unpriced_costs,
        net_value_fe=net_value,
    )
