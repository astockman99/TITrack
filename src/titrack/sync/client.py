"""Supabase client wrapper for cloud sync."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Supabase is optional - only required when cloud sync is enabled
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None


@dataclass
class CloudPrice:
    """Aggregated price from cloud."""

    config_base_id: int
    season_id: int
    price_fe_median: float
    price_fe_p10: Optional[float] = None
    price_fe_p90: Optional[float] = None
    submission_count: Optional[int] = None
    unique_devices: Optional[int] = None
    updated_at: Optional[datetime] = None


@dataclass
class CloudPriceHistory:
    """Hourly price history point from cloud."""

    config_base_id: int
    season_id: int
    hour_bucket: datetime
    price_fe_median: float
    price_fe_p10: Optional[float] = None
    price_fe_p90: Optional[float] = None
    submission_count: Optional[int] = None


@dataclass
class SubmitResult:
    """Result of a price submission."""

    success: bool
    error: Optional[str] = None
    rate_limited: bool = False


class CloudClient:
    """
    Supabase client wrapper for cloud price sync.

    Handles connection, authentication, and all cloud API calls.
    Uses anonymous device-based authentication (no user accounts).
    """

    # Environment variable names
    ENV_SUPABASE_URL = "TITRACK_SUPABASE_URL"
    ENV_SUPABASE_KEY = "TITRACK_SUPABASE_KEY"

    # Hardcoded defaults for packaged app (can be overridden by env vars)
    # These will be populated when Supabase project is created
    DEFAULT_SUPABASE_URL = "https://qhjulyngunwiculnharg.supabase.co"
    DEFAULT_SUPABASE_KEY = "sb_publishable_YgqYSMUarrM_IKvcNpJlBw_KwTpp7ho"

    def __init__(self) -> None:
        """Initialize the cloud client (not connected yet)."""
        self._client: Optional[Client] = None
        self._connected = False

    @property
    def is_available(self) -> bool:
        """Check if Supabase SDK is installed."""
        return SUPABASE_AVAILABLE

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to Supabase."""
        return self._connected and self._client is not None

    def get_config(self) -> tuple[Optional[str], Optional[str]]:
        """
        Get Supabase configuration from environment or defaults.

        Returns:
            Tuple of (url, key) or (None, None) if not configured
        """
        url = os.environ.get(self.ENV_SUPABASE_URL, self.DEFAULT_SUPABASE_URL)
        key = os.environ.get(self.ENV_SUPABASE_KEY, self.DEFAULT_SUPABASE_KEY)

        if not url or not key:
            return None, None

        return url, key

    def connect(self) -> bool:
        """
        Connect to Supabase.

        Returns:
            True if connection successful, False otherwise
        """
        if not SUPABASE_AVAILABLE:
            return False

        url, key = self.get_config()
        if not url or not key:
            return False

        try:
            self._client = create_client(url, key)
            self._connected = True
            return True
        except Exception as e:
            print(f"Cloud sync: Failed to connect to Supabase: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from Supabase."""
        self._client = None
        self._connected = False

    def submit_price(
        self,
        device_id: str,
        config_base_id: int,
        season_id: int,
        price_fe: float,
        prices_array: list[float],
    ) -> SubmitResult:
        """
        Submit a price observation to the cloud.

        Args:
            device_id: This device's UUID
            config_base_id: Item type ID
            season_id: Current season/league ID
            price_fe: Calculated reference price
            prices_array: Full array of prices from AH search

        Returns:
            SubmitResult indicating success/failure
        """
        if not self.is_connected:
            return SubmitResult(success=False, error="Not connected")

        try:
            # Call the submit_price RPC function
            result = self._client.rpc(
                "submit_price",
                {
                    "p_device_id": device_id,
                    "p_config_base_id": config_base_id,
                    "p_season_id": season_id,
                    "p_price_fe": price_fe,
                    "p_prices_array": prices_array,
                },
            ).execute()

            # Check for rate limiting response
            if result.data and isinstance(result.data, dict):
                if result.data.get("rate_limited"):
                    return SubmitResult(
                        success=False,
                        error="Rate limited",
                        rate_limited=True,
                    )

            return SubmitResult(success=True)

        except Exception as e:
            error_str = str(e)
            rate_limited = "rate" in error_str.lower() or "429" in error_str
            return SubmitResult(
                success=False,
                error=error_str,
                rate_limited=rate_limited,
            )

    def fetch_prices_delta(
        self, season_id: int, since: Optional[datetime] = None
    ) -> list[CloudPrice]:
        """
        Fetch aggregated prices that have changed since a timestamp.

        Args:
            season_id: Season to fetch prices for
            since: Only fetch prices updated after this time (None = all)

        Returns:
            List of CloudPrice objects
        """
        if not self.is_connected:
            return []

        try:
            query = (
                self._client.table("aggregated_prices")
                .select("*")
                .eq("season_id", season_id)
            )

            if since:
                query = query.gt("updated_at", since.isoformat())

            result = query.execute()

            prices = []
            for row in result.data or []:
                prices.append(
                    CloudPrice(
                        config_base_id=row["config_base_id"],
                        season_id=row["season_id"],
                        price_fe_median=row["price_fe_median"],
                        price_fe_p10=row.get("price_fe_p10"),
                        price_fe_p90=row.get("price_fe_p90"),
                        submission_count=row.get("submission_count"),
                        unique_devices=row.get("unique_devices"),
                        updated_at=(
                            datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
                            if row.get("updated_at")
                            else None
                        ),
                    )
                )

            return prices

        except Exception as e:
            print(f"Cloud sync: Failed to fetch prices: {e}")
            return []

    def fetch_price_history(
        self, season_id: int, hours: int = 72
    ) -> list[CloudPriceHistory]:
        """
        Fetch price history for sparklines.

        Args:
            season_id: Season to fetch history for
            hours: Number of hours of history to fetch

        Returns:
            List of CloudPriceHistory objects
        """
        if not self.is_connected:
            return []

        try:
            # Calculate cutoff time
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            result = (
                self._client.table("price_history")
                .select("*")
                .eq("season_id", season_id)
                .gt("hour_bucket", cutoff.isoformat())
                .order("hour_bucket", desc=False)
                .execute()
            )

            history = []
            for row in result.data or []:
                history.append(
                    CloudPriceHistory(
                        config_base_id=row["config_base_id"],
                        season_id=row["season_id"],
                        hour_bucket=datetime.fromisoformat(
                            row["hour_bucket"].replace("Z", "+00:00")
                        ),
                        price_fe_median=row["price_fe_median"],
                        price_fe_p10=row.get("price_fe_p10"),
                        price_fe_p90=row.get("price_fe_p90"),
                        submission_count=row.get("submission_count"),
                    )
                )

            return history

        except Exception as e:
            print(f"Cloud sync: Failed to fetch price history: {e}")
            return []

    def fetch_item_history(
        self, config_base_id: int, season_id: int, hours: int = 72
    ) -> list[CloudPriceHistory]:
        """
        Fetch price history for a specific item.

        Args:
            config_base_id: Item to fetch history for
            season_id: Season to fetch history for
            hours: Number of hours of history to fetch

        Returns:
            List of CloudPriceHistory objects ordered by time
        """
        if not self.is_connected:
            return []

        try:
            # Calculate cutoff time
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            result = (
                self._client.table("price_history")
                .select("*")
                .eq("config_base_id", config_base_id)
                .eq("season_id", season_id)
                .gt("hour_bucket", cutoff.isoformat())
                .order("hour_bucket", desc=False)
                .execute()
            )

            history = []
            for row in result.data or []:
                history.append(
                    CloudPriceHistory(
                        config_base_id=row["config_base_id"],
                        season_id=row["season_id"],
                        hour_bucket=datetime.fromisoformat(
                            row["hour_bucket"].replace("Z", "+00:00")
                        ),
                        price_fe_median=row["price_fe_median"],
                        price_fe_p10=row.get("price_fe_p10"),
                        price_fe_p90=row.get("price_fe_p90"),
                        submission_count=row.get("submission_count"),
                    )
                )

            return history

        except Exception as e:
            print(f"Cloud sync: Failed to fetch item history: {e}")
            return []
