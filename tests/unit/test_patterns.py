"""Tests for regex patterns."""

import pytest

from titrack.parser.patterns import (
    BAG_MODIFY_PATTERN,
    BAG_INIT_PATTERN,
    ITEM_CHANGE_PATTERN,
    LEVEL_EVENT_PATTERN,
    LEVEL_ID_PATTERN,
    HUB_ZONE_PATTERNS,
)


class TestBagModifyPattern:
    """Tests for BagMgr modification pattern."""

    def test_matches_standard_line(self):
        line = "GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 671"
        match = BAG_MODIFY_PATTERN.search(line)
        assert match is not None
        assert match.group("page_id") == "102"
        assert match.group("slot_id") == "0"
        assert match.group("config_base_id") == "100300"
        assert match.group("num") == "671"

    def test_matches_different_values(self):
        line = "GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 1 SlotId = 99 ConfigBaseId = 999999 Num = 12345"
        match = BAG_MODIFY_PATTERN.search(line)
        assert match is not None
        assert match.group("page_id") == "1"
        assert match.group("slot_id") == "99"
        assert match.group("config_base_id") == "999999"
        assert match.group("num") == "12345"

    def test_no_match_on_unrelated_line(self):
        line = "GameLog: Display: [Game] SomeOtherEvent"
        match = BAG_MODIFY_PATTERN.search(line)
        assert match is None

    def test_matches_with_prefix(self):
        line = "[2026.01.26-10.00.00:000][  0]GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 500"
        match = BAG_MODIFY_PATTERN.search(line)
        assert match is not None
        assert match.group("num") == "500"


class TestBagInitPattern:
    """Tests for BagMgr init/snapshot pattern."""

    def test_matches_standard_line(self):
        line = "GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 609"
        match = BAG_INIT_PATTERN.search(line)
        assert match is not None
        assert match.group("page_id") == "102"
        assert match.group("slot_id") == "0"
        assert match.group("config_base_id") == "100300"
        assert match.group("num") == "609"

    def test_matches_different_page_ids(self):
        # PageId 100 = equipment, 101 = skills, 102 = consumables, 103 = misc
        line = "GameLog: Display: [Game] BagMgr@:InitBagData PageId = 103 SlotId = 57 ConfigBaseId = 6153 Num = 14"
        match = BAG_INIT_PATTERN.search(line)
        assert match is not None
        assert match.group("page_id") == "103"
        assert match.group("slot_id") == "57"
        assert match.group("config_base_id") == "6153"
        assert match.group("num") == "14"

    def test_no_match_on_modify_line(self):
        line = "GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 671"
        match = BAG_INIT_PATTERN.search(line)
        assert match is None

    def test_matches_with_timestamp_prefix(self):
        line = "[2026.01.27-12.36.57:776][ 65]GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 609"
        match = BAG_INIT_PATTERN.search(line)
        assert match is not None
        assert match.group("num") == "609"


class TestItemChangePattern:
    """Tests for ItemChange context marker pattern."""

    def test_matches_start_marker(self):
        line = "GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start"
        match = ITEM_CHANGE_PATTERN.search(line)
        assert match is not None
        assert match.group("proto_name") == "PickItems"
        assert match.group("marker") == "start"

    def test_matches_end_marker(self):
        line = "GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end"
        match = ITEM_CHANGE_PATTERN.search(line)
        assert match is not None
        assert match.group("proto_name") == "PickItems"
        assert match.group("marker") == "end"

    def test_matches_other_proto_name(self):
        line = "GameLog: Display: [Game] ItemChange@ ProtoName=SellItems start"
        match = ITEM_CHANGE_PATTERN.search(line)
        assert match is not None
        assert match.group("proto_name") == "SellItems"

    def test_no_match_without_marker(self):
        line = "GameLog: Display: [Game] ItemChange@ ProtoName=PickItems"
        match = ITEM_CHANGE_PATTERN.search(line)
        assert match is None


