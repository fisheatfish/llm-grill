"""llama.cpp / llama-server client — OpenAI-compatible + /health endpoint."""

from __future__ import annotations

from llm_bench.config import ServerConfig

from .base import BaseClient


class LlamaCppClient(BaseClient):
    def __init__(self, server: ServerConfig) -> None:
        super().__init__(server)

    async def health(self) -> bool:
        try:
            resp = await self._http.get("/health")
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception:
            return False

    async def backend_metrics(self) -> dict:
        """llama-server exposes /metrics (Prometheus) since build 3800+."""
        try:
            resp = await self._http.get("/metrics")
            if resp.status_code != 200:
                return {}
            return _parse_llamacpp_prometheus(resp.text)
        except Exception:
            return {}


def _parse_llamacpp_prometheus(text: str) -> dict:
    result: dict = {}
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        parts = line.rsplit(" ", 1)
        if len(parts) == 2:
            key = parts[0].strip()
            try:
                result[key] = float(parts[1])
            except ValueError:
                pass
    return result
