"""Inventory tab constants and configuration."""


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
