"""Pydantic schemas for backends, models, and benchmark scenarios."""

from __future__ import annotations

import os
import re
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    PositiveFloat,
    PositiveInt,
    field_validator,
    model_validator,
)


class Backend(StrEnum):
    vllm = "vllm"
    sglang = "sglang"
    llamacpp = "llamacpp"
    litellm = "litellm"
    openai = "openai"


class BackendConfig(BaseModel):
    name: str
    url: HttpUrl
    type: Backend = Backend.openai
    api_key: str = "none"
    timeout: PositiveFloat = 120.0
    gpu_monitoring: bool = False
    ssh_host: str | None = None
    ssh_user: str = "root"

    @field_validator("api_key", mode="before")
    @classmethod
    def expand_env_var(cls, v: str) -> str:
        """Expand ${VAR_NAME} in api_key to the corresponding environment variable."""
        match = re.fullmatch(r"\$\{([^}]+)\}", str(v))
        if match:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                raise ValueError(f"Environment variable '{var_name}' is not set")
            return value
        return v

    @property
    def effective_ssh_host(self) -> str | None:
        """SSH host for GPU monitoring: explicit ssh_host, or extracted from url."""
        if not self.gpu_monitoring:
            return None
        if self.ssh_host:
            return self.ssh_host
        return str(self.url).split("://")[1].split(":")[0].split("/")[0]


class ModelConfig(BaseModel):
    name: str
    max_tokens: PositiveInt = 512
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.0
    top_p: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    top_k: Annotated[int, Field(ge=-1)] = -1


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | None = None
    content_file: str | None = None

    @model_validator(mode="after")
    def check_content_source(self) -> Message:
        if self.content is not None and self.content_file is not None:
            raise ValueError("Set either 'content' or 'content_file', not both")
        if self.content is None and self.content_file is None:
            raise ValueError("One of 'content' or 'content_file' is required")
        return self

    def resolve(self, base_dir: Path) -> None:
        """Read content_file relative to base_dir and set content."""
        if self.content_file is not None:
            p = base_dir / self.content_file
            if not p.exists():
                raise FileNotFoundError(f"content_file not found: {p}")
            self.content = p.read_text()
            self.content_file = None


class ConversationTemplate(BaseModel):
    name: str
    description: str = ""
    unique_prefix: bool = False
    turns: list[Message]

    @model_validator(mode="after")
    def has_user_turn(self) -> ConversationTemplate:
        if not any(m.role == "user" for m in self.turns):
            raise ValueError("Conversation must have at least one user turn")
        return self


class LoadConfig(BaseModel):
    concurrent_users: PositiveInt = 1
    iterations: PositiveInt = 1
    ramp_up_seconds: Annotated[float, Field(ge=0.0)] = 0.0
    think_time_seconds: Annotated[float, Field(ge=0.0)] = 0.0
    ramp_levels: list[PositiveInt] | None = None
    ramp_pause_seconds: Annotated[float, Field(ge=0.0)] = 10.0


class BenchmarkTarget(BaseModel):
    backend: str
    model: str
    conversation: str


class ScenarioConfig(BaseModel):
    name: str
    description: str = ""
    backends: list[BackendConfig]
    models: list[ModelConfig]
    conversations: list[ConversationTemplate]
    targets: list[BenchmarkTarget]
    load: LoadConfig = Field(default_factory=LoadConfig)
    run_id: str = Field(default_factory=lambda: uuid4().hex[:8])

    @model_validator(mode="after")
    def validate_target_references(self) -> ScenarioConfig:
        backend_names = {b.name for b in self.backends}
        model_names = {m.name for m in self.models}
        conv_names = {c.name for c in self.conversations}
        for t in self.targets:
            if t.backend not in backend_names:
                raise ValueError(
                    f"Target references unknown backend '{t.backend}'. "
                    f"Available: {sorted(backend_names)}"
                )
            if t.model not in model_names:
                raise ValueError(
                    f"Target references unknown model '{t.model}'. Available: {sorted(model_names)}"
                )
            if t.conversation not in conv_names:
                raise ValueError(
                    f"Target references unknown conversation '{t.conversation}'. "
                    f"Available: {sorted(conv_names)}"
                )
        return self

    def get_backend(self, name: str) -> BackendConfig:
        for b in self.backends:
            if b.name == name:
                return b
        raise KeyError(f"Backend '{name}' not found")

    def get_model(self, name: str) -> ModelConfig:
        for m in self.models:
            if m.name == name:
                return m
        raise KeyError(f"Model '{name}' not found")

    def get_conversation(self, name: str) -> ConversationTemplate:
        for c in self.conversations:
            if c.name == name:
                return c
        raise KeyError(f"Conversation '{name}' not found")
