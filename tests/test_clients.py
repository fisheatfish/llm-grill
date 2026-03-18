"""
Tests for backend clients.
Tests client factory, SSE streaming, health checks, and error handling using respx.
"""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

from llm_grill.clients import get_client
from llm_grill.config import Backend, BackendConfig, Message, ModelConfig


def _sse_body(tokens: list[str], model: str = "m", prompt_tokens: int = 10) -> bytes:
    """Build a minimal OpenAI-compatible SSE response."""
    lines = []
    for token in tokens:
        chunk = {
            "id": "test",
            "object": "chat.completion.chunk",
            "choices": [{"delta": {"content": token}, "finish_reason": None}],
        }
        lines.append(f"data: {json.dumps(chunk)}")
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
    """Create a vLLM server config for testing."""
    return BackendConfig(
        name="vllm-test",
        url="http://test-vllm:8000",
        type=Backend.vllm,
    )


@pytest.fixture()
def model() -> ModelConfig:
    """Create a minimal model config for testing."""
    return ModelConfig(name="test-model", max_tokens=16)


@pytest.fixture()
def messages() -> list[Message]:
    """Create a single user message for testing."""
    return [Message(role="user", content="hello")]


class TestGetClient:
    """Tests for the client factory function."""

    def test_should_return_vllm_client_for_vllm_backend(self, vllm_server: BackendConfig):
        """
        Should instantiate VllmClient for vllm backend.

        Given: A server config with backend=vllm
        When: Calling get_client()
        Then: Returns a VllmClient instance
        """
        # Given
        from llm_grill.clients.vllm import VllmClient

        # When
        client = get_client(vllm_server)

        # Then
        assert isinstance(client, VllmClient)

    def test_should_return_sglang_client_for_sglang_backend(self):
        """
        Should instantiate SglangClient for sglang backend.

        Given: A server config with backend=sglang
        When: Calling get_client()
        Then: Returns a SglangClient instance
        """
        # Given
        from llm_grill.clients.sglang import SglangClient

        server = BackendConfig(name="s", url="http://localhost:30000", type=Backend.sglang)

        # When / Then
        assert isinstance(get_client(server), SglangClient)

    def test_should_return_llamacpp_client_for_llamacpp_backend(self):
        """
        Should instantiate LlamaCppClient for llamacpp backend.

        Given: A server config with backend=llamacpp
        When: Calling get_client()
        Then: Returns a LlamaCppClient instance
        """
        # Given
        from llm_grill.clients.llamacpp import LlamaCppClient

        server = BackendConfig(name="s", url="http://localhost:8080", type=Backend.llamacpp)

        # When / Then
        assert isinstance(get_client(server), LlamaCppClient)


class TestVllmClientComplete:
    """Tests for VllmClient streaming completion and health checks."""

    @respx.mock
    async def test_should_stream_and_measure_metrics_on_success(
        self,
        vllm_server: BackendConfig,
        model: ModelConfig,
        messages: list[Message],
    ):
        """
        Should parse SSE stream and return correct content and timing metrics.

        Given: A mocked SSE endpoint returning ["Hello", " world"]
        When: Calling complete()
        Then: Content is concatenated, tokens counted, and timing is non-negative
        """
        # Given
        respx.post("http://test-vllm:8000/v1/chat/completions").mock(
            return_value=Response(
                200,
                content=_sse_body(["Hello", " world"]),
                headers={"content-type": "text/event-stream"},
            )
        )

        # When
        async with get_client(vllm_server) as client:
            result = await client.complete(messages, model)

        # Then
        assert result.content == "Hello world"
        assert result.completion_tokens == 2
        assert result.prompt_tokens == 10
        assert result.ttft_s >= 0
        assert result.e2e_latency_s >= result.ttft_s

    @respx.mock
    async def test_should_raise_on_http_error(
        self,
        vllm_server: BackendConfig,
        model: ModelConfig,
        messages: list[Message],
    ):
        """
        Should propagate HTTP errors as exceptions.

        Given: A mocked endpoint returning 500
        When: Calling complete()
        Then: An exception is raised
        """
        # Given
        respx.post("http://test-vllm:8000/v1/chat/completions").mock(
            return_value=Response(500, text="Internal Server Error")
        )

        # When / Then
        async with get_client(vllm_server) as client:
            with pytest.raises(Exception):
                await client.complete(messages, model)

    @respx.mock
    async def test_should_return_true_when_server_healthy(self, vllm_server: BackendConfig):
        """
        Should return True when /health returns 200.

        Given: A mocked /health endpoint returning 200
        When: Calling health()
        Then: Returns True
        """
        # Given
        respx.get("http://test-vllm:8000/health").mock(return_value=Response(200))

        # When
        async with get_client(vllm_server) as client:
            result = await client.health()

        # Then
        assert result is True

    @respx.mock
    async def test_should_return_false_when_server_down(self, vllm_server: BackendConfig):
        """
        Should return False when /health returns non-200.

        Given: A mocked /health endpoint returning 503
        When: Calling health()
        Then: Returns False
        """
        # Given
        respx.get("http://test-vllm:8000/health").mock(return_value=Response(503))

        # When
        async with get_client(vllm_server) as client:
            result = await client.health()

        # Then
        assert result is False
