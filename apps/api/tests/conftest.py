"""Shared pytest fixtures."""

import os

# Keep the suite offline + deterministic: never hit the live web-search providers, even though a
# developer's .env may carry real Brave/SerpAPI keys. Must run before settings are first imported.
os.environ.setdefault("WEB_SEARCH_PROVIDER", "none")

import pytest  # noqa: E402

from laboratree.core.registry import discover  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _discover_components():
    """Ensure all Lab components are registered before any test (idempotent)."""
    discover()
