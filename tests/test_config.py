"""Tests for config.py — Pydantic validation and scenario loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from llm_bench.config import (
    Backend,
    ConversationTemplate,
    Message,
    ModelConfig,
    ScenarioConfig,
    ServerConfig,
)
from llm_bench.scenario import load_scenario


class TestServerConfig:
    def test_valid(self) -> None:
        s = ServerConfig(name="s1", url="http://localhost:8000", backend=Backend.vllm)
        assert s.name == "s1"
        assert s.backend == Backend.vllm
        assert s.timeout == 120.0

    def test_invalid_url(self) -> None:
        with pytest.raises(Exception):
            ServerConfig(name="s1", url="not-a-url")

    def test_default_backend(self) -> None:
        s = ServerConfig(name="s1", url="http://localhost:8000")
        assert s.backend == Backend.openai


class TestModelConfig:
    def test_valid(self) -> None:
        m = ModelConfig(name="llama", max_tokens=256, temperature=0.7)
        assert m.max_tokens == 256

    def test_temperature_bounds(self) -> None:
        with pytest.raises(Exception):
            ModelConfig(name="m", temperature=3.0)

    def test_top_p_bounds(self) -> None:
        with pytest.raises(Exception):
            ModelConfig(name="m", top_p=1.5)


class TestConversationTemplate:
    def test_valid(self) -> None:
        c = ConversationTemplate(
            name="c1",
            turns=[Message(role="user", content="hello")],
        )
        assert len(c.turns) == 1

    def test_requires_user_turn(self) -> None:
        with pytest.raises(Exception):
            ConversationTemplate(
                name="c1",
                turns=[Message(role="system", content="be helpful")],
            )


class TestScenarioConfig:
    def test_get_server(self, scenario: ScenarioConfig) -> None:
        s = scenario.get_server("test-vllm")
        assert s.name == "test-vllm"

    def test_get_server_missing(self, scenario: ScenarioConfig) -> None:
        with pytest.raises(KeyError):
            scenario.get_server("nonexistent")

    def test_get_model(self, scenario: ScenarioConfig) -> None:
        m = scenario.get_model("test-model")
        assert m.name == "test-model"

    def test_get_conversation(self, scenario: ScenarioConfig) -> None:
        c = scenario.get_conversation("simple")
        assert c.name == "simple"


class TestLoadScenario:
    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        data = {
            "name": "test",
            "servers": [{"name": "s1", "url": "http://localhost:8000", "backend": "vllm"}],
            "models": [{"name": "m1", "max_tokens": 128}],
            "conversations": [{"name": "c1", "turns": [{"role": "user", "content": "hi"}]}],
            "targets": [{"server": "s1", "model": "m1", "conversation": "c1"}],
        }
        f = tmp_path / "scenario.yaml"
        f.write_text(yaml.dump(data))
        cfg = load_scenario(f)
        assert cfg.name == "test"
        assert len(cfg.servers) == 1

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_scenario(tmp_path / "nope.yaml")

    def test_load_invalid_schema(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("name: test\n")  # missing required fields
        with pytest.raises(Exception):
            load_scenario(f)
