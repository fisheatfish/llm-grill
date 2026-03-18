"""Shared fixtures for llm-bench tests."""

from __future__ import annotations

import pytest

from llm_bench.config import (
    Backend,
    BackendConfig,
    BenchmarkTarget,
    ConversationTemplate,
    LoadConfig,
    Message,
    ModelConfig,
    ScenarioConfig,
)


@pytest.fixture()
def backend_vllm() -> BackendConfig:
    """Create a vLLM server config pointing to localhost."""
    return BackendConfig(
        name="test-vllm",
        url="http://localhost:8000",
        api_key="test",
        type=Backend.vllm,
    )


@pytest.fixture()
def model_config() -> ModelConfig:
    """Create a minimal model config for testing."""
    return ModelConfig(name="test-model", max_tokens=64, temperature=0.0)


@pytest.fixture()
def simple_conversation() -> ConversationTemplate:
    """Create a single-turn conversation template."""
    return ConversationTemplate(
        name="simple",
        turns=[Message(role="user", content="Say hello.")],
    )


@pytest.fixture()
def multi_turn_conversation() -> ConversationTemplate:
    """Create a multi-turn conversation with system prompt and two user turns."""
    return ConversationTemplate(
        name="multi",
        turns=[
            Message(role="system", content="You are helpful."),
            Message(role="user", content="First question."),
            Message(role="user", content="Second question."),
        ],
    )


@pytest.fixture()
def scenario(
    backend_vllm: BackendConfig,
    model_config: ModelConfig,
    simple_conversation: ConversationTemplate,
) -> ScenarioConfig:
    """Create a minimal valid scenario with one server, model, conversation, and target."""
    return ScenarioConfig(
        name="test-scenario",
        backends=[backend_vllm],
        models=[model_config],
        conversations=[simple_conversation],
        targets=[
            BenchmarkTarget(
                backend="test-vllm",
                model="test-model",
                conversation="simple",
            )
        ],
        load=LoadConfig(concurrent_users=1, iterations=1),
    )
