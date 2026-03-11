"""SGLang client — OpenAI-compatible + /get_server_info endpoint."""

from __future__ import annotations

import logging

from .base import BaseClient

logger = logging.getLogger(__name__)


class SglangClient(BaseClient):
    async def backend_metrics(self) -> dict:
        """Fetch SGLang server info including KV cache usage.

        Notes:
            - cache_hit_rate requires SGLang to be started with --enable-cache-report.
            - kvcache is reported as a percentage (0-100) and normalized to 0-1.
        """
        try:
            resp = await self._http.get("/get_server_info")
            resp.raise_for_status()
            data = resp.json()
            kvcache_raw = _find_key(data, "kvcache")
            return {
                "kv_cache_usage": kvcache_raw / 100 if kvcache_raw is not None else None,
                "cache_hit_rate": _find_key(data, "cache_hit_rate"),
                "num_running_reqs": _find_key(data, "num_running_reqs"),
                "token_capacity": _find_key(data, "token_capacity"),
            }
        except Exception:
            logger.debug("Failed to fetch SGLang metrics for %s", self.server.name, exc_info=True)
            return {}


def _find_key(obj: object, key: str) -> object:
    """Recursively search for a key in a nested dict/list structure."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_key(item, key)
            if found is not None:
                return found
    return None
