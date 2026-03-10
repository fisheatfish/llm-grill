"""Shared fixtures for llm-bench tests."""

from __future__ import annotations

import pytest

from llm_bench.config import (
    Backend,
    BenchmarkTarget,
    ConversationTemplate,
    LoadConfig,
    Message,
    ModelConfig,
    ScenarioConfig,
    ServerConfig,
)


@pytest.fixture()
def server_vllm() -> ServerConfig:
    return ServerConfig(
        name="test-vllm",
        url="http://localhost:8000",
        api_key="test",
        backend=Backend.vllm,
    )


@pytest.fixture()
def model_config() -> ModelConfig:
    return ModelConfig(name="test-model", max_tokens=64, temperature=0.0)


@pytest.fixture()
def simple_conversation() -> ConversationTemplate:
    return ConversationTemplate(
        name="simple",
        turns=[Message(role="user", content="Say hello.")],
    )


@pytest.fixture()
def multi_turn_conversation() -> ConversationTemplate:
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
    server_vllm: ServerConfig,
    model_config: ModelConfig,
    simple_conversation: ConversationTemplate,
) -> ScenarioConfig:
    return ScenarioConfig(
        name="test-scenario",
        servers=[server_vllm],
        models=[model_config],
        conversations=[simple_conversation],
        targets=[
            BenchmarkTarget(
                server="test-vllm",
                model="test-model",
                conversation="simple",
            )
        ],
        load=LoadConfig(concurrent_users=1, iterations=1),
    )
