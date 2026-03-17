"""vLLM client — OpenAI-compatible + /metrics Prometheus endpoint."""

from __future__ import annotations

import logging

from .base import BaseClient
from .prometheus import parse_prometheus

logger = logging.getLogger(__name__)

_VLLM_METRICS = [
    "vllm:kv_cache_usage_perc",  # vLLM >= 0.4 (renamed from gpu_cache_usage_perc)
    "vllm:gpu_cache_usage_perc",  # vLLM < 0.4 (kept for backwards compatibility)
    "vllm:prefix_cache_hits_total",  # cumulative prefix cache hits (tokens)
    "vllm:prefix_cache_queries_total",  # cumulative prefix cache queries (tokens)
    "vllm:num_requests_running",
    "vllm:num_requests_waiting",
    "vllm:avg_prompt_throughput_toks_per_s",
    "vllm:avg_generation_throughput_toks_per_s",
]


class VllmClient(BaseClient):
    async def backend_metrics(self) -> dict:
        """Scrape Prometheus /metrics and return key vLLM KV-cache metrics."""
        try:
            resp = await self._http.get("/metrics")
            resp.raise_for_status()
            raw = parse_prometheus(resp.text, prefixes=_VLLM_METRICS)

            # Handle metric rename between vLLM versions
            kv_usage = raw.get("vllm:kv_cache_usage_perc") or raw.get("vllm:gpu_cache_usage_perc")

            # Prefix cache hit rate derived from cumulative counters
            hits = raw.get("vllm:prefix_cache_hits_total", 0)
            queries = raw.get("vllm:prefix_cache_queries_total", 0)
            cache_hit_rate = hits / queries if queries else None

            return {
                "kv_cache_usage": kv_usage,
                "cache_hit_rate": cache_hit_rate,
                "requests_running": raw.get("vllm:num_requests_running"),
                "requests_waiting": raw.get("vllm:num_requests_waiting"),
            }
        except Exception:
            logger.debug("Failed to fetch vLLM metrics for %s", self.server.name, exc_info=True)
            return {}
