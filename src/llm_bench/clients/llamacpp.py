"""llama.cpp / llama-server client — OpenAI-compatible + /health endpoint."""

from __future__ import annotations

import logging

from .base import BaseClient, _HEALTH_TIMEOUT
from .prometheus import parse_prometheus

logger = logging.getLogger(__name__)


class LlamaCppClient(BaseClient):
    async def health(self) -> bool:
        """llama-server returns JSON body with a 'status' field."""
        try:
            resp = await self._http.get("/health", timeout=_HEALTH_TIMEOUT)
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception:
            logger.debug("Health check failed for %s", self.server.name, exc_info=True)
            return False

    async def backend_metrics(self) -> dict:
        """llama-server exposes /metrics (Prometheus) since build 3800+."""
        try:
            resp = await self._http.get("/metrics")
            if resp.status_code != 200:
                return {}
            return parse_prometheus(resp.text)
        except Exception:
            logger.debug(
                "Failed to fetch llama.cpp metrics for %s", self.server.name, exc_info=True
            )
            return {}
