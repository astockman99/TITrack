"""Parser for player/character data from the game log."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PlayerInfo:
    """Player/character information parsed from game log."""

    name: str
    level: int
    season_id: int
    hero_id: int
    player_id: Optional[str] = None  # Unique player identifier

    @property
    def season_name(self) -> str:
        """Get human-readable season/league name."""
        return SEASON_NAMES.get(self.season_id, f"Season {self.season_id}")

    @property
    def hero_name(self) -> str:
        """Get human-readable hero/class name."""
        return HERO_NAMES.get(self.hero_id, f"Hero {self.hero_id}")


# Patterns for parsing player data from enter log
# Format: +player+Name [Murat#9371] or |      +Name [Murat#9371]
PLAYER_NAME_PATTERN = re.compile(r"\+player\+Name\s*\[([^\]]+)\]")
PLAYER_SEASON_PATTERN = re.compile(r"\+player\+SeasonId\s*\[(\d+)\]")
PLAYER_HERO_PATTERN = re.compile(r"\+player\+HeroId\s*\[(\d+)\]")
PLAYER_ID_PATTERN = re.compile(r"\+player\+PlayerId\s*\[([^\]]+)\]")

# Level pattern needs to be specific to avoid matching skill levels
# Player level format: |      +Level [95] (pipe, 6 spaces, +Level)
# Skill levels have format: |      |      +2+Level [20] (nested pipes or +N+Level)
PLAYER_LEVEL_PATTERN = re.compile(r"\+player\+Level\s*\[(\d+)\]")

# Alt patterns for pipe-prefixed format (must NOT match nested pipes or +N+Level)
PLAYER_NAME_PATTERN_ALT = re.compile(r"^\|\s{6}\+Name\s*\[([^\]]+)\]")
PLAYER_LEVEL_PATTERN_ALT = re.compile(r"^\|\s{6}\+Level\s*\[(\d+)\]")
PLAYER_SEASON_PATTERN_ALT = re.compile(r"^\|\s{6}\+SeasonId\s*\[(\d+)\]")
PLAYER_HERO_PATTERN_ALT = re.compile(r"^\|\s{6}\+HeroId\s*\[(\d+)\]")
PLAYER_ID_PATTERN_ALT = re.compile(r"^\|\s{6}\+PlayerId\s*\[([^\]]+)\]")


# Season ID to name mapping
# Note: Mapping may need updates as new seasons release
SEASON_NAMES = {
    # Permanent server (non-seasonal)
    1: "Permanent Server",
    # Current season (as of Jan 2026)
    1301: "SS11 Vorax",
    # Add historical seasons as needed
}


# Hero ID to name mapping
HERO_NAMES = {
    1100: "Rehan",
    1200: "Carino",
    1300: "Gemma",
    1400: "Youga",
    1500: "Moto",
    1600: "Iris",
    1700: "Thea",
    1800: "Erika",
    1900: "Bing",
    2000: "Oracle",
    2100: "Leonel",
    2200: "Cateye",
}


def parse_player_line(line: str) -> dict[str, any]:
    """
    Parse a single line for player data fields.

    Args:
        line: A single log line

    Returns:
        Dict with any matched fields: name, level, season_id, hero_id, player_id
    """
    result = {}

    # Try name patterns
    match = PLAYER_NAME_PATTERN.search(line)
    if match:
        result["name"] = match.group(1)
    else:
        match = PLAYER_NAME_PATTERN_ALT.search(line)
        if match:
            result["name"] = match.group(1)

    # Try level patterns
    match = PLAYER_LEVEL_PATTERN.search(line)
    if match:
        result["level"] = int(match.group(1))
    else:
        match = PLAYER_LEVEL_PATTERN_ALT.search(line)
        if match:
            result["level"] = int(match.group(1))

    # Try season patterns
    match = PLAYER_SEASON_PATTERN.search(line)
    if match:
        result["season_id"] = int(match.group(1))
    else:
        match = PLAYER_SEASON_PATTERN_ALT.search(line)
        if match:
            result["season_id"] = int(match.group(1))

    # Try hero patterns
    match = PLAYER_HERO_PATTERN.search(line)
    if match:
        result["hero_id"] = int(match.group(1))
    else:
        match = PLAYER_HERO_PATTERN_ALT.search(line)
        if match:
            result["hero_id"] = int(match.group(1))

    # Try player_id patterns
    match = PLAYER_ID_PATTERN.search(line)
    if match:
        result["player_id"] = match.group(1)
    else:
        match = PLAYER_ID_PATTERN_ALT.search(line)
        if match:
            result["player_id"] = match.group(1)

    return result


def parse_game_log(log_path: Path, from_end: bool = True) -> Optional[PlayerInfo]:
    """
    Parse player info from the main game log file.

    Args:
        log_path: Path to UE_game.log
        from_end: If True, search backwards from end for most recent data

    Returns:
        PlayerInfo if found, None otherwise
    """
    import logging

    logger = logging.getLogger("titrack")

    if not log_path.exists():
        return None

    name: Optional[str] = None
    level: Optional[int] = None
    season_id: Optional[int] = None
    hero_id: Optional[int] = None
    player_id: Optional[str] = None

    # Max bytes to read from end of file (5 MB) to avoid loading huge logs into memory
    MAX_TAIL_BYTES = 5 * 1024 * 1024

    try:
        file_size = log_path.stat().st_size

        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            if from_end:
                if file_size > MAX_TAIL_BYTES:
                    # Seek to near the end to avoid reading entire large file
                    f.seek(file_size - MAX_TAIL_BYTES)
                    f.readline()  # Skip partial line after seek
                lines = f.readlines()
                for line in reversed(lines):
                    parsed = parse_player_line(line)

                    if name is None and "name" in parsed:
                        name = parsed["name"]
                    if level is None and "level" in parsed:
                        level = parsed["level"]
                    if season_id is None and "season_id" in parsed:
                        season_id = parsed["season_id"]
                    if hero_id is None and "hero_id" in parsed:
                        hero_id = parsed["hero_id"]
                    if player_id is None and "player_id" in parsed:
                        player_id = parsed["player_id"]

                    # Stop once we have essential data
                    if name and season_id:
                        break

                # If not found in tail, try reading from the beginning
                if not (name and season_id) and file_size > MAX_TAIL_BYTES:
                    logger.info("Player data not in last 5MB, scanning from start...")
                    f.seek(0)
                    for line in f:
                        parsed = parse_player_line(line)

                        if name is None and "name" in parsed:
                            name = parsed["name"]
                        if season_id is None and "season_id" in parsed:
                            season_id = parsed["season_id"]
                        if level is None and "level" in parsed:
                            level = parsed["level"]
                        if hero_id is None and "hero_id" in parsed:
                            hero_id = parsed["hero_id"]
                        if player_id is None and "player_id" in parsed:
                            player_id = parsed["player_id"]

                        if name and season_id:
                            break
            else:
                # Read forward (for initial parse)
                for line in f:
                    parsed = parse_player_line(line)

                    if name is None and "name" in parsed:
                        name = parsed["name"]
                    if level is None and "level" in parsed:
                        level = parsed["level"]
                    if season_id is None and "season_id" in parsed:
                        season_id = parsed["season_id"]
                    if hero_id is None and "hero_id" in parsed:
                        hero_id = parsed["hero_id"]
                    if player_id is None and "player_id" in parsed:
                        player_id = parsed["player_id"]

                    # Stop once we have all data
                    if all([name, level, season_id, hero_id, player_id]):
                        break

    except Exception as e:
        logger.warning(f"Failed to parse player data from game log: {e}")
        return None

    # Return only if we got the essential data
    if name and season_id:
        return PlayerInfo(
            name=name,
            level=level or 0,
            season_id=season_id,
            hero_id=hero_id or 0,
            player_id=player_id,
        )

    return None


# Legacy alias for backwards compatibility
def parse_enter_log(log_path: Path) -> Optional[PlayerInfo]:
    """Legacy function - now parses from main game log."""
    return parse_game_log(log_path, from_end=True)


def get_enter_log_path(game_log_path: Path) -> Path:
    """
    Get the log path for player data.

    Now returns the main game log path since player data is there.
    """
    return game_log_path


def get_effective_player_id(player_info: Optional[PlayerInfo]) -> Optional[str]:
    """
    Get effective player ID for data isolation.

    If the player_info contains a player_id, use that. Otherwise, construct an
    identifier from season_id and name to ensure different characters
    have separate data tracking.

    Args:
        player_info: PlayerInfo object or None

    Returns:
        Effective player ID string, or None if player_info is None
    """
    if not player_info:
        return None
    if player_info.player_id:
        return player_info.player_id
    # Fallback: use "season_name" as unique identifier
    return f"{player_info.season_id}_{player_info.name}"
