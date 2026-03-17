"""Tests for backend clients using respx to mock HTTP."""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

from llm_bench.clients import get_client
from llm_bench.config import Backend, Message, ModelConfig, BackendConfig


def _sse_body(tokens: list[str], model: str = "m", prompt_tokens: int = 10) -> bytes:
    """Build a minimal OpenAI-compatible SSE response."""
    lines = []
    for i, token in enumerate(tokens):
        chunk = {
            "id": "test",
            "object": "chat.completion.chunk",
            "choices": [{"delta": {"content": token}, "finish_reason": None}],
        }
        lines.append(f"data: {json.dumps(chunk)}")
    # Final chunk with usage
    final = {
        "id": "test",
        "object": "chat.completion.chunk",
        "choices": [{"delta": {}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": len(tokens)},
    }
    lines.append(f"data: {json.dumps(final)}")
    lines.append("data: [DONE]")
    return "\n".join(lines).encode()


@pytest.fixture()
def vllm_server() -> BackendConfig:
    return BackendConfig(
        name="vllm-test",
        url="http://test-vllm:8000",
        type=Backend.vllm,
    )


@pytest.fixture()
def model() -> ModelConfig:
    return ModelConfig(name="test-model", max_tokens=16)


@pytest.fixture()
def messages() -> list[Message]:
    return [Message(role="user", content="hello")]


class TestGetClient:
    def test_returns_vllm_client(self, vllm_server: BackendConfig) -> None:
        from llm_bench.clients.vllm import VllmClient

        client = get_client(vllm_server)
        assert isinstance(client, VllmClient)

    def test_returns_sglang_client(self) -> None:
        from llm_bench.clients.sglang import SglangClient

        server = BackendConfig(name="s", url="http://localhost:30000", type=Backend.sglang)
        assert isinstance(get_client(server), SglangClient)

    def test_returns_llamacpp_client(self) -> None:
        from llm_bench.clients.llamacpp import LlamaCppClient

        server = BackendConfig(name="s", url="http://localhost:8080", type=Backend.llamacpp)
        assert isinstance(get_client(server), LlamaCppClient)


@pytest.mark.asyncio
class TestVllmClientComplete:
    @respx.mock
    async def test_complete_success(
        self,
        vllm_server: BackendConfig,
        model: ModelConfig,
        messages: list[Message],
    ) -> None:
        respx.post("http://test-vllm:8000/v1/chat/completions").mock(
            return_value=Response(
                200,
                content=_sse_body(["Hello", " world"]),
                headers={"content-type": "text/event-stream"},
            )
        )
        async with get_client(vllm_server) as client:
            result = await client.complete(messages, model)

        assert result.content == "Hello world"
        assert result.completion_tokens == 2
        assert result.prompt_tokens == 10
        assert result.ttft_s >= 0
        assert result.e2e_latency_s >= result.ttft_s

    @respx.mock
    async def test_complete_http_error(
        self,
        vllm_server: BackendConfig,
        model: ModelConfig,
        messages: list[Message],
    ) -> None:
        respx.post("http://test-vllm:8000/v1/chat/completions").mock(
            return_value=Response(500, text="Internal Server Error")
        )
        async with get_client(vllm_server) as client:
            with pytest.raises(Exception):
                await client.complete(messages, model)

    @respx.mock
    async def test_health_ok(self, vllm_server: BackendConfig) -> None:
        respx.get("http://test-vllm:8000/health").mock(return_value=Response(200))
        async with get_client(vllm_server) as client:
            assert await client.health() is True

    @respx.mock
    async def test_health_down(self, vllm_server: BackendConfig) -> None:
        respx.get("http://test-vllm:8000/health").mock(return_value=Response(503))
        async with get_client(vllm_server) as client:
            assert await client.health() is False
