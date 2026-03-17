"""Tests for config.py — Pydantic validation and scenario loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from llm_bench.config import (
    Backend,
    BackendConfig,
    ConversationTemplate,
    LoadConfig,
    Message,
    ModelConfig,
    ScenarioConfig,
)
from llm_bench.scenario import load_scenario


class TestBackendConfig:
    def test_valid(self) -> None:
        b = BackendConfig(name="b1", url="http://localhost:8000", type=Backend.vllm)
        assert b.name == "b1"
        assert b.type == Backend.vllm
        assert b.timeout == 120.0
        assert b.gpu_monitoring is False
        assert b.effective_ssh_host is None

    def test_gpu_monitoring_extracts_host_from_url(self) -> None:
        b = BackendConfig(
            name="b1", url="http://10.0.0.1:8000", type=Backend.vllm, gpu_monitoring=True
        )
        assert b.effective_ssh_host == "10.0.0.1"

    def test_gpu_monitoring_ssh_host_override(self) -> None:
        b = BackendConfig(
            name="b1",
            url="http://10.0.0.1:8000",
            type=Backend.vllm,
            gpu_monitoring=True,
            ssh_host="bastion.internal",
        )
        assert b.effective_ssh_host == "bastion.internal"

    def test_invalid_url(self) -> None:
        with pytest.raises(Exception):
            BackendConfig(name="b1", url="not-a-url", type=Backend.vllm)

    def test_default_type(self) -> None:
        b = BackendConfig(name="b1", url="http://localhost:8000")
        assert b.type == Backend.openai

    def test_with_all_fields(self) -> None:
        b = BackendConfig(
            name="b1",
            url="http://10.0.0.1:8000",
            type=Backend.sglang,
            api_key="secret",
            timeout=60.0,
            gpu_monitoring=True,
            ssh_user="admin",
        )
        assert b.ssh_user == "admin"
        assert b.api_key == "secret"
        assert b.timeout == 60.0
        assert b.effective_ssh_host == "10.0.0.1"


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
    def test_get_backend(self, scenario: ScenarioConfig) -> None:
        b = scenario.get_backend("test-vllm")
        assert b.name == "test-vllm"

    def test_get_backend_missing(self, scenario: ScenarioConfig) -> None:
        with pytest.raises(KeyError):
            scenario.get_backend("nonexistent")

    def test_get_model(self, scenario: ScenarioConfig) -> None:
        m = scenario.get_model("test-model")
        assert m.name == "test-model"

    def test_get_conversation(self, scenario: ScenarioConfig) -> None:
        c = scenario.get_conversation("simple")
        assert c.name == "simple"


class TestBenchmarkTarget:
    def test_valid(self) -> None:
        from llm_bench.config import BenchmarkTarget

        t = BenchmarkTarget(backend="b1", model="m1", conversation="c1")
        assert t.backend == "b1"

    def test_invalid_backend_ref(self) -> None:
        with pytest.raises(Exception, match="unknown backend"):
            ScenarioConfig(
                name="t",
                backends=[BackendConfig(name="b1", url="http://localhost:8000", type=Backend.vllm)],
                models=[ModelConfig(name="m1")],
                conversations=[
                    ConversationTemplate(name="c1", turns=[Message(role="user", content="hi")])
                ],
                targets=[{"backend": "nonexistent", "model": "m1", "conversation": "c1"}],
            )


class TestScenarioValidation:
    def test_run_id_generated(self) -> None:
        cfg = ScenarioConfig(
            name="t",
            backends=[BackendConfig(name="b1", url="http://localhost:8000")],
            models=[ModelConfig(name="m1")],
            conversations=[
                ConversationTemplate(name="c1", turns=[Message(role="user", content="hi")])
            ],
            targets=[{"backend": "b1", "model": "m1", "conversation": "c1"}],
        )
        assert len(cfg.run_id) == 8


class TestLoadConfig:
    def test_defaults(self) -> None:
        lc = LoadConfig()
        assert lc.ramp_levels is None
        assert lc.ramp_pause_seconds == 10.0

    def test_ramp_levels_parsed(self) -> None:
        lc = LoadConfig(ramp_levels=[1, 5, 10])
        assert lc.ramp_levels == [1, 5, 10]

    def test_ramp_pause_seconds_custom(self) -> None:
        lc = LoadConfig(ramp_pause_seconds=5.0)
        assert lc.ramp_pause_seconds == 5.0

    def test_ramp_pause_negative_rejected(self) -> None:
        with pytest.raises(Exception):
            LoadConfig(ramp_pause_seconds=-1.0)


class TestLoadScenario:
    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        data = {
            "name": "test",
            "backends": [{"name": "b1", "url": "http://localhost:8000", "type": "vllm"}],
            "models": [{"name": "m1", "max_tokens": 128}],
            "conversations": [{"name": "c1", "turns": [{"role": "user", "content": "hi"}]}],
            "targets": [{"backend": "b1", "model": "m1", "conversation": "c1"}],
        }
        f = tmp_path / "scenario.yaml"
        f.write_text(yaml.dump(data))
        cfg = load_scenario(f)
        assert cfg.name == "test"
        assert len(cfg.backends) == 1

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_scenario(tmp_path / "nope.yaml")

    def test_load_invalid_schema(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("name: test\n")  # missing required fields
        with pytest.raises(Exception):
            load_scenario(f)
