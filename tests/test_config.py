"""
Tests for config.py and scenario.py.
Tests Pydantic validation, defaults, cross-references, and YAML loading.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from llm_grill.config import (
    Backend,
    BackendConfig,
    BenchmarkTarget,
    ConversationTemplate,
    LoadConfig,
    Message,
    ModelConfig,
    ScenarioConfig,
)
from llm_grill.scenario import load_scenario


class TestBackendConfig:
    """Tests for BackendConfig validation and defaults."""

    def test_should_create_valid_config_when_all_fields_provided(self):
        """
        Should accept valid fields and set correct defaults.

        Given: Valid server parameters with explicit backend
        When: Creating a BackendConfig
        Then: All fields are set correctly with default timeout
        """
        # Given / When
        b = BackendConfig(name="b1", url="http://localhost:8000", type=Backend.vllm)

        # Then
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

    def test_should_reject_invalid_url(self):
        """
        Should raise ValidationError when URL is malformed.

        Given: An invalid URL string
        When: Creating a BackendConfig
        Then: Pydantic raises a validation error
        """
        # When / Then
        with pytest.raises(Exception):
            BackendConfig(name="b1", url="not-a-url", type=Backend.vllm)

    def test_should_default_to_openai_backend(self):
        """
        Should use openai as default backend when none specified.

        Given: No backend specified
        When: Creating a BackendConfig
        Then: Backend defaults to openai
        """
        # When
        server = BackendConfig(name="s1", url="http://localhost:8000")

        # Then
        assert server.type == Backend.openai


class TestModelConfig:
    """Tests for ModelConfig validation and bounds."""

    def test_should_accept_valid_parameters(self):
        """
        Should create model config with specified values.

        Given: Valid model parameters
        When: Creating a ModelConfig
        Then: Values are set correctly
        """
        # When
        model = ModelConfig(name="llama", max_tokens=256, temperature=0.7)

        # Then
        assert model.max_tokens == 256

    def test_should_reject_temperature_above_2(self):
        """
        Should reject temperature > 2.0.

        Given: Temperature set to 3.0
        When: Creating a ModelConfig
        Then: Validation error is raised
        """
        # When / Then
        with pytest.raises(Exception):
            ModelConfig(name="m", temperature=3.0)

    def test_should_reject_top_p_above_1(self):
        """
        Should reject top_p > 1.0.

        Given: top_p set to 1.5
        When: Creating a ModelConfig
        Then: Validation error is raised
        """
        # When / Then
        with pytest.raises(Exception):
            ModelConfig(name="m", top_p=1.5)


class TestConversationTemplate:
    """Tests for ConversationTemplate validation."""

    def test_should_accept_conversation_with_user_turn(self):
        """
        Should create a valid conversation when it has at least one user turn.

        Given: A conversation with a single user turn
        When: Creating a ConversationTemplate
        Then: Template is created with correct turn count
        """
        # When
        conv = ConversationTemplate(
            name="c1",
            turns=[Message(role="user", content="hello")],
        )

        # Then
        assert len(conv.turns) == 1

    def test_should_reject_conversation_without_user_turn(self):
        """
        Should reject a conversation with only system messages.

        Given: A conversation with only a system turn
        When: Creating a ConversationTemplate
        Then: Validation error is raised
        """
        # When / Then
        with pytest.raises(Exception):
            ConversationTemplate(
                name="c1",
                turns=[Message(role="system", content="be helpful")],
            )


class TestScenarioConfigLookups:
    """Tests for ScenarioConfig getter methods."""

    def test_should_find_server_by_name(self, scenario: ScenarioConfig):
        """
        Should return the matching server when name exists.

        Given: A scenario with server "test-vllm"
        When: Calling get_backend("test-vllm")
        Then: Returns the correct server
        """
        # When
        server = scenario.get_backend("test-vllm")

        # Then
        assert server.name == "test-vllm"

    def test_should_raise_when_server_not_found(self, scenario: ScenarioConfig):
        """
        Should raise KeyError when server name does not exist.

        Given: A scenario without server "nonexistent"
        When: Calling get_backend("nonexistent")
        Then: KeyError is raised
        """
        # When / Then
        with pytest.raises(KeyError):
            scenario.get_backend("nonexistent")

    def test_should_find_model_by_name(self, scenario: ScenarioConfig):
        """
        Should return the matching model when name exists.

        Given: A scenario with model "test-model"
        When: Calling get_model("test-model")
        Then: Returns the correct model
        """
        # When
        model = scenario.get_model("test-model")

        # Then
        assert model.name == "test-model"

    def test_should_find_conversation_by_name(self, scenario: ScenarioConfig):
        """
        Should return the matching conversation when name exists.

        Given: A scenario with conversation "simple"
        When: Calling get_conversation("simple")
        Then: Returns the correct conversation
        """
        # When
        conv = scenario.get_conversation("simple")

        # Then
        assert conv.name == "simple"


class TestBackendConfigExtended:
    """Tests for BackendConfig GPU and SSH fields."""

    def test_should_create_with_defaults(self):
        """
        Should set ssh_host to None and ssh_user to "root" by default.

        Given: Minimal backend config parameters
        When: Creating a BackendConfig
        Then: Defaults are applied correctly
        """
        # When
        backend = BackendConfig(name="gpu-vllm", url="http://10.0.0.1:8000", type=Backend.vllm)

        # Then
        assert backend.name == "gpu-vllm"
        assert backend.ssh_host is None
        assert backend.ssh_user == "root"

    def test_should_accept_all_optional_fields(self):
        """
        Should store all optional fields when provided.

        Given: BackendConfig with all optional fields set
        When: Creating the config
        Then: All values are stored correctly
        """
        # When
        backend = BackendConfig(
            name="b1",
            url="http://10.0.0.1:8000",
            type=Backend.sglang,
            ssh_host="10.0.0.1",
            ssh_user="admin",
        )

        # Then
        assert backend.ssh_user == "admin"
        assert backend.ssh_host == "10.0.0.1"


class TestBenchmarkTarget:
    """Tests for BenchmarkTarget backend reference validation."""

    def test_should_store_backend(self):
        """
        Should store the backend reference when provided.

        Given: A target with backend="gpu-vllm"
        When: Creating a BenchmarkTarget
        Then: backend is "gpu-vllm"
        """
        # When
        target = BenchmarkTarget(backend="gpu-vllm", model="m1", conversation="c1")

        # Then
        assert target.backend == "gpu-vllm"

    def test_should_reject_invalid_backend_reference(self):
        """
        Should reject a target referencing a non-existent backend.

        Given: A scenario with backend "gpu-vllm" but target referencing "nonexistent"
        When: Creating the ScenarioConfig
        Then: Validation error mentioning "unknown backend" is raised
        """
        # When / Then
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


class TestUniquePrefix:
    """Tests for ConversationTemplate unique_prefix flag."""

    def test_should_default_unique_prefix_to_false(self):
        """
        Given: A conversation without unique_prefix
        When: Creating the ConversationTemplate
        Then: unique_prefix defaults to False
        """
        # When
        conv = ConversationTemplate(name="c1", turns=[Message(role="user", content="hi")])

        # Then
        assert conv.unique_prefix is False

    def test_should_accept_unique_prefix_true(self):
        """
        Given: A conversation with unique_prefix=True
        When: Creating the ConversationTemplate
        Then: unique_prefix is True
        """
        # When
        conv = ConversationTemplate(
            name="c1", unique_prefix=True, turns=[Message(role="user", content="hi")]
        )

        # Then
        assert conv.unique_prefix is True


class TestScenarioBackends:
    """Tests for ScenarioConfig backend-related features."""

    def test_should_find_backend_by_name(self):
        """
        Should return the matching backend when name exists.

        Given: A scenario with backend "gpu-vllm"
        When: Calling get_backend("gpu-vllm")
        Then: Returns the correct backend
        """
        # Given

        cfg = ScenarioConfig(
            name="t",
            backends=[
                BackendConfig(name="gpu-vllm", url="http://10.0.0.1:8000", type=Backend.vllm)
            ],
            models=[ModelConfig(name="m1")],
            conversations=[
                ConversationTemplate(name="c1", turns=[Message(role="user", content="hi")])
            ],
            targets=[{"backend": "gpu-vllm", "model": "m1", "conversation": "c1"}],
        )

        # When
        backend = cfg.get_backend("gpu-vllm")

        # Then
        assert backend.name == "gpu-vllm"

    def test_should_raise_when_backend_not_found(self, scenario: ScenarioConfig):
        """
        Should raise KeyError when backend name does not exist.

        Given: A scenario without backends
        When: Calling get_backend("nonexistent")
        Then: KeyError is raised
        """
        # When / Then
        with pytest.raises(KeyError):
            scenario.get_backend("nonexistent")

    def test_should_generate_8_char_run_id(self):
        """
        Should auto-generate an 8-character run_id.

        Given: A valid scenario without explicit run_id
        When: Creating the ScenarioConfig
        Then: run_id is 8 characters long
        """
        # Given / When
        cfg = ScenarioConfig(
            name="t",
            backends=[BackendConfig(name="b1", url="http://localhost:8000")],
            models=[ModelConfig(name="m1")],
            conversations=[
                ConversationTemplate(name="c1", turns=[Message(role="user", content="hi")])
            ],
            targets=[{"backend": "b1", "model": "m1", "conversation": "c1"}],
        )

        # Then
        assert len(cfg.run_id) == 8


class TestLoadConfig:
    """Tests for LoadConfig defaults and validation."""

    def test_should_default_ramp_levels_to_none(self):
        """
        Should have ramp_levels=None and ramp_pause_seconds=10.0 by default.

        Given: No ramp parameters specified
        When: Creating a LoadConfig
        Then: Defaults are applied
        """
        # When
        load = LoadConfig()

        # Then
        assert load.ramp_levels is None
        assert load.ramp_pause_seconds == 10.0

    def test_should_accept_ramp_levels_list(self):
        """
        Should store ramp_levels when provided as a list.

        Given: ramp_levels=[1, 5, 10]
        When: Creating a LoadConfig
        Then: ramp_levels is stored correctly
        """
        # When
        load = LoadConfig(ramp_levels=[1, 5, 10])

        # Then
        assert load.ramp_levels == [1, 5, 10]

    def test_should_accept_custom_ramp_pause(self):
        """
        Should store custom ramp_pause_seconds.

        Given: ramp_pause_seconds=5.0
        When: Creating a LoadConfig
        Then: Value is stored
        """
        # When
        load = LoadConfig(ramp_pause_seconds=5.0)

        # Then
        assert load.ramp_pause_seconds == 5.0

    def test_should_reject_negative_ramp_pause(self):
        """
        Should reject negative ramp_pause_seconds.

        Given: ramp_pause_seconds=-1.0
        When: Creating a LoadConfig
        Then: Validation error is raised
        """
        # When / Then
        with pytest.raises(Exception):
            LoadConfig(ramp_pause_seconds=-1.0)


class TestMessageContentFile:
    """Tests for Message content_file external reference resolution."""

    def test_should_resolve_content_from_file_when_content_file_set(self, tmp_path: Path):
        """
        Should read file content and clear content_file after resolve.

        Given: A Message with content_file pointing to an existing file
        When: Calling resolve()
        Then: content is populated from the file and content_file is cleared
        """
        # Given
        f = tmp_path / "doc.txt"
        f.write_text("hello world")
        msg = Message(role="user", content_file="doc.txt")

        # When
        msg.resolve(tmp_path)

        # Then
        assert msg.content == "hello world"
        assert msg.content_file is None

    def test_should_reject_when_both_content_and_content_file_provided(self):
        """
        Should raise ValidationError when both content sources are set.

        Given: Both content and content_file specified
        When: Creating a Message
        Then: Validation error mentioning "not both" is raised
        """
        # When / Then
        with pytest.raises(Exception, match="not both"):
            Message(role="user", content="hi", content_file="doc.txt")

    def test_should_reject_when_neither_content_nor_content_file_provided(self):
        """
        Should raise ValidationError when no content source is set.

        Given: Neither content nor content_file specified
        When: Creating a Message
        Then: Validation error mentioning "required" is raised
        """
        # When / Then
        with pytest.raises(Exception, match="required"):
            Message(role="user")

    def test_should_raise_when_content_file_does_not_exist(self, tmp_path: Path):
        """
        Should raise FileNotFoundError when referenced file is missing.

        Given: A Message with content_file pointing to a non-existent file
        When: Calling resolve()
        Then: FileNotFoundError with descriptive message is raised
        """
        # Given
        msg = Message(role="user", content_file="missing.txt")

        # When / Then
        with pytest.raises(FileNotFoundError, match="content_file not found"):
            msg.resolve(tmp_path)

    def test_should_noop_when_content_is_inline(self, tmp_path: Path):
        """
        Should leave inline content unchanged after resolve.

        Given: A Message with inline content (no content_file)
        When: Calling resolve()
        Then: content remains unchanged
        """
        # Given
        msg = Message(role="user", content="already inline")

        # When
        msg.resolve(tmp_path)

        # Then
        assert msg.content == "already inline"

    def test_should_resolve_content_file_in_scenario_loading(self, tmp_path: Path):
        """
        Should resolve content_file references when loading a full scenario from YAML.

        Given: A YAML scenario with a turn using content_file
        When: Calling load_scenario()
        Then: The turn content is populated from the referenced file
        """
        # Given
        ctx = tmp_path / "ctx.txt"
        ctx.write_text("big context here")
        data = {
            "name": "test",
            "backends": [{"name": "b1", "url": "http://localhost:8000", "type": "vllm"}],
            "models": [{"name": "m1"}],
            "conversations": [
                {
                    "name": "c1",
                    "turns": [
                        {"role": "user", "content_file": "ctx.txt"},
                        {"role": "user", "content": "summarize"},
                    ],
                }
            ],
            "targets": [{"backend": "b1", "model": "m1", "conversation": "c1"}],
        }
        f = tmp_path / "scenario.yaml"
        f.write_text(yaml.dump(data))

        # When
        cfg = load_scenario(f)

        # Then
        assert cfg.conversations[0].turns[0].content == "big context here"
        assert cfg.conversations[0].turns[1].content == "summarize"


class TestLoadScenario:
    """Tests for YAML scenario loading via load_scenario()."""

    def test_should_load_valid_yaml(self, tmp_path: Path):
        """
        Should parse and validate a correct YAML scenario file.

        Given: A valid YAML scenario file on disk
        When: Calling load_scenario()
        Then: Returns a ScenarioConfig with correct values
        """
        # Given
        data = {
            "name": "test",
            "backends": [{"name": "b1", "url": "http://localhost:8000", "type": "vllm"}],
            "models": [{"name": "m1", "max_tokens": 128}],
            "conversations": [{"name": "c1", "turns": [{"role": "user", "content": "hi"}]}],
            "targets": [{"backend": "b1", "model": "m1", "conversation": "c1"}],
        }
        f = tmp_path / "scenario.yaml"
        f.write_text(yaml.dump(data))

        # When
        cfg = load_scenario(f)

        # Then
        assert cfg.name == "test"
        assert len(cfg.backends) == 1

    def test_should_raise_when_file_not_found(self, tmp_path: Path):
        """
        Should raise FileNotFoundError for missing files.

        Given: A path to a non-existent file
        When: Calling load_scenario()
        Then: FileNotFoundError is raised
        """
        # When / Then
        with pytest.raises(FileNotFoundError):
            load_scenario(tmp_path / "nope.yaml")

    def test_should_raise_when_schema_invalid(self, tmp_path: Path):
        """
        Should raise validation error when required fields are missing.

        Given: A YAML file with only "name" field
        When: Calling load_scenario()
        Then: Validation error is raised
        """
        # Given
        f = tmp_path / "bad.yaml"
        f.write_text("name: test\n")

        # When / Then
        with pytest.raises(Exception):
            load_scenario(f)
