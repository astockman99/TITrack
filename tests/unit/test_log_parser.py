"""Tests for log line parser."""

import pytest

from titrack.core.models import (
    ParsedBagEvent,
    ParsedContextMarker,
    ParsedLevelEvent,
)
from titrack.parser.log_parser import parse_line, parse_lines


class TestParseLine:
    """Tests for single line parsing."""

    def test_parses_bag_modify_event(self):
        line = "GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 671"
        event = parse_line(line)
        assert isinstance(event, ParsedBagEvent)
        assert event.page_id == 102
        assert event.slot_id == 0
        assert event.config_base_id == 100300
        assert event.num == 671
        assert event.raw_line == line
        assert event.is_init is False

    def test_parses_bag_init_event(self):
        line = "GameLog: Display: [Game] BagMgr@:InitBagData PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 609"
        event = parse_line(line)
        assert isinstance(event, ParsedBagEvent)
        assert event.page_id == 102
        assert event.slot_id == 0
        assert event.config_base_id == 100300
        assert event.num == 609
        assert event.raw_line == line
        assert event.is_init is True

    def test_parses_bag_init_event_different_page(self):
        """Test init events for different bag pages (equipment, skills, misc)."""
        line = "GameLog: Display: [Game] BagMgr@:InitBagData PageId = 103 SlotId = 57 ConfigBaseId = 6153 Num = 14"
        event = parse_line(line)
        assert isinstance(event, ParsedBagEvent)
        assert event.page_id == 103
        assert event.slot_id == 57
        assert event.config_base_id == 6153
        assert event.num == 14
        assert event.is_init is True

    def test_parses_context_start(self):
        line = "GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start"
        event = parse_line(line)
        assert isinstance(event, ParsedContextMarker)
        assert event.proto_name == "PickItems"
        assert event.is_start is True

    def test_parses_context_end(self):
        line = "GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end"
        event = parse_line(line)
        assert isinstance(event, ParsedContextMarker)
        assert event.proto_name == "PickItems"
        assert event.is_start is False

    def test_parses_level_event(self):
        line = "SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/02KD/KD_YuanSuKuangDong000"
        event = parse_line(line)
        assert isinstance(event, ParsedLevelEvent)
        assert event.event_type == "OpenMainWorld"
        assert "KD_YuanSuKuangDong000" in event.level_info

    def test_returns_none_for_unknown_line(self):
        line = "Some random log line"
        event = parse_line(line)
        assert event is None

    def test_returns_none_for_empty_line(self):
        event = parse_line("")
        assert event is None

    def test_handles_newlines(self):
        line = "SceneLevelMgr@ OpenMainWorld END! InMainLevelPath = /Game/Art/Maps/01SD/XZ_Test\r\n"
        event = parse_line(line)
        assert isinstance(event, ParsedLevelEvent)
        assert "XZ_Test" in event.level_info


class TestParseLines:
    """Tests for multi-line parsing."""

    def test_parses_multiple_lines(self):
        lines = [
            "GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start",
            "GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 500",
            "GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end",
        ]
        events = parse_lines(lines)
        assert len(events) == 3
        assert isinstance(events[0], ParsedContextMarker)
        assert isinstance(events[1], ParsedBagEvent)
        assert isinstance(events[2], ParsedContextMarker)

    def test_filters_none_events(self):
        lines = [
            "Random line 1",
            "GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 500",
            "Random line 2",
        ]
        events = parse_lines(lines)
        assert len(events) == 1
        assert isinstance(events[0], ParsedBagEvent)
