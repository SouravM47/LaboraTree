"""Pluggable LLM client — the agents' brain. Supports Azure OpenAI and plain OpenAI.

Azure is reached through its OpenAI-compatible ``/openai/v1`` route, which works for both
gpt-5.x deployments and serverless models (e.g. DeepSeek). Swapping providers is a config flip.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from openai import BadRequestError, OpenAI

from ..config import settings
from .observability import record_llm_call


def resolve_azure_api_version(base_url: str, configured: str) -> str:
    """The /openai/v1 route only accepts 'preview'/'latest'; dated versions 400.

    Falls back to the configured value for the legacy deployments route.
    """
    if base_url.rstrip("/").endswith("/openai/v1"):
        return "preview"
    return configured


class LLMClient:
    """Minimal provider-agnostic client implementing the SDK ``LLM`` protocol."""

    def __init__(self) -> None:
        self.provider = settings.llm_provider.lower()
        if self.provider == "azure":
            base_url = settings.azure_openai_v1_endpoint.rstrip("/")
            api_version = resolve_azure_api_version(base_url, settings.azure_openai_api_version)
            self._client = OpenAI(
                api_key=settings.azure_openai_api_key,
                base_url=base_url,
                default_query={"api-version": api_version},
            )
            self._chat_model = settings.azure_openai_deployment_name
            self._embed_model = settings.azure_openai_embedding_deployment
            self._temperature: float | None = settings.azure_openai_temperature
        else:
            # base_url lets us target any OpenAI-compatible provider (DeepSeek, DeepInfra, OpenRouter,
            # Together, Fireworks, self-hosted vLLM). Blank → the real OpenAI endpoint.
            self._client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url or None,
            )
            self._chat_model = settings.openai_model
            self._embed_model = settings.openai_embedding_model
            self._temperature = None

    def model_for(self, role: str = "default") -> str:
        """Role-specific model override, falling back to the default chat model."""
        if role == "generation" and settings.generation_model:
            return settings.generation_model
        if role == "reasoning" and settings.reasoning_model:
            return settings.reasoning_model
        return self._chat_model

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        role: str = "default",
        **kw: Any,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        params: dict[str, Any] = {"model": self.model_for(role), "messages": messages}
        if self._temperature is not None:
            params["temperature"] = self._temperature
        params.update(kw)
        start = time.perf_counter()
        try:
            try:
                resp = self._client.chat.completions.create(**params)
            except BadRequestError as exc:
                # gpt-5.x reasoning models reject a non-default temperature; retry without.
                if "temperature" in str(exc) and "temperature" in params:
                    params.pop("temperature")
                    resp = self._client.chat.completions.create(**params)
                else:
                    raise
        except Exception as exc:
            self._trace(params.get("model", ""), role, None,
                        (time.perf_counter() - start) * 1000, "error", str(exc))
            raise
        self._trace(params["model"], role, getattr(resp, "usage", None),
                    (time.perf_counter() - start) * 1000, "ok", None)
        return resp.choices[0].message.content or ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        start = time.perf_counter()
        try:
            resp = self._client.embeddings.create(model=self._embed_model, input=texts)
        except Exception as exc:
            self._trace(self._embed_model, "embed", None,
                        (time.perf_counter() - start) * 1000, "error", str(exc))
            raise
        self._trace(self._embed_model, "embed", getattr(resp, "usage", None),
                    (time.perf_counter() - start) * 1000, "ok", None)
        return [item.embedding for item in resp.data]

    def _trace(self, model, role, usage, latency_ms, status, error) -> None:
        pt = int(getattr(usage, "prompt_tokens", 0) or 0)
        ct = int(getattr(usage, "completion_tokens", 0) or 0)
        tt = int(getattr(usage, "total_tokens", 0) or (pt + ct))
        try:
            record_llm_call(provider=self.provider, model=model or "", role=role, prompt_tokens=pt,
                            completion_tokens=ct, total_tokens=tt, latency_ms=latency_ms,
                            status=status, error=error)
        except Exception:
            pass

    def configured(self) -> bool:
        """Whether an API key is present (agents can run)."""
        if self.provider == "azure":
            return bool(settings.azure_openai_api_key and settings.azure_openai_v1_endpoint)
        return bool(settings.openai_api_key)


@lru_cache
def get_llm() -> LLMClient:
    return LLMClient()
