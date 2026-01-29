"""Configuration and settings management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Common Steam library locations
STEAM_PATHS = [
    Path("C:/Program Files (x86)/Steam/steamapps/common/Torchlight Infinite"),
    Path("C:/Program Files/Steam/steamapps/common/Torchlight Infinite"),
    Path("D:/Steam/steamapps/common/Torchlight Infinite"),
    Path("D:/SteamLibrary/steamapps/common/Torchlight Infinite"),
    Path("E:/SteamLibrary/steamapps/common/Torchlight Infinite"),
]

# Relative path to log file within game directory
LOG_RELATIVE_PATH = Path("UE_Game/Torchlight/Saved/Logs/UE_game.log")


def find_log_file(custom_game_dir: Optional[str] = None) -> Optional[Path]:
    """
    Auto-detect the game log file location.

    Checks custom directory first (if provided), then common Steam library locations.

    Args:
        custom_game_dir: Custom game installation directory to check first

    Returns:
        Path to log file if found, None otherwise
    """
    # Check custom directory first if provided
    if custom_game_dir:
        custom_path = Path(custom_game_dir) / LOG_RELATIVE_PATH
        if custom_path.exists():
            return custom_path

    # Fall back to common Steam paths
    for steam_path in STEAM_PATHS:
        log_path = steam_path / LOG_RELATIVE_PATH
        if log_path.exists():
            return log_path
    return None


def validate_game_directory(game_dir: str) -> tuple[bool, Optional[Path]]:
    """
    Validate that a directory contains the game log file.

    Args:
        game_dir: Path to the game installation directory

    Returns:
        Tuple of (is_valid, log_path) where log_path is the full path if valid
    """
    game_path = Path(game_dir)
    if not game_path.exists():
        return False, None

    log_path = game_path / LOG_RELATIVE_PATH
    if log_path.exists():
        return True, log_path

    return False, None


def get_default_db_path() -> Path:
    """
    Get the default database path.

    Uses %LOCALAPPDATA%/TITrack/tracker.db on Windows.
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "TITrack" / "tracker.db"
    # Fallback
    return Path.home() / ".titrack" / "tracker.db"


def get_portable_db_path() -> Path:
    """
    Get the portable database path (beside executable).

    Returns:
        Path to data/tracker.db in current directory
    """
    return Path.cwd() / "data" / "tracker.db"


@dataclass
class Settings:
    """Application settings."""

    # Path to game log file
    log_path: Optional[Path] = None

    # Path to database file
    db_path: Path = field(default_factory=get_default_db_path)

    # Use portable mode (data beside exe)
    portable: bool = False

    # Poll interval for log tailing (seconds)
    poll_interval: float = 0.5

    # Item seed file path
    seed_file: Optional[Path] = None

    def __post_init__(self) -> None:
        """Apply portable mode if enabled."""
        if self.portable:
            self.db_path = get_portable_db_path()

        # Auto-detect log path if not set
        if self.log_path is None:
            self.log_path = find_log_file()

    @classmethod
    def from_args(
        cls,
        log_path: Optional[str] = None,
        db_path: Optional[str] = None,
        portable: bool = False,
        seed_file: Optional[str] = None,
    ) -> "Settings":
        """
        Create settings from CLI arguments.

        Args:
            log_path: Override log file path
            db_path: Override database path
            portable: Use portable mode
            seed_file: Path to item seed file
        """
        return cls(
            log_path=Path(log_path) if log_path else None,
            db_path=Path(db_path) if db_path else get_default_db_path(),
            portable=portable,
            seed_file=Path(seed_file) if seed_file else None,
        )

    def validate(self) -> list[str]:
        """
        Validate settings.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if self.log_path and not self.log_path.exists():
            errors.append(f"Log file not found: {self.log_path}")

        if self.seed_file and not self.seed_file.exists():
            errors.append(f"Seed file not found: {self.seed_file}")

        return errors
