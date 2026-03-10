"""vLLM client — OpenAI-compatible + /metrics Prometheus endpoint."""

from __future__ import annotations

import logging

from .base import BaseClient
from .prometheus import parse_prometheus

logger = logging.getLogger(__name__)

_VLLM_METRICS = [
    "vllm:gpu_cache_usage_perc",
    "vllm:cpu_cache_usage_perc",
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
            return parse_prometheus(resp.text, prefixes=_VLLM_METRICS)
        except Exception:
            logger.debug("Failed to fetch vLLM metrics for %s", self.server.name, exc_info=True)
            return {}
