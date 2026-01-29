"""Device identification for cloud sync."""

import uuid
from typing import Optional

from titrack.db.repository import Repository


def get_or_create_device_id(repo: Repository) -> str:
    """
    Get or create a unique device identifier for cloud sync.

    The device ID is stored in the settings table and persists across sessions.
    This provides anonymous identification without requiring user accounts.

    Args:
        repo: Repository instance for database access

    Returns:
        UUID string representing this device
    """
    device_id = repo.get_setting("cloud_device_id")

    if device_id is None:
        # Generate new UUID v4
        device_id = str(uuid.uuid4())
        repo.set_setting("cloud_device_id", device_id)

    return device_id


def validate_device_id(device_id: Optional[str]) -> bool:
    """
    Validate that a device ID is a properly formatted UUID.

    Args:
        device_id: The device ID to validate

    Returns:
        True if valid UUID format, False otherwise
    """
    if not device_id:
        return False

    try:
        uuid.UUID(device_id)
        return True
    except (ValueError, AttributeError):
        return False
