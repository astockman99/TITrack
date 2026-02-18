"""Stats API routes for time-series data."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query

from pydantic import BaseModel

from titrack.data.zones import get_zone_display_name
from titrack.db.repository import Repository
from titrack.parser.patterns import FE_CONFIG_BASE_ID

router = APIRouter(prefix="/api/stats", tags=["stats"])


def get_repository() -> Repository:
    """Dependency injection for repository - set by app factory."""
    raise NotImplementedError("Repository not configured")


class TimeSeriesPoint(BaseModel):
    """Single point in time series."""

    timestamp: datetime
    value: float
    cumulative_seconds: float = 0  # Running sum of in-map time


class TimeSeriesResponse(BaseModel):
    """Time series data for charts."""

    cumulative_value: list[TimeSeriesPoint]  # Total value over time
    value_per_hour: list[TimeSeriesPoint]  # Value/hour rate over time
    cumulative_fe: list[TimeSeriesPoint]  # Raw FE over time (legacy)
    realtime_tracking: bool = False  # Whether realtime tracking is enabled


@router.get("/history", response_model=TimeSeriesResponse)
def get_stats_history(
    hours: int = Query(24, ge=1, le=168, description="Hours of history to return"),
    repo: Repository = Depends(get_repository),
) -> TimeSeriesResponse:
    """
    Get time-series stats for charting.

    Returns cumulative value and rolling value/hour over time.
    Values include FE + priced items.
    """
    # Get all non-hub runs
    all_runs = repo.get_recent_runs(limit=10000)
    runs = [r for r in all_runs if not r.is_hub and r.end_ts is not None]
    runs.sort(key=lambda r: r.start_ts)  # Oldest first

    if not runs:
        return TimeSeriesResponse(
            cumulative_value=[],
            value_per_hour=[],
            cumulative_fe=[],
        )

    # Load ignored state
    ignored_run_ids = repo.get_ignored_run_ids()

    # Check if map costs are enabled (to match stats header behavior)
    map_costs_enabled = repo.get_setting("map_costs_enabled") == "true"

    # Calculate cumulative value at each run completion
    cumulative_value_points = []
    cumulative_fe_points = []
    cumulative_value = 0.0
    cumulative_fe = 0
    cumulative_map_seconds = 0.0

    # Load all ignored items (bulk query)
    all_ignored_items = repo.get_all_ignored_items()

    # Pre-calculate run values for efficiency (skip ignored runs)
    run_values = {}
    for run in runs:
        if run.id in ignored_run_ids:
            continue
        fe_gained, total_value = repo.get_run_value(run.id)
        # Subtract ignored item values
        ignored_items = all_ignored_items.get(run.id)
        if ignored_items:
            ignored_value = repo.get_ignored_item_value(run.id, ignored_items)
            total_value -= ignored_value
        # Subtract map costs if enabled
        if map_costs_enabled:
            _, cost_value, _ = repo.get_run_cost(run.id)
            total_value -= cost_value
        run_values[run.id] = (fe_gained, total_value)

    for run in runs:
        if run.id in ignored_run_ids:
            continue
        fe_gained, total_value = run_values[run.id]
        cumulative_fe += fe_gained
        cumulative_value += total_value
        if run.duration_seconds:
            cumulative_map_seconds += run.duration_seconds
        cumulative_value_points.append(
            TimeSeriesPoint(
                timestamp=run.end_ts,
                value=round(cumulative_value, 2),
                cumulative_seconds=cumulative_map_seconds,
            )
        )
        cumulative_fe_points.append(
            TimeSeriesPoint(
                timestamp=run.end_ts,
                value=cumulative_fe,
                cumulative_seconds=cumulative_map_seconds,
            )
        )

    # Check realtime tracking mode
    realtime_enabled = repo.get_setting("realtime_tracking_enabled") == "true"

    # Calculate rolling value/hour (using 1-hour windows)
    value_per_hour_points = []
    window_minutes = 60

    # Filter runs for rolling calculation (exclude ignored)
    non_ignored_runs = [r for r in runs if r.id not in ignored_run_ids]

    # Pre-compute cumulative in-map seconds for value_per_hour points
    vph_cumulative_seconds = 0.0

    for i, run in enumerate(non_ignored_runs):
        if run.duration_seconds:
            vph_cumulative_seconds += run.duration_seconds

        # Find runs in the last hour window
        window_start = run.end_ts - timedelta(minutes=window_minutes)
        window_runs = [
            r for r in non_ignored_runs[:i+1]
            if r.end_ts and r.end_ts >= window_start
        ]

        if window_runs:
            # Sum value in window
            window_value = 0.0
            window_duration = 0.0
            for wr in window_runs:
                _, total_value = run_values[wr.id]
                window_value += total_value
                if wr.duration_seconds:
                    window_duration += wr.duration_seconds

            # Calculate rate (value per hour)
            if realtime_enabled and len(window_runs) >= 2:
                # Use wall-clock window duration instead of summed run durations
                wall_duration = (run.end_ts - window_runs[0].start_ts).total_seconds()
                if wall_duration > 0:
                    value_rate = (window_value / wall_duration) * 3600
                else:
                    value_rate = 0
            elif window_duration > 0:
                value_rate = (window_value / window_duration) * 3600
            else:
                value_rate = 0

            value_per_hour_points.append(
                TimeSeriesPoint(
                    timestamp=run.end_ts,
                    value=round(value_rate, 2),
                    cumulative_seconds=vph_cumulative_seconds,
                )
            )

    # Filter to requested time window
    cutoff = datetime.now() - timedelta(hours=hours)

    filtered_cumulative_value = [p for p in cumulative_value_points if p.timestamp >= cutoff]
    filtered_value_rate = [p for p in value_per_hour_points if p.timestamp >= cutoff]
    filtered_cumulative_fe = [p for p in cumulative_fe_points if p.timestamp >= cutoff]

    return TimeSeriesResponse(
        cumulative_value=filtered_cumulative_value,
        value_per_hour=filtered_value_rate,
        cumulative_fe=filtered_cumulative_fe,
        realtime_tracking=realtime_enabled,
    )


class ZoneInfo(BaseModel):
    """Zone information."""

    zone_signature: str
    display_name: str
    needs_translation: bool


class ZonesResponse(BaseModel):
    """List of zones."""

    zones: list[ZoneInfo]
    total: int
    untranslated: int


@router.get("/zones", response_model=ZonesResponse)
def get_zones(
    repo: Repository = Depends(get_repository),
) -> ZonesResponse:
    """Get all unique zones encountered with their display names."""
    zone_signatures = repo.get_unique_zones()

    zones = []
    untranslated = 0

    for sig in zone_signatures:
        display = get_zone_display_name(sig)
        # Check if it's untranslated (contains underscore or Chinese chars)
        needs_trans = "_" in display or any('\u4e00' <= c <= '\u9fff' for c in display)
        if needs_trans:
            untranslated += 1
        zones.append(ZoneInfo(
            zone_signature=sig,
            display_name=display,
            needs_translation=needs_trans,
        ))

    return ZonesResponse(
        zones=zones,
        total=len(zones),
        untranslated=untranslated,
    )
