"""Client factory — returns the right BaseClient subclass for a given backend."""

from __future__ import annotations

from llm_bench.config import Backend, ServerConfig

from .base import BaseClient
from .litellm import LiteLLMClient
from .llamacpp import LlamaCppClient
from .sglang import SglangClient
from .vllm import VllmClient

_REGISTRY: dict[Backend, type[BaseClient]] = {
    Backend.vllm: VllmClient,
    Backend.sglang: SglangClient,
    Backend.llamacpp: LlamaCppClient,
    Backend.litellm: LiteLLMClient,
    Backend.openai: VllmClient,  # OpenAI-compatible fallback — uses vLLM client (no extras)
}


def get_client(server: ServerConfig) -> BaseClient:
    """Instantiate the appropriate client for the given server config."""
    client_cls = _REGISTRY.get(server.backend, VllmClient)
    return client_cls(server)


__all__ = [
    "BaseClient",
    "VllmClient",
    "SglangClient",
    "LlamaCppClient",
    "LiteLLMClient",
    "get_client",
]
