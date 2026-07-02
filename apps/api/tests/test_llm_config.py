"""Regression tests for LLM client config (Azure v1 route api-version)."""

from laboratree.core.llm import resolve_azure_api_version


def test_v1_route_forces_preview_api_version():
    # The /openai/v1 route rejects dated versions -> must become "preview".
    assert resolve_azure_api_version(
        "https://x.openai.azure.com/openai/v1", "2024-12-01-preview"
    ) == "preview"
    assert resolve_azure_api_version("https://x.openai.azure.com/openai/v1/", "anything") == "preview"


def test_legacy_route_keeps_configured_version():
    assert resolve_azure_api_version(
        "https://x.openai.azure.com/openai/deployments/foo", "2024-12-01-preview"
    ) == "2024-12-01-preview"
