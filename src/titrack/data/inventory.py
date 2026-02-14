"""Inventory tab constants and configuration."""

from typing import Optional

from titrack.db.connection import Database


class InventoryPage:
    """Inventory tab PageId mappings from game logs."""

    GEAR = 100  # Equipment/Gear - prices too dependent on affixes
    SKILL = 101  # Skills and skill-related items
    COMMODITY = 102  # Consumables, currency, crafting materials
    MISC = 103  # Miscellaneous items

    ALL = [GEAR, SKILL, COMMODITY, MISC]

    NAMES = {
        GEAR: "Gear",
        SKILL: "Skill",
        COMMODITY: "Commodity",
        MISC: "Misc",
    }


# Pages to exclude from tracking (prices not reliable)
EXCLUDED_PAGES = frozenset([InventoryPage.GEAR])

# Pages to track (all except excluded)
TRACKED_PAGES = frozenset([
    p for p in InventoryPage.ALL if p not in EXCLUDED_PAGES
])

# Gear-tab item types (type_cn) that have stable, tradeable prices.
# Items matching these types are allowed through the gear page exclusion filter.
ALLOWED_GEAR_TYPE_CN = frozenset([
    # Destiny
    "命运",
    "命运相关",
    "未定宿命",
    # Prisms
    "异度棱镜",
    "特殊棱镜",
    "棱镜水平仪",
    "棱镜校尺",
    "棱镜修复仪",
    # Divinity
    "神格契约",
    "神格残片",
    "巨力之神",
    "征战之神",
    "欺诈之神",
    "机械之神",
])

# Module-level set of ConfigBaseIds allowed from gear tab, populated at startup.
_allowed_gear_ids: frozenset[int] = frozenset()


def initialize_gear_allowlist(db: Database) -> None:
    """Query items table and populate the gear allowlist from ALLOWED_GEAR_TYPE_CN.

    Call this once after db.connect() at startup.
    """
    global _allowed_gear_ids

    if not ALLOWED_GEAR_TYPE_CN:
        _allowed_gear_ids = frozenset()
        return

    placeholders = ",".join("?" * len(ALLOWED_GEAR_TYPE_CN))
    rows = db.fetchall(
        f"SELECT config_base_id FROM items WHERE type_cn IN ({placeholders})",
        tuple(ALLOWED_GEAR_TYPE_CN),
    )
    _allowed_gear_ids = frozenset(row["config_base_id"] for row in rows)


def set_gear_allowlist(ids: frozenset[int]) -> None:
    """Set the gear allowlist directly (for testing)."""
    global _allowed_gear_ids
    _allowed_gear_ids = ids


def get_gear_allowlist() -> frozenset[int]:
    """Get the current gear allowlist."""
    return _allowed_gear_ids


def is_gear_excluded(page_id: int, config_base_id: Optional[int] = None) -> bool:
    """Check if an item should be excluded based on page and allowlist.

    Returns True if the item should be excluded from tracking.

    - Non-excluded pages always return False (item is tracked).
    - Excluded pages return False if config_base_id is in the gear allowlist.
    - Excluded pages return True otherwise.
    """
    if page_id not in EXCLUDED_PAGES:
        return False
    if config_base_id is not None and config_base_id in _allowed_gear_ids:
        return False
    return True
