"""Global test fixtures."""

import pytest

from titrack.data.inventory import set_gear_allowlist


@pytest.fixture(autouse=True)
def _reset_gear_allowlist():
    """Reset gear allowlist to empty after each test to prevent cross-test contamination."""
    yield
    set_gear_allowlist(frozenset())
