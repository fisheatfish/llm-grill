"""Abstract base class for all inference backend clients."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from llm_bench.config import Message, ModelConfig, ServerConfig


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
    def __init__(self, server: ServerConfig) -> None:
        self.server = server
        base = str(server.url).rstrip("/")
        headers = {"Authorization": f"Bearer {server.api_key}"}
        self._http = httpx.AsyncClient(
            base_url=base,
            headers=headers,
            timeout=server.timeout,
        )

    async def __aenter__(self) -> BaseClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._http.aclose()

    async def close(self) -> None:
        await self._http.aclose()

    # --- public interface ---

    async def complete(self, messages: list[Message], model: ModelConfig) -> StreamResult:
        """Send a streaming chat completion and return measured metrics."""
        payload = self._build_payload(messages, model)
        content_parts: list[str] = []
        t0 = time.perf_counter()
        t_first: float | None = None
        t_last = t0
        prompt_tokens = 0
        completion_tokens = 0

        async with self._http.stream("POST", "/v1/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[len("data:"):].strip()
                if raw == "[DONE]":
                    t_last = time.perf_counter()
                    break
                chunk = json.loads(raw)
                # extract usage if present (last chunk on some backends)
                if chunk.get("usage"):
                    prompt_tokens = chunk["usage"].get("prompt_tokens", 0)
                    completion_tokens = chunk["usage"].get("completion_tokens", 0)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                token = delta.get("content") or ""
                if token:
                    if t_first is None:
                        t_first = time.perf_counter()
                    content_parts.append(token)

        t_first = t_first or t_last
        ttft = t_first - t0
        e2e = t_last - t0
        decode_time = e2e - ttft
        if completion_tokens == 0:
            completion_tokens = len(content_parts)
        tpot = decode_time / max(completion_tokens - 1, 1)
        tps = completion_tokens / e2e if e2e else 0.0

        return StreamResult(
            content="".join(content_parts),
            ttft_s=ttft,
            e2e_latency_s=e2e,
            tpot_s=tpot,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tokens_per_second=tps,
        )

    @abstractmethod
    async def health(self) -> bool:
        """Return True if the server is reachable and ready."""

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
