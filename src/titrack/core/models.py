"""Core domain models - dataclasses with no I/O dependencies."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional


class EventContext(Enum):
    """Context in which an item change occurred."""

    PICK_ITEMS = auto()  # Inside PickItems block (loot pickup)
    MAP_OPEN = auto()  # Inside Spv3Open block (map opening costs)
    OTHER = auto()  # Any other context (vendor, stash, etc.)


@dataclass(frozen=True)
class SlotKey:
    """Unique identifier for an inventory slot."""

    page_id: int
    slot_id: int

    def __str__(self) -> str:
        return f"({self.page_id}, {self.slot_id})"


@dataclass
class SlotState:
    """Current state of an inventory slot."""

    page_id: int
    slot_id: int
    config_base_id: int
    num: int
    updated_at: datetime = field(default_factory=datetime.now)
    player_id: Optional[str] = None  # Inventory is per-character

    @property
    def key(self) -> SlotKey:
        return SlotKey(self.page_id, self.slot_id)


@dataclass
class ItemDelta:
    """A change in item quantity."""

    page_id: int
    slot_id: int
    config_base_id: int
    delta: int  # Positive = gain, negative = loss
    context: EventContext
    proto_name: Optional[str]  # e.g., "PickItems"
    run_id: Optional[int]
    timestamp: datetime = field(default_factory=datetime.now)
    season_id: Optional[int] = None  # Season/league for data isolation
    player_id: Optional[str] = None  # Player for data isolation

    @property
    def key(self) -> SlotKey:
        return SlotKey(self.page_id, self.slot_id)


@dataclass
class Run:
    """A single map/zone run."""

    id: Optional[int]  # None until persisted
    zone_signature: str  # Level identifier
    start_ts: datetime
    end_ts: Optional[datetime] = None
    is_hub: bool = False  # True if this is a hub/town zone
    level_id: Optional[int] = None  # For zone differentiation (same path, different areas)
    level_type: Optional[int] = None  # 3=normal, 11=nightmare (Twinightmare mechanic)
    level_uid: Optional[int] = None  # Unique instance ID (for consolidating split runs)
    season_id: Optional[int] = None  # Season/league for data isolation
    player_id: Optional[str] = None  # Player for data isolation

    @property
    def is_active(self) -> bool:
        return self.end_ts is None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.end_ts is None:
            return None
        return (self.end_ts - self.start_ts).total_seconds()


@dataclass
class Item:
    """Item metadata from the item database."""

    config_base_id: int
    name_en: Optional[str]
    name_cn: Optional[str]
    type_cn: Optional[str]
    icon_url: Optional[str]
    url_en: Optional[str]
    url_cn: Optional[str]


@dataclass
class Price:
    """Price entry for an item."""

    config_base_id: int
    price_fe: float  # Value in Flame Elementium
    source: str  # "manual", "import", etc.
    updated_at: datetime = field(default_factory=datetime.now)
    season_id: Optional[int] = None  # Season/league for price isolation


# Parsed event types


@dataclass
class ParsedBagEvent:
    """Parsed BagMgr modification or init event."""

    page_id: int
    slot_id: int
    config_base_id: int
    num: int  # Absolute stack count
    raw_line: str
    is_init: bool = False  # True for InitBagData (snapshot), False for Modfy (change)


@dataclass
class ParsedContextMarker:
    """Parsed ItemChange context marker (start/end of block)."""

    proto_name: str  # e.g., "PickItems"
    is_start: bool  # True for start, False for end
    raw_line: str


@dataclass
class ParsedLevelEvent:
    """Parsed level transition event."""

    event_type: str  # "EnterLevel" or "OpenLevel"
    level_info: str  # Raw level identifier string
    raw_line: str


@dataclass
class ParsedLevelIdEvent:
    """Parsed LevelId event (for zone differentiation)."""

    level_uid: int
    level_type: int
    level_id: int
    raw_line: str


@dataclass
class ParsedPlayerDataEvent:
    """Parsed player data from log (for character detection)."""

    name: Optional[str] = None
    level: Optional[int] = None
    season_id: Optional[int] = None
    hero_id: Optional[int] = None
    player_id: Optional[str] = None
    raw_line: str = ""


# Type alias for any parsed event
ParsedEvent = ParsedBagEvent | ParsedContextMarker | ParsedLevelEvent | ParsedLevelIdEvent | ParsedPlayerDataEvent | None
