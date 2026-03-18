"""LiteLLM proxy client — OpenAI-compatible + /health endpoint."""

from __future__ import annotations

import logging

from .base import BaseClient

logger = logging.getLogger(__name__)


class LiteLLMClient(BaseClient):
    async def health(self) -> bool:
        """Use /health/liveliness — /health triggers inference calls on all models."""
        for path in ("/health/liveliness", "/health"):
            try:
                resp = await self._http.get(path, timeout=10.0)
                if resp.status_code == 200:
                    return True
            except Exception:
                logger.debug(
                    "Health check failed (%s) for %s", path, self.server.name, exc_info=True
                )
        return False

    async def backend_metrics(self) -> dict:
        """LiteLLM exposes /metrics (Prometheus) when enabled."""
        try:
            resp = await self._http.get("/metrics")
            if resp.status_code != 200:
                return {}
            return {"raw_prometheus": resp.text[:2000]}
        except Exception:
            logger.debug("Failed to fetch LiteLLM metrics for %s", self.server.name, exc_info=True)
            return {}