class TestLevelEventPattern:
    """Tests for level transition event pattern."""

    def test_matches_open_main_world(self):
        line = "SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/XZ_YuJinZhiXiBiNanSuo200"
        match = LEVEL_EVENT_PATTERN.search(line)
        assert match is not None
        assert match.group("event_type") == "OpenMainWorld"
        assert "/Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200" in match.group("level_info")

    def test_matches_map_zone(self):
        line = "SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/02KD/KD_YuanSuKuangDong000/KD_YuanSuKuangDong000"
        match = LEVEL_EVENT_PATTERN.search(line)
        assert match is not None
        assert match.group("event_type") == "OpenMainWorld"
        assert "KD_YuanSuKuangDong000" in match.group("level_info")

    def test_no_match_on_other_scene_events(self):
        line = "SceneLevelMgr@ OpenSubWorld STT!"
        match = LEVEL_EVENT_PATTERN.search(line)
        assert match is None


class TestLevelIdPattern:
    """Tests for LevelId extraction pattern."""

    def test_matches_level_id_line(self):
        line = "GameLog: Display: [Game] LevelMgr@ LevelUid, LevelType, LevelId = 1061006 3 4606"
        match = LEVEL_ID_PATTERN.search(line)
        assert match is not None
        assert match.group("level_uid") == "1061006"
        assert match.group("level_type") == "3"
        assert match.group("level_id") == "4606"

    def test_matches_different_values(self):
        line = "GameLog: Display: [Game] LevelMgr@ LevelUid, LevelType, LevelId = 1061406 3 4654"
        match = LEVEL_ID_PATTERN.search(line)
        assert match is not None
        assert match.group("level_uid") == "1061406"
        assert match.group("level_id") == "4654"

    def test_no_match_on_other_level_mgr_line(self):
        line = "GameLog: Display: [Game] LevelMgr@:LevelPath, Model = Content/Art/Maps/03YL/YL_BeiFengLinDi201"
        match = LEVEL_ID_PATTERN.search(line)
        assert match is None


class TestHubZonePatterns:
    """Tests for hub/town zone detection patterns."""

    def test_detects_hub(self):
        assert any(p.search("MainHub_Social") for p in HUB_ZONE_PATTERNS)

    def test_detects_town(self):
        assert any(p.search("Town_Start") for p in HUB_ZONE_PATTERNS)

    def test_detects_hideout(self):
        assert any(p.search("Player_Hideout_01") for p in HUB_ZONE_PATTERNS)

    def test_detects_embers_rest_by_path(self):
        # Ember's Rest hideout detected by name, not zone code
        assert any(p.search("/Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200") for p in HUB_ZONE_PATTERNS)

    def test_does_not_match_dragonrest_cavern(self):
        # Dragonrest Cavern uses 01SD code but should NOT be detected as hub
        assert not any(p.search("/Game/Art/Maps/01SD/SD_ShouGuSiDi000") for p in HUB_ZONE_PATTERNS)

    def test_detects_embers_rest_by_name(self):
        assert any(p.search("YuJinZhiXiBiNanSuo") for p in HUB_ZONE_PATTERNS)

    def test_does_not_match_map(self):
        assert not any(p.search("Map_Desert_T16_001") for p in HUB_ZONE_PATTERNS)

    def test_does_not_match_map_zone_path(self):
        # Map zones like 02KD should not be detected as hub
        assert not any(p.search("/Game/Art/Maps/02KD/KD_YuanSuKuangDong000") for p in HUB_ZONE_PATTERNS)

    def test_does_not_match_timemark_7_zone(self):
        # Timemark 7 maps use 04DD code but should NOT be detected as hub
        assert not any(p.search("/Game/Art/Maps/04DD/DD_ChaoBaiZhiLu200") for p in HUB_ZONE_PATTERNS)

    def test_detects_sacred_court_manor_hideout(self):
        # Sacred Court Manor hideout (also uses 04DD) should still be detected
        assert any(p.search("/Game/Art/Maps/04DD/DD_ShengTingZhuangYuan000") for p in HUB_ZONE_PATTERNS)
