"""Configuration and settings management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Common game installation locations (Steam and standalone client)
GAME_PATHS = [
    # Steam library locations
    Path("C:/Program Files (x86)/Steam/steamapps/common/Torchlight Infinite"),
    Path("C:/Program Files/Steam/steamapps/common/Torchlight Infinite"),
    Path("D:/Steam/steamapps/common/Torchlight Infinite"),
    Path("D:/SteamLibrary/steamapps/common/Torchlight Infinite"),
    Path("E:/Steam/steamapps/common/Torchlight Infinite"),
    Path("E:/SteamLibrary/steamapps/common/Torchlight Infinite"),
    Path("F:/Steam/steamapps/common/Torchlight Infinite"),
    Path("F:/SteamLibrary/steamapps/common/Torchlight Infinite"),
    Path("G:/Steam/steamapps/common/Torchlight Infinite"),
    Path("G:/SteamLibrary/steamapps/common/Torchlight Infinite"),
    # Standalone client locations
    Path("C:/Program Files (x86)/Torchlight Infinite"),
    Path("C:/Program Files/Torchlight Infinite"),
    Path("D:/Torchlight Infinite"),
    Path("E:/Torchlight Infinite"),
]

# Keep for backwards compatibility
STEAM_PATHS = GAME_PATHS

# Relative paths to log file within game directory
# Steam version uses UE_Game directly, standalone client has Game/UE_game
# Note: Windows is case-insensitive, but we include variations for clarity
LOG_RELATIVE_PATHS = [
    Path("UE_Game/Torchlight/Saved/Logs/UE_game.log"),  # Steam (common)
    Path("UE_game/TorchLight/Saved/Logs/UE_game.log"),  # Steam (alternate capitalization)
    Path("Game/UE_game/Torchlight/Saved/Logs/UE_game.log"),  # Standalone client
]

# Keep for backwards compatibility
LOG_RELATIVE_PATH = LOG_RELATIVE_PATHS[0]

# Log file name
LOG_FILE_NAME = "UE_game.log"


def resolve_log_path(user_path: str) -> Optional[Path]:
    """
    Intelligently resolve a user-provided path to the log file.

    Handles various user inputs:
    - Direct path to UE_game.log file
    - Path to Logs directory
    - Path to any parent directory (Saved, Torchlight, UE_Game, game root, etc.)

    Args:
        user_path: Any path the user provides

    Returns:
        Path to log file if found, None otherwise
    """
    path = Path(user_path)

    if not path.exists():
        return None

    # Case 1: User pointed directly to the log file
    if path.is_file() and path.name.lower() == LOG_FILE_NAME.lower():
        return path

    # Case 2: User pointed to a directory - try to find the log file
    if path.is_dir():
        # Check if log file is directly in this directory (e.g., user pointed to Logs folder)
        direct_log = path / LOG_FILE_NAME
        if direct_log.exists():
            return direct_log

        # Try appending known relative paths (user pointed to game root)
        for relative_path in LOG_RELATIVE_PATHS:
            log_path = path / relative_path
            if log_path.exists():
                return log_path

        # Try partial path matching - user might have pointed to an intermediate directory
        # e.g., UE_Game, Torchlight, Saved, etc.
        # Build possible suffixes from the relative paths
        for relative_path in LOG_RELATIVE_PATHS:
            parts = relative_path.parts  # e.g., ('UE_Game', 'Torchlight', 'Saved', 'Logs', 'UE_game.log')
            # Try matching from each part of the relative path
            for i, part in enumerate(parts[:-1]):  # Exclude the filename
                if path.name.lower() == part.lower():
                    # User pointed to this directory, append the rest
                    remaining = Path(*parts[i + 1 :])
                    log_path = path / remaining
                    if log_path.exists():
                        return log_path

    return None


def find_log_file(custom_game_dir: Optional[str] = None) -> Optional[Path]:
    """
    Auto-detect the game log file location.

    Checks custom directory first (if provided), then common Steam library locations.
    Supports both Steam and standalone client folder structures.
    Handles flexible user input (game root, log directory, or log file path).

    Args:
        custom_game_dir: Custom path to check first (can be game root, log dir, or log file)

    Returns:
        Path to log file if found, None otherwise
    """
    # Check custom directory first if provided (with smart resolution)
    if custom_game_dir:
        resolved = resolve_log_path(custom_game_dir)
        if resolved:
            return resolved

    # Fall back to common game installation paths (try all relative paths for each)
    for game_path in GAME_PATHS:
        for relative_path in LOG_RELATIVE_PATHS:
            log_path = game_path / relative_path
            if log_path.exists():
                return log_path
    return None


def validate_game_directory(game_dir: str) -> tuple[bool, Optional[Path]]:
    """
    Validate that a path can be resolved to the game log file.

    Handles flexible user input:
    - Game installation root directory
    - Direct path to the log file
    - Path to the Logs directory
    - Path to any intermediate directory (UE_Game, Torchlight, Saved, etc.)

    Supports both Steam and standalone client folder structures.

    Args:
        game_dir: Path provided by user (can be game root, log dir, or log file)

    Returns:
        Tuple of (is_valid, log_path) where log_path is the full path if valid
    """
    log_path = resolve_log_path(game_dir)
    if log_path:
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
        Path to data/tracker.db beside the executable
    """
    from titrack.config.paths import get_app_dir
    return get_app_dir() / "data" / "tracker.db"


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
