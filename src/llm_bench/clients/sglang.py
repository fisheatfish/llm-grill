"""SGLang client — OpenAI-compatible + /metrics Prometheus endpoint + /server_info."""

from __future__ import annotations

import logging

from .base import BaseClient
from .prometheus import parse_prometheus

logger = logging.getLogger(__name__)

_SGLANG_METRICS = [
    "sglang:cache_hit_rate",
    "sglang:num_running_reqs",
    "sglang:num_queue_reqs",
    "sglang:token_usage",
    "sglang:gen_throughput",
]


class SglangClient(BaseClient):
    async def backend_metrics(self) -> dict:
        """Fetch SGLang metrics from Prometheus /metrics.

        Uses /metrics (Prometheus) for kv_cache_usage (token_usage),
        cache_hit_rate, running/waiting reqs.
        """
        result: dict = {}

        try:
            resp = await self._http.get("/metrics")
            resp.raise_for_status()
            raw = parse_prometheus(resp.text, prefixes=_SGLANG_METRICS)
            result["kv_cache_usage"] = raw.get("sglang:token_usage")
            result["cache_hit_rate"] = raw.get("sglang:cache_hit_rate")
            result["requests_running"] = raw.get("sglang:num_running_reqs")
            result["requests_waiting"] = raw.get("sglang:num_queue_reqs")
            result["gen_throughput"] = raw.get("sglang:gen_throughput")
        except Exception:
            logger.debug("Failed to fetch SGLang /metrics for %s", self.server.name, exc_info=True)

        return result


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
