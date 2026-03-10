"""SGLang client — OpenAI-compatible + /get_server_info endpoint."""

from __future__ import annotations

from llm_bench.config import ServerConfig

from .base import BaseClient


class SglangClient(BaseClient):
    def __init__(self, server: ServerConfig) -> None:
        super().__init__(server)

    async def health(self) -> bool:
        try:
            resp = await self._http.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

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
                "internal_states": data.get("internal_states"),
            }
        except Exception:
            return {}
