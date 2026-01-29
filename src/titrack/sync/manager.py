"""Sync manager - orchestrates cloud sync operations."""

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional

from titrack.db.connection import Database
from titrack.db.repository import Repository
from titrack.sync.client import CloudClient, CloudPrice, CloudPriceHistory
from titrack.sync.device import get_or_create_device_id


class SyncStatus(Enum):
    """Cloud sync status states."""

    DISABLED = "disabled"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SYNCING = "syncing"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class SyncStatusInfo:
    """Detailed sync status information."""

    status: SyncStatus
    enabled: bool
    upload_enabled: bool
    download_enabled: bool
    queue_pending: int
    queue_failed: int
    last_upload: Optional[datetime] = None
    last_download: Optional[datetime] = None
    last_error: Optional[str] = None
    cloud_available: bool = False


class SyncManager:
    """
    Manages cloud sync operations for crowd-sourced pricing.

    Handles:
    - Queueing price submissions for upload
    - Background upload loop (every 60s)
    - Background download loop (prices every 5min, history every 1-6hr)
    - Status tracking and reporting
    """

    # Sync intervals in seconds
    UPLOAD_INTERVAL = 60  # Upload queue every 60s
    PRICE_DOWNLOAD_INTERVAL = 300  # Download prices every 5 minutes
    HISTORY_DOWNLOAD_INTERVAL_MIN = 3600  # 1 hour minimum
    HISTORY_DOWNLOAD_INTERVAL_MAX = 21600  # 6 hours maximum

    # Queue settings
    MAX_RETRY_ATTEMPTS = 3
    BATCH_SIZE = 50  # Max items to upload per batch

    def __init__(
        self,
        db: Database,
        on_status_change: Optional[Callable[[SyncStatusInfo], None]] = None,
    ) -> None:
        """
        Initialize sync manager.

        Args:
            db: Database connection for queue and cache storage
            on_status_change: Callback when sync status changes
        """
        self.db = db
        self.repo = Repository(db)
        self.client = CloudClient()
        self._on_status_change = on_status_change

        self._device_id: Optional[str] = None
        self._season_id: Optional[int] = None

        # Background thread state
        self._running = False
        self._upload_thread: Optional[threading.Thread] = None
        self._download_thread: Optional[threading.Thread] = None

        # Status tracking
        self._status = SyncStatus.DISABLED
        self._last_error: Optional[str] = None
        self._last_upload: Optional[datetime] = None
        self._last_download: Optional[datetime] = None
        self._last_history_download: Optional[datetime] = None

    def set_season_context(self, season_id: Optional[int]) -> None:
        """Set the current season for filtering data."""
        self._season_id = season_id
        self.repo.set_player_context(season_id, None)

    @property
    def is_enabled(self) -> bool:
        """Check if cloud sync is enabled."""
        return self.repo.get_setting("cloud_sync_enabled") == "true"

    @property
    def is_upload_enabled(self) -> bool:
        """Check if upload is enabled."""
        setting = self.repo.get_setting("cloud_upload_enabled")
        return setting is None or setting == "true"  # Default true

    @property
    def is_download_enabled(self) -> bool:
        """Check if download is enabled."""
        setting = self.repo.get_setting("cloud_download_enabled")
        return setting is None or setting == "true"  # Default true

    def enable(self) -> bool:
        """
        Enable cloud sync.

        Returns:
            True if successfully enabled and connected, False otherwise
        """
        if not self.client.is_available:
            self._last_error = "Supabase SDK not installed"
            return False

        # Check if Supabase is configured
        url, key = self.client.get_config()
        if not url or not key:
            self._last_error = "Supabase not configured"
            return False

        self._set_status(SyncStatus.CONNECTING)

        # Try to connect
        if not self.client.connect():
            self._set_status(SyncStatus.ERROR)
            self._last_error = "Failed to connect to cloud service"
            return False

        # Get/create device ID
        self._device_id = get_or_create_device_id(self.repo)

        # Save enabled state
        self.repo.set_setting("cloud_sync_enabled", "true")

        self._set_status(SyncStatus.CONNECTED)
        self.start_background_sync()
        return True

    def disable(self) -> None:
        """Disable cloud sync."""
        self.stop_background_sync()
        self.client.disconnect()
        self.repo.set_setting("cloud_sync_enabled", "false")
        self._set_status(SyncStatus.DISABLED)

    def start_background_sync(self) -> None:
        """Start background sync threads."""
        if self._running:
            return

        self._running = True

        # Start upload thread
        self._upload_thread = threading.Thread(
            target=self._upload_loop, daemon=True, name="cloud-sync-upload"
        )
        self._upload_thread.start()

        # Start download thread
        self._download_thread = threading.Thread(
            target=self._download_loop, daemon=True, name="cloud-sync-download"
        )
        self._download_thread.start()

        print("Cloud sync: Background threads started")

    def stop_background_sync(self) -> None:
        """Stop background sync threads."""
        self._running = False

        # Threads are daemonic, so they'll stop when main thread exits
        # Just wait briefly for clean shutdown
        if self._upload_thread and self._upload_thread.is_alive():
            self._upload_thread.join(timeout=2.0)
        if self._download_thread and self._download_thread.is_alive():
            self._download_thread.join(timeout=2.0)

        self._upload_thread = None
        self._download_thread = None

    def queue_price_submission(
        self,
        config_base_id: int,
        season_id: int,
        price_fe: float,
        prices_array: list[float],
    ) -> None:
        """
        Queue a price submission for upload.

        Args:
            config_base_id: Item type ID
            season_id: Current season ID
            price_fe: Calculated reference price
            prices_array: Full array of prices from AH search
        """
        if not self.is_enabled or not self.is_upload_enabled:
            return

        # Store in queue
        self.db.execute(
            """
            INSERT INTO cloud_sync_queue
            (config_base_id, season_id, price_fe, prices_array, queued_at, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (
                config_base_id,
                season_id,
                price_fe,
                json.dumps(prices_array),
                datetime.now().isoformat(),
            ),
        )

    def get_status_info(self) -> SyncStatusInfo:
        """Get current sync status information."""
        # Count queue items
        pending_row = self.db.fetchone(
            "SELECT COUNT(*) FROM cloud_sync_queue WHERE status = 'pending'"
        )
        pending = pending_row[0] if pending_row else 0

        failed_row = self.db.fetchone(
            "SELECT COUNT(*) FROM cloud_sync_queue WHERE status = 'failed'"
        )
        failed = failed_row[0] if failed_row else 0

        return SyncStatusInfo(
            status=self._status,
            enabled=self.is_enabled,
            upload_enabled=self.is_upload_enabled,
            download_enabled=self.is_download_enabled,
            queue_pending=pending,
            queue_failed=failed,
            last_upload=self._last_upload,
            last_download=self._last_download,
            last_error=self._last_error,
            cloud_available=self.client.is_available,
        )

    def trigger_sync(self) -> dict:
        """
        Trigger an immediate sync.

        Returns:
            Dict with sync results
        """
        if not self.is_enabled:
            return {"success": False, "error": "Cloud sync not enabled"}

        if not self.client.is_connected:
            if not self.client.connect():
                return {"success": False, "error": "Failed to connect"}

        results = {"success": True, "uploaded": 0, "downloaded": 0}

        # Upload pending items
        if self.is_upload_enabled:
            uploaded = self._process_upload_queue()
            results["uploaded"] = uploaded

        # Download new prices
        if self.is_download_enabled:
            downloaded = self._download_prices()
            results["downloaded"] = downloaded

        return results

    def get_cached_cloud_prices(self, season_id: Optional[int] = None) -> list[dict]:
        """
        Get cached cloud prices from local database.

        Args:
            season_id: Filter by season (uses current if None)

        Returns:
            List of price dicts
        """
        season_id = season_id or self._season_id or 0

        rows = self.db.fetchall(
            """
            SELECT config_base_id, season_id, price_fe_median, price_fe_p10,
                   price_fe_p90, submission_count, unique_devices,
                   cloud_updated_at, cached_at
            FROM cloud_price_cache
            WHERE season_id = ?
            """,
            (season_id,),
        )

        return [
            {
                "config_base_id": row["config_base_id"],
                "season_id": row["season_id"],
                "price_fe_median": row["price_fe_median"],
                "price_fe_p10": row["price_fe_p10"],
                "price_fe_p90": row["price_fe_p90"],
                "submission_count": row["submission_count"],
                "unique_devices": row["unique_devices"],
                "cloud_updated_at": row["cloud_updated_at"],
                "cached_at": row["cached_at"],
            }
            for row in rows
        ]

    def get_cached_price_history(
        self, config_base_id: int, season_id: Optional[int] = None
    ) -> list[dict]:
        """
        Get cached price history for an item from local database.

        Args:
            config_base_id: Item to get history for
            season_id: Filter by season (uses current if None)

        Returns:
            List of history point dicts
        """
        season_id = season_id or self._season_id or 0

        rows = self.db.fetchall(
            """
            SELECT config_base_id, season_id, hour_bucket, price_fe_median,
                   price_fe_p10, price_fe_p90, submission_count
            FROM cloud_price_history
            WHERE config_base_id = ? AND season_id = ?
            ORDER BY hour_bucket ASC
            """,
            (config_base_id, season_id),
        )

        return [
            {
                "config_base_id": row["config_base_id"],
                "season_id": row["season_id"],
                "hour_bucket": row["hour_bucket"],
                "price_fe_median": row["price_fe_median"],
                "price_fe_p10": row["price_fe_p10"],
                "price_fe_p90": row["price_fe_p90"],
                "submission_count": row["submission_count"],
            }
            for row in rows
        ]

    def _set_status(self, status: SyncStatus) -> None:
        """Update status and notify callback."""
        self._status = status
        if self._on_status_change:
            self._on_status_change(self.get_status_info())

    def _upload_loop(self) -> None:
        """Background thread for uploading queued prices."""
        while self._running:
            try:
                if self.is_enabled and self.is_upload_enabled:
                    if self.client.is_connected:
                        self._process_upload_queue()
                    elif self.client.is_available:
                        # Try to reconnect
                        self.client.connect()
            except Exception as e:
                self._last_error = str(e)
                print(f"Cloud sync upload error: {e}")

            # Sleep in small increments to allow quick shutdown
            for _ in range(self.UPLOAD_INTERVAL):
                if not self._running:
                    break
                time.sleep(1)

    def _download_loop(self) -> None:
        """Background thread for downloading cloud prices."""
        while self._running:
            try:
                if self.is_enabled and self.is_download_enabled:
                    if self.client.is_connected:
                        self._download_prices()
                        self._maybe_download_history()
                    elif self.client.is_available:
                        # Try to reconnect
                        self.client.connect()
            except Exception as e:
                self._last_error = str(e)
                print(f"Cloud sync download error: {e}")

            # Sleep in small increments
            for _ in range(self.PRICE_DOWNLOAD_INTERVAL):
                if not self._running:
                    break
                time.sleep(1)

    def _process_upload_queue(self) -> int:
        """
        Process pending items in the upload queue.

        Returns:
            Number of items successfully uploaded
        """
        if not self._device_id:
            self._device_id = get_or_create_device_id(self.repo)

        # Get pending items
        rows = self.db.fetchall(
            """
            SELECT id, config_base_id, season_id, price_fe, prices_array, attempts
            FROM cloud_sync_queue
            WHERE status = 'pending'
            ORDER BY queued_at ASC
            LIMIT ?
            """,
            (self.BATCH_SIZE,),
        )

        if not rows:
            return 0

        uploaded = 0
        for row in rows:
            try:
                prices_array = json.loads(row["prices_array"])

                result = self.client.submit_price(
                    device_id=self._device_id,
                    config_base_id=row["config_base_id"],
                    season_id=row["season_id"],
                    price_fe=row["price_fe"],
                    prices_array=prices_array,
                )

                if result.success:
                    # Mark as uploaded
                    self.db.execute(
                        "DELETE FROM cloud_sync_queue WHERE id = ?", (row["id"],)
                    )
                    uploaded += 1
                elif result.rate_limited:
                    # Don't increment attempts, just wait
                    break  # Stop processing this batch
                else:
                    # Increment attempts
                    attempts = row["attempts"] + 1
                    if attempts >= self.MAX_RETRY_ATTEMPTS:
                        self.db.execute(
                            "UPDATE cloud_sync_queue SET status = 'failed', attempts = ? WHERE id = ?",
                            (attempts, row["id"]),
                        )
                    else:
                        self.db.execute(
                            "UPDATE cloud_sync_queue SET attempts = ? WHERE id = ?",
                            (attempts, row["id"]),
                        )

            except Exception as e:
                print(f"Cloud sync: Error uploading item {row['id']}: {e}")
                # Increment attempts
                attempts = row["attempts"] + 1
                self.db.execute(
                    "UPDATE cloud_sync_queue SET attempts = ? WHERE id = ?",
                    (attempts, row["id"]),
                )

        if uploaded > 0:
            self._last_upload = datetime.now()

        return uploaded

    def _download_prices(self) -> int:
        """
        Download updated prices from cloud.

        Returns:
            Number of prices downloaded/updated
        """
        if not self._season_id:
            return 0

        # Get last sync timestamp
        last_sync_str = self.repo.get_setting("cloud_last_price_sync")
        last_sync = None
        if last_sync_str:
            try:
                last_sync = datetime.fromisoformat(last_sync_str)
            except ValueError:
                pass

        # Fetch delta
        prices = self.client.fetch_prices_delta(self._season_id, since=last_sync)

        if not prices:
            return 0

        # Upsert into cache
        for price in prices:
            self.db.execute(
                """
                INSERT OR REPLACE INTO cloud_price_cache
                (config_base_id, season_id, price_fe_median, price_fe_p10,
                 price_fe_p90, submission_count, unique_devices,
                 cloud_updated_at, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    price.config_base_id,
                    price.season_id,
                    price.price_fe_median,
                    price.price_fe_p10,
                    price.price_fe_p90,
                    price.submission_count,
                    price.unique_devices,
                    price.updated_at.isoformat() if price.updated_at else None,
                ),
            )

        # Update last sync timestamp
        self.repo.set_setting("cloud_last_price_sync", datetime.now().isoformat())
        self._last_download = datetime.now()

        return len(prices)

    def _maybe_download_history(self) -> int:
        """
        Download price history if enough time has passed.

        Returns:
            Number of history points downloaded
        """
        if not self._season_id:
            return 0

        # Check if we need to download history
        if self._last_history_download:
            elapsed = (datetime.now() - self._last_history_download).total_seconds()
            if elapsed < self.HISTORY_DOWNLOAD_INTERVAL_MIN:
                return 0

        # Fetch history
        history = self.client.fetch_price_history(self._season_id, hours=72)

        if not history:
            return 0

        # Clear old history and insert new
        self.db.execute(
            "DELETE FROM cloud_price_history WHERE season_id = ?", (self._season_id,)
        )

        for point in history:
            self.db.execute(
                """
                INSERT INTO cloud_price_history
                (config_base_id, season_id, hour_bucket, price_fe_median,
                 price_fe_p10, price_fe_p90, submission_count, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    point.config_base_id,
                    point.season_id,
                    point.hour_bucket.isoformat(),
                    point.price_fe_median,
                    point.price_fe_p10,
                    point.price_fe_p90,
                    point.submission_count,
                ),
            )

        # Update last history sync
        self.repo.set_setting("cloud_last_history_sync", datetime.now().isoformat())
        self._last_history_download = datetime.now()

        return len(history)

    def initialize(self) -> None:
        """
        Initialize sync manager on startup.

        Checks if sync was enabled and reconnects if so.
        """
        if not self.is_enabled:
            return

        if not self.client.is_available:
            print("Cloud sync: Supabase SDK not available")
            return

        # Check config
        url, key = self.client.get_config()
        if not url or not key:
            print("Cloud sync: Not configured (missing URL or key)")
            return

        # Try to connect
        self._set_status(SyncStatus.CONNECTING)

        if self.client.connect():
            self._device_id = get_or_create_device_id(self.repo)
            self._set_status(SyncStatus.CONNECTED)
            self.start_background_sync()
            print("Cloud sync: Reconnected and background sync started")
        else:
            self._set_status(SyncStatus.OFFLINE)
            print("Cloud sync: Failed to connect (will retry)")
