"""Collector diagnostics endpoint.

Powers the character-detection panel on the dashboard, which replaces the old
generic "Waiting for character detection..." message. The panel uses the
returned fields to render one of several targeted messages (log missing,
stale log, newer candidate found elsewhere, etc.) so users can self-diagnose
the common failure modes without a support request.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from titrack.config.settings import find_all_log_files

router = APIRouter(prefix="/api/collector", tags=["collector"])


# Content markers we recognise in a TI log. "GameLog:" is the pre-SS12 prefix;
# "TLLua:" / "TLShipping:" are the post-SS12 Lunaria prefixes. "LevelMgr@" is
# an event marker that appears under both prefixes.
_TI_LOG_MARKERS = (b"TLLua:", b"TLShipping:", b"GameLog:", b"LevelMgr@")

# How much of the file tail to sniff for markers. 64 KB is enough to cover a
# handful of recent events on even a quiet log, and cheap to read.
_SNIFF_BYTES = 64 * 1024


class CandidateLog(BaseModel):
    """Another UE_game.log that exists on disk."""

    path: str
    size_bytes: int
    last_modified_iso: Optional[str]
    seconds_since_modified: Optional[int]


class CollectorDiagnoseResponse(BaseModel):
    log_path: Optional[str]
    log_path_configured: bool
    log_exists: bool
    log_size_bytes: Optional[int]
    log_last_modified_iso: Optional[str]
    log_seconds_since_modified: Optional[int]
    looks_like_ti_log: Optional[bool]
    tailer_position: Optional[int]
    tailer_bytes_behind: Optional[int]
    player_lines_seen: bool
    player_detected: bool
    other_candidates: list[CandidateLog]


def _mtime_fields(path: Path) -> tuple[Optional[str], Optional[int]]:
    """Return (ISO-8601 mtime, seconds since mtime) for a path, or (None, None)."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None, None
    iso = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    seconds = int(max(0, datetime.now(tz=timezone.utc).timestamp() - mtime))
    return iso, seconds


def _looks_like_ti_log(path: Path, size: int) -> Optional[bool]:
    """Heuristic: does the tail of the file contain known TI log markers."""
    if size <= 0:
        return None
    try:
        with open(path, "rb") as f:
            if size > _SNIFF_BYTES:
                f.seek(size - _SNIFF_BYTES)
            sample = f.read(_SNIFF_BYTES)
    except OSError:
        return None
    return any(marker in sample for marker in _TI_LOG_MARKERS)


@router.get("/diagnose", response_model=CollectorDiagnoseResponse)
def diagnose_collector(request: Request) -> CollectorDiagnoseResponse:
    """
    Return diagnostic info for the character-detection panel.

    The values here are sampled on demand (no persistent state), so callers can
    poll this every few seconds while awaiting detection without worrying about
    stale data.
    """
    state = request.app.state
    log_path: Optional[Path] = getattr(state, "log_path", None)
    collector = getattr(state, "collector", None)
    player_info = getattr(state, "player_info", None)

    log_path_configured = log_path is not None
    log_exists = False
    log_size_bytes: Optional[int] = None
    log_last_modified_iso: Optional[str] = None
    log_seconds_since_modified: Optional[int] = None
    looks_like_ti_log: Optional[bool] = None

    if log_path is not None:
        try:
            log_exists = log_path.exists() and log_path.is_file()
        except OSError:
            log_exists = False

        if log_exists:
            try:
                log_size_bytes = os.path.getsize(log_path)
            except OSError:
                log_size_bytes = None
            log_last_modified_iso, log_seconds_since_modified = _mtime_fields(log_path)
            if log_size_bytes is not None:
                looks_like_ti_log = _looks_like_ti_log(log_path, log_size_bytes)

    tailer_position: Optional[int] = None
    tailer_bytes_behind: Optional[int] = None
    if collector is not None and hasattr(collector, "tailer"):
        tailer = collector.tailer
        try:
            tailer_position = int(tailer.position)
        except (AttributeError, TypeError):
            tailer_position = None
        if log_size_bytes is not None and tailer_position is not None:
            tailer_bytes_behind = max(0, log_size_bytes - tailer_position)

    player_lines_seen = bool(
        collector is not None
        and getattr(collector, "_player_data_last_update", None) is not None
    )
    player_detected = player_info is not None

    # Enumerate other log files on disk that we're NOT currently watching.
    other_candidates: list[CandidateLog] = []
    current_resolved: Optional[Path] = None
    if log_path is not None:
        try:
            current_resolved = log_path.resolve()
        except OSError:
            current_resolved = log_path

    for candidate in find_all_log_files():
        try:
            candidate_resolved = candidate.resolve()
        except OSError:
            candidate_resolved = candidate
        if current_resolved is not None and candidate_resolved == current_resolved:
            continue
        try:
            size = os.path.getsize(candidate)
        except OSError:
            continue
        iso, seconds = _mtime_fields(candidate)
        other_candidates.append(
            CandidateLog(
                path=str(candidate),
                size_bytes=size,
                last_modified_iso=iso,
                seconds_since_modified=seconds,
            )
        )

    # Newest candidate first so the UI can highlight the most promising switch.
    other_candidates.sort(
        key=lambda c: c.seconds_since_modified if c.seconds_since_modified is not None else 10**12
    )

    return CollectorDiagnoseResponse(
        log_path=str(log_path) if log_path else None,
        log_path_configured=log_path_configured,
        log_exists=log_exists,
        log_size_bytes=log_size_bytes,
        log_last_modified_iso=log_last_modified_iso,
        log_seconds_since_modified=log_seconds_since_modified,
        looks_like_ti_log=looks_like_ti_log,
        tailer_position=tailer_position,
        tailer_bytes_behind=tailer_bytes_behind,
        player_lines_seen=player_lines_seen,
        player_detected=player_detected,
        other_candidates=other_candidates,
    )
