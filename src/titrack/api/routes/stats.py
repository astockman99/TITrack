"""Stats API routes for time-series data."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query

from pydantic import BaseModel

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


class TimeSeriesResponse(BaseModel):
    """Time series data for charts."""

    cumulative_value: list[TimeSeriesPoint]  # Total value over time
    value_per_hour: list[TimeSeriesPoint]  # Value/hour rate over time
    cumulative_fe: list[TimeSeriesPoint]  # Raw FE over time (legacy)


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

    # Calculate cumulative value at each run completion
    cumulative_value_points = []
    cumulative_fe_points = []
    cumulative_value = 0.0
    cumulative_fe = 0

    # Pre-calculate run values for efficiency
    run_values = {}
    for run in runs:
        fe_gained, total_value = repo.get_run_value(run.id)
        run_values[run.id] = (fe_gained, total_value)

    for run in runs:
        fe_gained, total_value = run_values[run.id]
        cumulative_fe += fe_gained
        cumulative_value += total_value
        cumulative_value_points.append(
            TimeSeriesPoint(timestamp=run.end_ts, value=round(cumulative_value, 2))
        )
        cumulative_fe_points.append(
            TimeSeriesPoint(timestamp=run.end_ts, value=cumulative_fe)
        )

    # Calculate rolling value/hour (using 1-hour windows)
    value_per_hour_points = []
    window_minutes = 60

    for i, run in enumerate(runs):
        # Find runs in the last hour window
        window_start = run.end_ts - timedelta(minutes=window_minutes)
        window_runs = [
            r for r in runs[:i+1]
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
            if window_duration > 0:
                value_rate = (window_value / window_duration) * 3600
            else:
                value_rate = 0

            value_per_hour_points.append(
                TimeSeriesPoint(timestamp=run.end_ts, value=round(value_rate, 2))
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
    )
