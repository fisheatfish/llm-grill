"""LiteLLM proxy client — OpenAI-compatible + /health endpoint."""

from __future__ import annotations

from llm_bench.config import ServerConfig

from .base import BaseClient


class LiteLLMClient(BaseClient):
    def __init__(self, server: ServerConfig) -> None:
        super().__init__(server)

    async def health(self) -> bool:
        try:
            resp = await self._http.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def backend_metrics(self) -> dict:
        """LiteLLM exposes /metrics (Prometheus) when enabled."""
        try:
            resp = await self._http.get("/metrics")
            if resp.status_code != 200:
                return {}
            # Return raw text for now; structured parsing is backend-specific
            return {"raw_prometheus": resp.text[:2000]}
        except Exception:
            return {}
