"""Shared pytest fixtures."""

import pytest

from laboratree.core.registry import discover


@pytest.fixture(scope="session", autouse=True)
def _discover_components():
    """Ensure all Lab components are registered before any test (idempotent)."""
    discover()
