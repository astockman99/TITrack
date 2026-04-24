"""Resource path resolution for frozen (PyInstaller) and source modes."""

import os
import sys
from pathlib import Path
from typing import Optional


def is_frozen() -> bool:
    """Check if running as a PyInstaller frozen executable."""
    return getattr(sys, "frozen", False)


_CLOUD_SYNC_MARKERS = (
    ("onedrive", "OneDrive"),
    ("dropbox", "Dropbox"),
    ("google drive", "Google Drive"),
    ("googledrive", "Google Drive"),
    ("icloud drive", "iCloud Drive"),
    ("iclouddrive", "iCloud Drive"),
    ("pclouddrive", "pCloud"),
    ("box sync", "Box"),
    ("mega sync", "MEGA"),
    ("megasync", "MEGA"),
)


def detect_install_path_issue() -> Optional[tuple[str, str]]:
    """
    Detect install locations known to break auto-updates.

    Returns a (kind, display_name) tuple describing the problem, or None if the
    install path looks fine. `kind` is "cloud" or "program_files"; `display_name`
    is the service/location name for user-facing messages.

    Only meaningful in frozen mode — dev runs return None.
    """
    if not is_frozen():
        return None

    path_segments = [p.lower() for p in Path(sys.executable).parent.parts]

    for needle, name in _CLOUD_SYNC_MARKERS:
        for segment in path_segments:
            # OneDrive Business folders are "OneDrive - CompanyName"; match prefix too.
            if segment == needle or segment.startswith(needle + " -") or segment.startswith(needle + "-"):
                return ("cloud", name)

    app_path_lower = str(Path(sys.executable).parent).lower()
    for env_key in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        protected = os.environ.get(env_key)
        if protected and app_path_lower.startswith(protected.lower()):
            return ("program_files", "Program Files")

    return None


def get_install_path_warning() -> Optional[str]:
    """
    Human-readable warning string if the install location will break auto-updates.

    Returns None if the install path looks fine or we're running from source.
    """
    issue = detect_install_path_issue()
    if not issue:
        return None

    kind, name = issue
    if kind == "cloud":
        return (
            f"TITrack is installed inside a {name}-synced folder. Auto-updates may be "
            f"silently reverted when {name} re-syncs from the cloud, leaving you on "
            f"the old version. Reinstall to a non-synced location (e.g. C:\\TITrack) "
            f"for updates to stick."
        )
    if kind == "program_files":
        return (
            "TITrack is installed inside Program Files. Auto-updates may fail or be "
            "silently redirected by Windows UAC, leaving you on the old version. "
            "Reinstall to a location like C:\\TITrack or %LOCALAPPDATA%\\TITrack."
        )
    return None


def get_app_dir() -> Path:
    """
    Get the application directory.

    In frozen mode: directory containing the exe
    In source mode: project root (contains src/, pyproject.toml)
    """
    if is_frozen():
        # Frozen: exe is in dist/TITrack/TITrack.exe
        return Path(sys.executable).parent
    else:
        # Source: this file is at src/titrack/config/paths.py
        # Project root is 4 levels up
        return Path(__file__).resolve().parents[3]


def get_internal_dir() -> Path:
    """
    Get the _internal directory for PyInstaller 6.x bundled files.

    In frozen mode: _internal subdirectory beside exe
    In source mode: project root (same as app_dir)
    """
    if is_frozen():
        # PyInstaller 6.x puts bundled data files in _internal
        return get_app_dir() / "_internal"
    else:
        return get_app_dir()


def get_resource_path(relative_path: str) -> Path:
    """
    Get the absolute path to a bundled resource file.

    Args:
        relative_path: Path relative to app directory (e.g., "tlidb_items_seed_en.json")

    Returns:
        Absolute path to the resource file
    """
    if is_frozen():
        # PyInstaller 6.x: bundled files are in _internal directory
        return get_internal_dir() / relative_path
    else:
        return get_app_dir() / relative_path


def get_data_dir(portable: bool = False) -> Path:
    """
    Get the data directory for storing database and user files.

    Args:
        portable: If True, use ./data beside the executable

    Returns:
        Path to data directory (created if needed)
    """
    if portable or is_frozen():
        # Portable mode or frozen: data beside exe
        data_dir = get_app_dir() / "data"
    else:
        # Development: use user's local app data
        import os

        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            data_dir = Path(local_app_data) / "TITracker"
        else:
            # Fallback to beside app
            data_dir = get_app_dir() / "data"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_static_dir() -> Path:
    """
    Get the directory containing static web files.

    Returns:
        Path to static files directory
    """
    if is_frozen():
        # Frozen: static files bundled at _internal/titrack/web/static/
        return get_internal_dir() / "titrack" / "web" / "static"
    else:
        # Source: src/titrack/web/static/
        return Path(__file__).resolve().parent.parent / "web" / "static"


def get_items_seed_path() -> Path:
    """
    Get the path to the items seed JSON file.

    Returns:
        Path to tlidb_items_seed_en.json
    """
    return get_resource_path("tlidb_items_seed_en.json")
