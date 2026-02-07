"""Log line parser - converts raw lines to typed events."""

from titrack.core.models import (
    ParsedBagEvent,
    ParsedBagRemoveEvent,
    ParsedContextMarker,
    ParsedEvent,
    ParsedLevelEvent,
    ParsedLevelIdEvent,
    ParsedPlayerDataEvent,
)
from titrack.parser.patterns import (
    BAG_MODIFY_PATTERN,
    BAG_REMOVE_PATTERN,
    BAG_INIT_PATTERN,
    ITEM_CHANGE_PATTERN,
    LEVEL_EVENT_PATTERN,
    LEVEL_ID_PATTERN,
)
from titrack.parser.player_parser import parse_player_line


def parse_line(line: str) -> ParsedEvent:
    """
    Parse a single log line into a typed event.

    Args:
        line: Raw log line (may include newline)

    Returns:
        ParsedEvent if the line matches a known pattern, None otherwise
    """
    line = line.rstrip("\r\n")

    if not line:
        return None

    # Try BagMgr modification
    match = BAG_MODIFY_PATTERN.search(line)
    if match:
        return ParsedBagEvent(
            page_id=int(match.group("page_id")),
            slot_id=int(match.group("slot_id")),
            config_base_id=int(match.group("config_base_id")),
            num=int(match.group("num")),
            raw_line=line,
            is_init=False,
        )

    # Try BagMgr remove (slot fully cleared, e.g., last item consumed)
    match = BAG_REMOVE_PATTERN.search(line)
    if match:
        return ParsedBagRemoveEvent(
            page_id=int(match.group("page_id")),
            slot_id=int(match.group("slot_id")),
            raw_line=line,
        )

    # Try BagMgr init/snapshot (triggered by sorting inventory)
    match = BAG_INIT_PATTERN.search(line)
    if match:
        return ParsedBagEvent(
            page_id=int(match.group("page_id")),
            slot_id=int(match.group("slot_id")),
            config_base_id=int(match.group("config_base_id")),
            num=int(match.group("num")),
            raw_line=line,
            is_init=True,
        )

    # Try ItemChange context marker
    match = ITEM_CHANGE_PATTERN.search(line)
    if match:
        return ParsedContextMarker(
            proto_name=match.group("proto_name"),
            is_start=match.group("marker") == "start",
            raw_line=line,
        )

    # Try level event
    match = LEVEL_EVENT_PATTERN.search(line)
    if match:
        return ParsedLevelEvent(
            event_type=match.group("event_type"),
            level_info=match.group("level_info").strip(),
            raw_line=line,
        )

    # Try LevelId event (for zone differentiation)
    match = LEVEL_ID_PATTERN.search(line)
    if match:
        return ParsedLevelIdEvent(
            level_uid=int(match.group("level_uid")),
            level_type=int(match.group("level_type")),
            level_id=int(match.group("level_id")),
            raw_line=line,
        )

    # Try player data (for character detection)
    player_data = parse_player_line(line)
    if player_data:
        return ParsedPlayerDataEvent(
            name=player_data.get("name"),
            level=player_data.get("level"),
            season_id=player_data.get("season_id"),
            hero_id=player_data.get("hero_id"),
            player_id=player_data.get("player_id"),
            raw_line=line,
        )

    return None


def parse_lines(lines: list[str]) -> list[ParsedEvent]:
    """
    Parse multiple log lines.

    Args:
        lines: List of raw log lines

    Returns:
        List of parsed events (None values filtered out)
    """
    events = [parse_line(line) for line in lines]
    return [e for e in events if e is not None]
