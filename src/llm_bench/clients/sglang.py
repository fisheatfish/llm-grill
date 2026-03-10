"""SGLang client — OpenAI-compatible + /get_server_info endpoint."""

from __future__ import annotations

import logging

from .base import BaseClient

logger = logging.getLogger(__name__)


class SglangClient(BaseClient):
    async def backend_metrics(self) -> dict:
        """Fetch SGLang server info including cache hit rate."""
        try:
            resp = await self._http.get("/get_server_info")
            resp.raise_for_status()
            data = resp.json()
            return {
                "cache_hit_rate": data.get("cache_hit_rate"),
                "num_running_reqs": data.get("num_running_reqs"),
                "num_waiting_reqs": data.get("num_waiting_reqs"),
                "token_usage": data.get("token_usage"),
            }
        except Exception:
            logger.debug("Failed to fetch SGLang metrics for %s", self.server.name, exc_info=True)
            return {}
