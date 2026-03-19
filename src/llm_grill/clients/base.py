"""Abstract base class for all inference backend clients."""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from llm_grill.config import BackendConfig, Message, ModelConfig

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT = 10.0  # seconds — shorter than inference timeout


@dataclass
class StreamResult:
    content: str
    ttft_s: float
    e2e_latency_s: float
    tpot_s: float
    prompt_tokens: int
    completion_tokens: int
    tokens_per_second: float


class BaseClient(ABC):
    def __init__(self, server: BackendConfig) -> None:
        self.server = server
        base = str(server.url).rstrip("/")
        headers = {}
        if server.api_key and server.api_key != "none":
            headers["Authorization"] = f"Bearer {server.api_key}"
        self._http = httpx.AsyncClient(
            base_url=base,
            headers=headers,
            timeout=server.timeout,
        )

    async def __aenter__(self) -> BaseClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._http.aclose()

    # --- public interface ---

    async def complete(self, messages: list[Message], model: ModelConfig) -> StreamResult:
        """Send a streaming chat completion and measure TTFT/TPOT/E2E."""
        payload = self._build_payload(messages, model)
        content_parts: list[str] = []
        t0 = time.perf_counter()
        t_first: float | None = None
        prompt_tokens = 0
        completion_tokens = 0

        logger.debug("POST /v1/chat/completions server=%s model=%s", self.server.name, model.name)

        async with self._http.stream("POST", "/v1/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[len("data:") :].strip()
                if raw == "[DONE]":
                    break
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    logger.debug("Skipping malformed SSE chunk: %r", raw[:100])
                    continue
                if chunk.get("usage"):
                    prompt_tokens = chunk["usage"].get("prompt_tokens", 0)
                    completion_tokens = chunk["usage"].get("completion_tokens", 0)
                choices = chunk.get("choices") or []
                delta = choices[0].get("delta", {}) if choices else {}
                token = delta.get("content") or ""
                if token:
                    if t_first is None:
                        t_first = time.perf_counter()
                    content_parts.append(token)

        # Always record end time after the stream closes, even without [DONE]
        t_last = time.perf_counter()
        t_first = t_first or t_last
        ttft = t_first - t0
        e2e = t_last - t0
        if completion_tokens == 0:
            completion_tokens = len(content_parts)
        tpot = (e2e - ttft) / max(completion_tokens - 1, 1)
        tps = completion_tokens / e2e if e2e else 0.0

        logger.debug(
            "Done server=%s TTFT=%.3fs E2E=%.3fs tokens=%d",
            self.server.name,
            ttft,
            e2e,
            completion_tokens,
        )

        return StreamResult(
            content="".join(content_parts),
            ttft_s=ttft,
            e2e_latency_s=e2e,
            tpot_s=tpot,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tokens_per_second=tps,
        )

    async def health(self) -> bool:
        """Return True if the server is reachable. Override for custom health checks."""
        try:
            resp = await self._http.get("/health", timeout=_HEALTH_TIMEOUT)
            return resp.status_code == 200
        except Exception:
            logger.debug("Health check failed for %s", self.server.name, exc_info=True)
            return False

    @abstractmethod
    async def backend_metrics(self) -> dict:
        """Return backend-specific raw metrics (empty dict if unavailable)."""

    # --- helpers ---

    def _build_payload(self, messages: list[Message], model: ModelConfig) -> dict:
        return {
            "model": model.name,
            "messages": [m.model_dump() for m in messages],
            "max_tokens": model.max_tokens,
            "temperature": model.temperature,
            "top_p": model.top_p,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
