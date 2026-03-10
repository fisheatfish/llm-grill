"""vLLM client — OpenAI-compatible + /metrics Prometheus endpoint."""

from __future__ import annotations

from llm_bench.config import ServerConfig

from .base import BaseClient


class VllmClient(BaseClient):
    def __init__(self, server: ServerConfig) -> None:
        super().__init__(server)

    async def health(self) -> bool:
        try:
            resp = await self._http.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def backend_metrics(self) -> dict:
        """Scrape Prometheus /metrics and return key vLLM KV-cache metrics."""
        try:
            resp = await self._http.get("/metrics")
            resp.raise_for_status()
            return _parse_prometheus(resp.text, prefixes=[
                "vllm:gpu_cache_usage_perc",
                "vllm:cpu_cache_usage_perc",
                "vllm:num_requests_running",
                "vllm:num_requests_waiting",
                "vllm:avg_prompt_throughput_toks_per_s",
                "vllm:avg_generation_throughput_toks_per_s",
            ])
        except Exception:
            return {}


def _parse_prometheus(text: str, prefixes: list[str]) -> dict:
    """Extract gauge/counter values from Prometheus text format."""
    result: dict = {}
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        for prefix in prefixes:
            if line.startswith(prefix):
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    key = parts[0].split("{")[0]
                    try:
                        result[key] = float(parts[1])
                    except ValueError:
                        pass
    return result
