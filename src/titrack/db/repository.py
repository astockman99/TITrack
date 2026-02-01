"""Repository - CRUD operations for all entities."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from titrack.core.models import (
    EventContext,
    Item,
    ItemDelta,
    Price,
    Run,
    SlotState,
)
from titrack.db.connection import Database
from titrack.data.inventory import EXCLUDED_PAGES


class Repository:
    """Data access layer for all entities."""

    def __init__(self, db: Database) -> None:
        self.db = db
        # Current player context for filtering (set externally)
        self._current_season_id: Optional[int] = None
        self._current_player_id: Optional[str] = None

    def set_player_context(self, season_id: Optional[int], player_id: Optional[str]) -> None:
        """Set the current player context for filtering queries."""
        self._current_season_id = season_id
        self._current_player_id = player_id

    def has_player_context(self) -> bool:
        """Return True if a player context has been set."""
        return self._current_player_id is not None

    # --- Settings ---

    def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value by key."""
        row = self.db.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        self.db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat()),
        )

    # --- Runs ---

    def insert_run(self, run: Run) -> int:
        """Insert a new run and return its ID."""
        cursor = self.db.execute(
            """INSERT INTO runs (zone_signature, start_ts, end_ts, is_hub, level_id, level_type, level_uid, season_id, player_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.zone_signature,
                run.start_ts.isoformat(),
                run.end_ts.isoformat() if run.end_ts else None,
                1 if run.is_hub else 0,
                run.level_id,
                run.level_type,
                run.level_uid,
                run.season_id,
                run.player_id,
            ),
        )
        return cursor.lastrowid

    def update_run_end(self, run_id: int, end_ts: datetime) -> None:
        """Update a run's end timestamp."""
        self.db.execute(
            "UPDATE runs SET end_ts = ? WHERE id = ?",
            (end_ts.isoformat(), run_id),
        )

    def get_run(self, run_id: int) -> Optional[Run]:
        """Get a run by ID."""
        row = self.db.fetchone("SELECT * FROM runs WHERE id = ?", (run_id,))
        if not row:
            return None
        return self._row_to_run(row)

    def get_active_run(self, season_id: Optional[int] = None, player_id: Optional[str] = None) -> Optional[Run]:
        """Get the currently active (non-ended) run, optionally filtered by season/player."""
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return None if no player context is set (awaiting character login)
        if self._current_player_id is None and player_id is None:
            return None

        if season_id is not None:
            # Filter: show data where season/player matches OR is NULL (legacy/untagged)
            # This excludes data explicitly tagged for a DIFFERENT season/player
            row = self.db.fetchone(
                """SELECT * FROM runs WHERE end_ts IS NULL
                   AND (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)
                   ORDER BY start_ts DESC LIMIT 1""",
                (season_id, player_id or ''),
            )
        else:
            row = self.db.fetchone(
                "SELECT * FROM runs WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1"
            )
        if not row:
            return None
        return self._row_to_run(row)

    def get_recent_runs(self, limit: int = 20, season_id: Optional[int] = None, player_id: Optional[str] = None) -> list[Run]:
        """Get recent runs ordered by start time descending, optionally filtered by season/player."""
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return empty list if no player context is set (awaiting character login)
        if self._current_player_id is None and player_id is None:
            return []

        if season_id is not None:
            # Filter: show data where season/player matches OR is NULL (legacy/untagged)
            # This excludes data explicitly tagged for a DIFFERENT season/player
            rows = self.db.fetchall(
                """SELECT * FROM runs
                   WHERE (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)
                   ORDER BY start_ts DESC LIMIT ?""",
                (season_id, player_id or '', limit),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM runs ORDER BY start_ts DESC LIMIT ?", (limit,)
            )
        return [self._row_to_run(row) for row in rows]

    def get_max_run_id(self) -> int:
        """Get the maximum run ID."""
        row = self.db.fetchone("SELECT MAX(id) as max_id FROM runs")
        return row["max_id"] or 0

    def get_unique_zones(self, season_id: Optional[int] = None, player_id: Optional[str] = None) -> list[str]:
        """Get all unique zone signatures from runs, optionally filtered by season/player."""
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return empty list if no player context is set (awaiting character login)
        if self._current_player_id is None and player_id is None:
            return []

        if season_id is not None:
            # Filter: show data where season/player matches OR is NULL (legacy/untagged)
            rows = self.db.fetchall(
                """SELECT DISTINCT zone_signature FROM runs
                   WHERE (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)
                   ORDER BY zone_signature""",
                (season_id, player_id or ''),
            )
        else:
            rows = self.db.fetchall(
                "SELECT DISTINCT zone_signature FROM runs ORDER BY zone_signature"
            )
        return [row["zone_signature"] for row in rows]

    def _row_to_run(self, row) -> Run:
        # Handle columns which may not exist in older databases
        keys = row.keys()
        level_id = row["level_id"] if "level_id" in keys else None
        level_type = row["level_type"] if "level_type" in keys else None
        level_uid = row["level_uid"] if "level_uid" in keys else None
        season_id = row["season_id"] if "season_id" in keys else None
        player_id = row["player_id"] if "player_id" in keys else None
        return Run(
            id=row["id"],
            zone_signature=row["zone_signature"],
            start_ts=datetime.fromisoformat(row["start_ts"]),
            end_ts=datetime.fromisoformat(row["end_ts"]) if row["end_ts"] else None,
            is_hub=bool(row["is_hub"]),
            level_id=level_id,
            level_type=level_type,
            level_uid=level_uid,
            season_id=season_id,
            player_id=player_id,
        )

    # --- Item Deltas ---

    def insert_delta(self, delta: ItemDelta) -> int:
        """Insert an item delta and return its ID."""
        cursor = self.db.execute(
            """INSERT INTO item_deltas
               (page_id, slot_id, config_base_id, delta, context, proto_name, run_id, timestamp, season_id, player_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                delta.page_id,
                delta.slot_id,
                delta.config_base_id,
                delta.delta,
                delta.context.name,
                delta.proto_name,
                delta.run_id,
                delta.timestamp.isoformat(),
                delta.season_id,
                delta.player_id,
            ),
        )
        return cursor.lastrowid

    def get_deltas_for_run(self, run_id: int, include_excluded: bool = False) -> list[ItemDelta]:
        """
        Get all deltas for a run.

        Args:
            run_id: The run ID to get deltas for.
            include_excluded: If True, include excluded pages (e.g., Gear).
                              Default False filters out excluded pages.
        """
        if include_excluded or not EXCLUDED_PAGES:
            rows = self.db.fetchall(
                "SELECT * FROM item_deltas WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            )
        else:
            placeholders = ",".join("?" * len(EXCLUDED_PAGES))
            rows = self.db.fetchall(
                f"SELECT * FROM item_deltas WHERE run_id = ? AND page_id NOT IN ({placeholders}) ORDER BY timestamp",
                (run_id, *EXCLUDED_PAGES),
            )
        return [self._row_to_delta(row) for row in rows]

    def get_run_summary(self, run_id: int, include_excluded: bool = False) -> dict[int, int]:
        """
        Get aggregated delta per item for a run (excludes map costs).

        Args:
            run_id: The run ID to get summary for.
            include_excluded: If True, include excluded pages (e.g., Gear).
                              Default False filters out excluded pages.

        Returns:
            Dict mapping config_base_id -> total delta
        """
        # Always exclude Spv3Open (map costs) from loot summary
        if include_excluded or not EXCLUDED_PAGES:
            rows = self.db.fetchall(
                """SELECT config_base_id, SUM(delta) as total_delta
                   FROM item_deltas
                   WHERE run_id = ? AND (proto_name IS NULL OR proto_name != 'Spv3Open')
                   GROUP BY config_base_id""",
                (run_id,),
            )
        else:
            placeholders = ",".join("?" * len(EXCLUDED_PAGES))
            rows = self.db.fetchall(
                f"""SELECT config_base_id, SUM(delta) as total_delta
                   FROM item_deltas
                   WHERE run_id = ? AND page_id NOT IN ({placeholders})
                   AND (proto_name IS NULL OR proto_name != 'Spv3Open')
                   GROUP BY config_base_id""",
                (run_id, *EXCLUDED_PAGES),
            )
        return {row["config_base_id"]: row["total_delta"] for row in rows}

    def _row_to_delta(self, row) -> ItemDelta:
        keys = row.keys()
        season_id = row["season_id"] if "season_id" in keys else None
        player_id = row["player_id"] if "player_id" in keys else None
        return ItemDelta(
            page_id=row["page_id"],
            slot_id=row["slot_id"],
            config_base_id=row["config_base_id"],
            delta=row["delta"],
            context=EventContext[row["context"]],
            proto_name=row["proto_name"],
            run_id=row["run_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            season_id=season_id,
            player_id=player_id,
        )

    # --- Slot State ---

    def upsert_slot_state(self, state: SlotState) -> None:
        """Insert or update slot state."""
        # Use empty string for NULL player_id to match PK constraint
        player_id = state.player_id if state.player_id else ""
        self.db.execute(
            """INSERT OR REPLACE INTO slot_state
               (player_id, page_id, slot_id, config_base_id, num, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                player_id,
                state.page_id,
                state.slot_id,
                state.config_base_id,
                state.num,
                state.updated_at.isoformat(),
            ),
        )

    def get_all_slot_states(self, include_excluded: bool = False, player_id: Optional[str] = None) -> list[SlotState]:
        """
        Get all slot states.

        Args:
            include_excluded: If True, include excluded pages (e.g., Gear).
                              Default False filters out excluded pages.
            player_id: Filter by player_id. If None, uses current context or returns all.
        """
        # Use provided value or fall back to context
        player_id = player_id if player_id is not None else self._current_player_id

        # Return empty list if no player context is set (awaiting character login)
        if self._current_player_id is None and player_id is None:
            return []

        player_id_filter = player_id if player_id else ""

        if include_excluded or not EXCLUDED_PAGES:
            if player_id is not None:
                rows = self.db.fetchall(
                    "SELECT * FROM slot_state WHERE player_id = ?",
                    (player_id_filter,),
                )
            else:
                rows = self.db.fetchall("SELECT * FROM slot_state")
        else:
            placeholders = ",".join("?" * len(EXCLUDED_PAGES))
            if player_id is not None:
                rows = self.db.fetchall(
                    f"SELECT * FROM slot_state WHERE player_id = ? AND page_id NOT IN ({placeholders})",
                    (player_id_filter, *EXCLUDED_PAGES),
                )
            else:
                rows = self.db.fetchall(
                    f"SELECT * FROM slot_state WHERE page_id NOT IN ({placeholders})",
                    tuple(EXCLUDED_PAGES),
                )
        return [self._row_to_slot_state(row) for row in rows]

    def get_slot_state(self, page_id: int, slot_id: int, player_id: Optional[str] = None) -> Optional[SlotState]:
        """Get state for a specific slot."""
        # Use provided value or fall back to context
        player_id = player_id if player_id is not None else self._current_player_id
        player_id_filter = player_id if player_id else ""

        row = self.db.fetchone(
            "SELECT * FROM slot_state WHERE player_id = ? AND page_id = ? AND slot_id = ?",
            (player_id_filter, page_id, slot_id),
        )
        if not row:
            return None
        return self._row_to_slot_state(row)

    def clear_page_slot_states(self, page_id: int, player_id: Optional[str] = None) -> int:
        """
        Clear all slot states for a specific inventory page and player.

        Used when receiving InitBagData events to ensure stale slots are removed.

        Returns:
            Number of slots cleared.
        """
        # Use provided value or fall back to context
        player_id = player_id if player_id is not None else self._current_player_id
        player_id_filter = player_id if player_id else ""

        cursor = self.db.execute(
            "DELETE FROM slot_state WHERE player_id = ? AND page_id = ?",
            (player_id_filter, page_id),
        )
        return cursor.rowcount

    def _row_to_slot_state(self, row) -> SlotState:
        keys = row.keys()
        player_id = row["player_id"] if "player_id" in keys else None
        # Convert empty string back to None
        if player_id == "":
            player_id = None
        return SlotState(
            page_id=row["page_id"],
            slot_id=row["slot_id"],
            config_base_id=row["config_base_id"],
            num=row["num"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
            player_id=player_id,
        )

    # --- Items ---

    def upsert_item(self, item: Item) -> None:
        """Insert or update item metadata."""
        self.db.execute(
            """INSERT OR REPLACE INTO items
               (config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                item.config_base_id,
                item.name_en,
                item.name_cn,
                item.type_cn,
                item.icon_url,
                item.url_en,
                item.url_cn,
            ),
        )

    def upsert_items_batch(self, items: list[Item]) -> None:
        """Insert or update multiple items."""
        self.db.executemany(
            """INSERT OR REPLACE INTO items
               (config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    item.config_base_id,
                    item.name_en,
                    item.name_cn,
                    item.type_cn,
                    item.icon_url,
                    item.url_en,
                    item.url_cn,
                )
                for item in items
            ],
        )

    def get_item(self, config_base_id: int) -> Optional[Item]:
        """Get item by ConfigBaseId."""
        row = self.db.fetchone(
            "SELECT * FROM items WHERE config_base_id = ?", (config_base_id,)
        )
        if not row:
            return None
        return self._row_to_item(row)

    def get_item_name(self, config_base_id: int) -> str:
        """Get item name, falling back to Unknown <id> if not found."""
        item = self.get_item(config_base_id)
        if item and item.name_en:
            return item.name_en
        return f"Unknown {config_base_id}"

    def get_all_items(self) -> list[Item]:
        """Get all items."""
        rows = self.db.fetchall("SELECT * FROM items")
        return [self._row_to_item(row) for row in rows]

    def get_item_count(self) -> int:
        """Get total number of items in database."""
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM items")
        return row["cnt"] if row else 0

    def update_item_name(self, config_base_id: int, name_en: str) -> None:
        """Update an item's English name."""
        self.db.execute(
            "UPDATE items SET name_en = ? WHERE config_base_id = ?",
            (name_en, config_base_id),
        )

    def _row_to_item(self, row) -> Item:
        return Item(
            config_base_id=row["config_base_id"],
            name_en=row["name_en"],
            name_cn=row["name_cn"],
            type_cn=row["type_cn"],
            icon_url=row["icon_url"],
            url_en=row["url_en"],
            url_cn=row["url_cn"],
        )

    # --- Prices ---

    def upsert_price(self, price: Price) -> None:
        """Insert or update a price entry."""
        # Use 0 for NULL season_id to match PK constraint
        season_id = price.season_id if price.season_id is not None else 0
        self.db.execute(
            """INSERT OR REPLACE INTO prices
               (config_base_id, season_id, price_fe, source, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                price.config_base_id,
                season_id,
                price.price_fe,
                price.source,
                price.updated_at.isoformat(),
            ),
        )

    def get_price(self, config_base_id: int, season_id: Optional[int] = None) -> Optional[Price]:
        """Get price for an item, filtered by season (no cross-season fallback)."""
        # Use provided value or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        row = self.db.fetchone(
            "SELECT * FROM prices WHERE config_base_id = ? AND season_id = ?",
            (config_base_id, season_id_filter),
        )
        if not row:
            return None
        return self._row_to_price(row)

    def get_cloud_price(self, config_base_id: int, season_id: Optional[int] = None) -> Optional[float]:
        """
        Get cloud price for an item (median price from community data).

        Returns the median price in FE, or None if not available.
        Only returns prices with at least 3 unique contributors.
        """
        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        row = self.db.fetchone(
            """SELECT price_fe_median, unique_devices FROM cloud_price_cache
               WHERE config_base_id = ? AND season_id = ? AND unique_devices >= 1""",
            (config_base_id, season_id_filter),
        )
        if not row:
            return None
        return row["price_fe_median"]

    def get_effective_price(self, config_base_id: int, season_id: Optional[int] = None) -> Optional[float]:
        """
        Get the effective price for an item using cloud-first logic.

        Priority:
        1. Cloud price is the default (community aggregate, more reliable)
        2. Local price overrides ONLY if it's newer than the cloud data

        Returns the price in FE, or None if no price available.
        """
        from datetime import datetime

        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        # Get cloud price with timestamp
        cloud_row = self.db.fetchone(
            """SELECT price_fe_median, cloud_updated_at, unique_devices FROM cloud_price_cache
               WHERE config_base_id = ? AND season_id = ? AND unique_devices >= 1""",
            (config_base_id, season_id_filter),
        )

        # Get local price with timestamp
        local_row = self.db.fetchone(
            "SELECT price_fe, updated_at FROM prices WHERE config_base_id = ? AND season_id = ?",
            (config_base_id, season_id_filter),
        )

        cloud_price = cloud_row["price_fe_median"] if cloud_row else None
        local_price = local_row["price_fe"] if local_row else None

        # If only one exists, use it
        if cloud_price is None and local_price is None:
            return None
        if cloud_price is None:
            return local_price
        if local_price is None:
            return cloud_price

        # Both exist - compare timestamps
        # Local overrides only if it's newer than cloud
        cloud_updated = cloud_row["cloud_updated_at"] if cloud_row else None
        local_updated = local_row["updated_at"] if local_row else None

        if cloud_updated and local_updated:
            try:
                # Parse ISO format timestamps and normalize to naive UTC for comparison
                cloud_dt = datetime.fromisoformat(cloud_updated.replace("Z", "+00:00"))
                local_dt = datetime.fromisoformat(local_updated.replace("Z", "+00:00"))

                # Strip timezone info for comparison (both treated as UTC)
                if cloud_dt.tzinfo is not None:
                    cloud_dt = cloud_dt.replace(tzinfo=None)
                if local_dt.tzinfo is not None:
                    local_dt = local_dt.replace(tzinfo=None)

                if local_dt > cloud_dt:
                    return local_price
                else:
                    return cloud_price
            except (ValueError, AttributeError, TypeError):
                # If timestamp parsing fails, prefer cloud
                return cloud_price
        elif local_updated and not cloud_updated:
            # Cloud has no timestamp, prefer local if it has one
            return local_price
        else:
            # Default to cloud
            return cloud_price

    def get_all_prices(self, season_id: Optional[int] = None) -> list[Price]:
        """Get all prices, filtered by season (no cross-season mixing)."""
        # Use provided value or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        rows = self.db.fetchall(
            "SELECT * FROM prices WHERE season_id = ?",
            (season_id_filter,),
        )
        return [self._row_to_price(row) for row in rows]

    def get_price_count(self, season_id: Optional[int] = None) -> int:
        """Get total number of prices in database, filtered by season."""
        # Use provided value or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        row = self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM prices WHERE season_id = ?",
            (season_id_filter,),
        )
        return row["cnt"] if row else 0

    def upsert_prices_batch(self, prices: list[Price]) -> None:
        """Insert or update multiple prices."""
        self.db.executemany(
            """INSERT OR REPLACE INTO prices
               (config_base_id, season_id, price_fe, source, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (
                    price.config_base_id,
                    price.season_id if price.season_id is not None else 0,
                    price.price_fe,
                    price.source,
                    price.updated_at.isoformat(),
                )
                for price in prices
            ],
        )

    def migrate_legacy_prices(self, target_season_id: int) -> int:
        """
        Migrate legacy prices (season_id=0) to a specific season.

        Args:
            target_season_id: The season to assign legacy prices to.

        Returns:
            Number of prices migrated.
        """
        # Count legacy prices first
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM prices WHERE season_id = 0")
        count = row["cnt"] if row else 0

        if count > 0:
            # Update legacy prices to target season
            self.db.execute(
                "UPDATE prices SET season_id = ? WHERE season_id = 0",
                (target_season_id,),
            )

        return count

    def _row_to_price(self, row) -> Price:
        keys = row.keys()
        season_id = row["season_id"] if "season_id" in keys else None
        # Convert 0 back to None (legacy/unknown)
        if season_id == 0:
            season_id = None
        return Price(
            config_base_id=row["config_base_id"],
            price_fe=row["price_fe"],
            source=row["source"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
            season_id=season_id,
        )

    def get_trade_tax_multiplier(self) -> float:
        """
        Get the trade tax multiplier based on settings.

        The Torchlight trade house takes 1 FE per 8 FE (12.5% tax).
        When enabled, values are multiplied by 0.875 to show after-tax amounts.

        Returns:
            1.0 if tax disabled, 0.875 if enabled
        """
        if self.get_setting("trade_tax_enabled") == "true":
            return 0.875  # 7/8 = 87.5% after 12.5% tax
        return 1.0

    def get_run_value(self, run_id: int) -> tuple[int, float]:
        """
        Calculate total value of a run's loot.

        Returns:
            Tuple of (raw_fe_gained, total_value_fe)
            - raw_fe_gained: Just the FE currency picked up
            - total_value_fe: FE + value of other items based on prices
              (with trade tax applied to non-FE items if enabled)
        """
        from titrack.parser.patterns import FE_CONFIG_BASE_ID

        summary = self.get_run_summary(run_id)
        raw_fe = summary.get(FE_CONFIG_BASE_ID, 0)
        total_value = float(raw_fe)

        tax_multiplier = self.get_trade_tax_multiplier()

        for config_id, quantity in summary.items():
            if config_id == FE_CONFIG_BASE_ID:
                continue
            if quantity <= 0:
                continue

            # Use effective price (cloud-first, local overrides if newer)
            price_fe = self.get_effective_price(config_id)

            if price_fe and price_fe > 0:
                # Apply trade tax to non-FE items (would need to sell them)
                total_value += price_fe * quantity * tax_multiplier

        return raw_fe, total_value

    def get_run_cost(self, run_id: int) -> tuple[dict[int, int], float, list[int]]:
        """
        Get map costs for a run (Spv3Open consumption).

        Args:
            run_id: The run ID to get costs for.

        Returns:
            Tuple of (cost_summary, total_cost_fe, unpriced_config_ids)
            - cost_summary: {config_base_id: quantity} (negative values for consumption)
            - total_cost_fe: Sum of priced items only (absolute value)
            - unpriced_config_ids: List of items without known prices
        """
        rows = self.db.fetchall(
            """SELECT config_base_id, SUM(delta) as total_delta
               FROM item_deltas
               WHERE run_id = ? AND proto_name = 'Spv3Open'
               GROUP BY config_base_id""",
            (run_id,),
        )
        summary = {row["config_base_id"]: row["total_delta"] for row in rows}

        total_cost = 0.0
        unpriced: list[int] = []
        tax_multiplier = self.get_trade_tax_multiplier()

        for config_id, quantity in summary.items():
            price_fe = self.get_effective_price(config_id)
            if price_fe and price_fe > 0:
                # Use absolute value since quantity is negative (consumption)
                total_cost += abs(quantity) * price_fe * tax_multiplier
            else:
                unpriced.append(config_id)

        return summary, total_cost, unpriced

    # --- Data Management ---

    def clear_run_data(self) -> int:
        """
        Clear all run tracking data (runs and item_deltas).

        Preserves: items, prices, settings, slot_state, log_position.

        Returns:
            Number of runs deleted.
        """
        # Get count before deletion
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM runs")
        run_count = row["cnt"] if row else 0

        # Get raw connection for direct control
        conn = self.db.connection

        # Use explicit transaction for deletion
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Delete item_deltas first (foreign key reference)
            conn.execute("DELETE FROM item_deltas")
            # Delete runs
            conn.execute("DELETE FROM runs")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        # Force WAL checkpoint to ensure changes are written to main database
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        return run_count

    # --- Log Position ---

    def save_log_position(self, file_path: Path, position: int, file_size: int) -> None:
        """Save current log file position for resume."""
        # Guard against oversized integers (SQLite max is 2^63-1)
        MAX_SQLITE_INT = 9223372036854775807
        if position > MAX_SQLITE_INT or file_size > MAX_SQLITE_INT:
            print(f"WARNING: Log position overflow - position={position}, file_size={file_size}")
            # Clamp to max value to avoid crash
            position = min(position, MAX_SQLITE_INT)
            file_size = min(file_size, MAX_SQLITE_INT)

        conn = self.db.connection
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """INSERT OR REPLACE INTO log_position
                   (id, file_path, position, file_size, updated_at)
                   VALUES (1, ?, ?, ?, ?)""",
                (str(file_path), position, file_size, datetime.now().isoformat()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        # Force checkpoint
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def get_log_position(self) -> Optional[tuple[Path, int, int]]:
        """
        Get saved log position.

        Returns:
            Tuple of (file_path, position, file_size) or None
        """
        row = self.db.fetchone("SELECT * FROM log_position WHERE id = 1")
        if not row:
            return None
        return (Path(row["file_path"]), row["position"], row["file_size"])

    def get_cumulative_loot(
        self, season_id: Optional[int] = None, player_id: Optional[str] = None
    ) -> list[dict]:
        """
        Get cumulative loot statistics across all runs.

        Aggregates all item deltas (positive quantities only) grouped by config_base_id.
        Excludes map costs (proto_name='Spv3Open') and gear page (PageId 100).

        Args:
            season_id: Filter by season (uses context if None)
            player_id: Filter by player (uses context if None)

        Returns:
            List of dicts with keys: config_base_id, total_quantity
        """
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return empty list if no player context is set
        if self._current_player_id is None and player_id is None:
            return []

        # Build query with appropriate filters
        # Only include items picked up during map runs (run_id IS NOT NULL)
        base_query = """
            SELECT config_base_id, SUM(delta) as total_quantity
            FROM item_deltas
            WHERE run_id IS NOT NULL
            AND (proto_name IS NULL OR proto_name != 'Spv3Open')
        """

        params: list = []

        # Filter by season/player
        if season_id is not None:
            base_query += " AND (season_id IS NULL OR season_id = ?)"
            params.append(season_id)
            base_query += " AND (player_id IS NULL OR player_id = ?)"
            params.append(player_id or '')

        # Exclude gear page
        if EXCLUDED_PAGES:
            placeholders = ",".join("?" * len(EXCLUDED_PAGES))
            base_query += f" AND page_id NOT IN ({placeholders})"
            params.extend(EXCLUDED_PAGES)

        # Group and filter for positive quantities only
        base_query += " GROUP BY config_base_id HAVING SUM(delta) > 0"

        rows = self.db.fetchall(base_query, tuple(params))
        return [
            {"config_base_id": row["config_base_id"], "total_quantity": row["total_quantity"]}
            for row in rows
        ]

    def get_completed_run_count(
        self, season_id: Optional[int] = None, player_id: Optional[str] = None
    ) -> int:
        """
        Get count of completed (non-hub) runs.

        Args:
            season_id: Filter by season (uses context if None)
            player_id: Filter by player (uses context if None)

        Returns:
            Number of completed runs
        """
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return 0 if no player context is set
        if self._current_player_id is None and player_id is None:
            return 0

        if season_id is not None:
            row = self.db.fetchone(
                """SELECT COUNT(*) as cnt FROM runs
                   WHERE end_ts IS NOT NULL AND is_hub = 0
                   AND (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)""",
                (season_id, player_id or ''),
            )
        else:
            row = self.db.fetchone(
                "SELECT COUNT(*) as cnt FROM runs WHERE end_ts IS NOT NULL AND is_hub = 0"
            )
        return row["cnt"] if row else 0

    def get_total_run_duration(
        self, season_id: Optional[int] = None, player_id: Optional[str] = None
    ) -> float:
        """
        Get total duration of all completed (non-hub) runs in seconds.

        Args:
            season_id: Filter by season (uses context if None)
            player_id: Filter by player (uses context if None)

        Returns:
            Total duration in seconds
        """
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return 0 if no player context is set
        if self._current_player_id is None and player_id is None:
            return 0.0

        if season_id is not None:
            row = self.db.fetchone(
                """SELECT SUM(
                       (julianday(end_ts) - julianday(start_ts)) * 86400
                   ) as total_seconds
                   FROM runs
                   WHERE end_ts IS NOT NULL AND is_hub = 0
                   AND (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)""",
                (season_id, player_id or ''),
            )
        else:
            row = self.db.fetchone(
                """SELECT SUM(
                       (julianday(end_ts) - julianday(start_ts)) * 86400
                   ) as total_seconds
                   FROM runs
                   WHERE end_ts IS NOT NULL AND is_hub = 0"""
            )
        return row["total_seconds"] if row and row["total_seconds"] else 0.0

    def get_total_map_costs(
        self, season_id: Optional[int] = None, player_id: Optional[str] = None
    ) -> float:
        """
        Get total map costs across all runs.

        Args:
            season_id: Filter by season (uses context if None)
            player_id: Filter by player (uses context if None)

        Returns:
            Total map cost in FE
        """
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return 0 if no player context is set
        if self._current_player_id is None and player_id is None:
            return 0.0

        # Get all map cost deltas (Spv3Open events with run_id)
        if season_id is not None:
            rows = self.db.fetchall(
                """SELECT config_base_id, SUM(delta) as total_delta
                   FROM item_deltas
                   WHERE run_id IS NOT NULL AND proto_name = 'Spv3Open'
                   AND (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)
                   GROUP BY config_base_id""",
                (season_id, player_id or ''),
            )
        else:
            rows = self.db.fetchall(
                """SELECT config_base_id, SUM(delta) as total_delta
                   FROM item_deltas
                   WHERE run_id IS NOT NULL AND proto_name = 'Spv3Open'
                   GROUP BY config_base_id"""
            )

        total_cost = 0.0
        tax_multiplier = self.get_trade_tax_multiplier()

        for row in rows:
            config_id = row["config_base_id"]
            quantity = row["total_delta"]  # Negative for consumption
            price_fe = self.get_effective_price(config_id)
            if price_fe and price_fe > 0:
                # Use absolute value since quantity is negative
                total_cost += abs(quantity) * price_fe * tax_multiplier

        return total_cost
