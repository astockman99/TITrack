"""Compiled regex patterns for log parsing."""

import re

# BagMgr modification line
# Example: GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 671
BAG_MODIFY_PATTERN = re.compile(
    r"GameLog:\s*Display:\s*\[Game\]\s*BagMgr@:Modfy\s+BagItem\s+"
    r"PageId\s*=\s*(?P<page_id>\d+)\s+"
    r"SlotId\s*=\s*(?P<slot_id>\d+)\s+"
    r"ConfigBaseId\s*=\s*(?P<config_base_id>\d+)\s+"
    r"Num\s*=\s*(?P<num>\d+)"
)

# BagMgr remove line (slot fully cleared, e.g., last item in stack consumed)
# Example: GameLog: Display: [Game] BagMgr@:RemoveBagItem PageId = 103 SlotId = 39
BAG_REMOVE_PATTERN = re.compile(
    r"GameLog:\s*Display:\s*\[Game\]\s*BagMgr@:RemoveBagItem\s+"
    r"PageId\s*=\s*(?P<page_id>\d+)\s+"
    r"SlotId\s*=\s*(?P<slot_id>\d+)"
)

# BagMgr init/snapshot line (triggered by sorting inventory or opening bag)
# Example: GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 609
BAG_INIT_PATTERN = re.compile(
    r"GameLog:\s*Display:\s*\[Game\]\s*BagMgr@:InitBagData\s+"
    r"PageId\s*=\s*(?P<page_id>\d+)\s+"
    r"SlotId\s*=\s*(?P<slot_id>\d+)\s+"
    r"ConfigBaseId\s*=\s*(?P<config_base_id>\d+)\s+"
    r"Num\s*=\s*(?P<num>\d+)"
)

# ItemChange context markers
# Example: GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
# Example: GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
ITEM_CHANGE_PATTERN = re.compile(
    r"GameLog:\s*Display:\s*\[Game\]\s*ItemChange@\s*"
    r"ProtoName=(?P<proto_name>\w+)\s+"
    r"(?P<marker>start|end)"
)

# Level transition events
# Actual format from game logs:
# SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/04DD/DD_ShengTingZhuangYuan000/...
LEVEL_EVENT_PATTERN = re.compile(
    r"SceneLevelMgr@\s+(?P<event_type>OpenMainWorld)\s+END!\s+"
    r"InMainLevelPath\s*=\s*(?P<level_info>.+)"
)

# LevelId extraction (for differentiating zones with same path but different areas)
# Example: GameLog: Display: [Game] LevelMgr@ LevelUid, LevelType, LevelId = 1061006 3 4606
LEVEL_ID_PATTERN = re.compile(
    r"GameLog:\s*Display:\s*\[Game\]\s*LevelMgr@\s+LevelUid,\s*LevelType,\s*LevelId\s*=\s*"
    r"(?P<level_uid>\d+)\s+(?P<level_type>\d+)\s+(?P<level_id>\d+)"
)

# Known hub/town zone patterns (for run segmentation)
# These patterns identify non-mapping zones
# Map paths look like: /Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/...
# Hub/hideout codes: 01SD (Ember's Rest hideout), 04DD, etc.
HUB_ZONE_PATTERNS = [
    re.compile(r"hideout", re.IGNORECASE),
    re.compile(r"town", re.IGNORECASE),
    re.compile(r"hub", re.IGNORECASE),
    re.compile(r"lobby", re.IGNORECASE),
    re.compile(r"social", re.IGNORECASE),
    # Note: /01SD/ and /04DD/ removed - zone codes are shared by hideouts AND maps
    # Hideouts are detected by their specific Chinese names instead
    re.compile(r"YuJinZhiXiBiNanSuo", re.IGNORECASE),  # Ember's Rest (Chinese name)
    re.compile(r"ShengTingZhuangYuan(?!000)", re.IGNORECASE),  # Sacred Court Manor (hideout, but not 000 map)
    re.compile(r"ZhuCheng", re.IGNORECASE),  # Main city
    re.compile(r"/UI/", re.IGNORECASE),  # UI screens (login, etc.)
    re.compile(r"LoginScene", re.IGNORECASE),  # Login screen
]

# Flame Elementium ConfigBaseId (primary currency)
FE_CONFIG_BASE_ID = 100300

# Bound (untradeable) item IDs — always valued at 0 FE.
# Pattern: bound variant = original ConfigBaseId + 1000.
BOUND_ITEM_IDS = frozenset({
    # Flame Fuels (燃料)
    101200,  # Bound Flame Sand (100200)
    101300,  # Bound Flame Elementium (100300)
    # Embers (灰烬)
    201003,  # Bound Fine Ember (200003)
    201028,  # Bound Precious Ember (200028)
    201029,  # Bound Matchless Ember (200029)
    201030,  # Bound Ultimate Ember (200030)
    # Core Currencies (通用道具)
    6011,    # Bound Elixir of Oblivion (5011)
    6028,    # Bound Netherrealm Resonance (5028)
    6029,    # Bound Winding Key (5029)
    6030,    # Bound Twin Reflection (5030)
    6031,    # Bound Sprout of Legends (5031)
    6040,    # Bound Deep Space Resonance (5040)
    6080,    # Bound Energy Core (5080)
})

# Proto names for non-loot inventory changes (trade house, recycling, skill management, etc.).
# These update inventory (slot state) but should NOT create deltas or count as loot.
EXCLUDED_PROTO_NAMES = frozenset({
    "Push2", "XchgReceive", "ExchangeItem", "XchgRecall", "XchgForSale", "UnequipSkill"
})

# Proto names for map cost events (compass/beacon consumption).
MAP_COST_PROTO_NAMES = frozenset({"Spv3Open", "ClimbTowerOpen"})
