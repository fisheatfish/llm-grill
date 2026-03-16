"""Pydantic schemas for servers, models, and benchmark scenarios."""

from __future__ import annotations

import os
import re
from enum import StrEnum
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


class ServerConfig(BaseModel):
    name: str
    url: HttpUrl
    api_key: str = "none"
    backend: Backend = Backend.openai
    timeout: PositiveFloat = 120.0

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


class ModelConfig(BaseModel):
    name: str
    max_tokens: PositiveInt = 512
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.0
    top_p: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ConversationTemplate(BaseModel):
    name: str
    description: str = ""
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


class BackendConfig(BaseModel):
    name: str
    url: HttpUrl
    type: Backend
    ssh_host: str | None = None
    ssh_user: str = "root"
    gpu_type: str | None = None
    model_dtype: str | None = None

    def to_server_config(self) -> ServerConfig:
        return ServerConfig(name=self.name, url=self.url, backend=self.type, api_key="none")


class BenchmarkTarget(BaseModel):
    server: str
    model: str
    conversation: str
    backend: str | None = None


class ScenarioConfig(BaseModel):
    name: str
    description: str = ""
    servers: list[ServerConfig]
    models: list[ModelConfig]
    conversations: list[ConversationTemplate]
    targets: list[BenchmarkTarget]
    load: LoadConfig = Field(default_factory=LoadConfig)
    backends: list[BackendConfig] = Field(default_factory=list)
    run_id: str = Field(default_factory=lambda: uuid4().hex[:8])

    @model_validator(mode="after")
    def validate_target_references(self) -> ScenarioConfig:
        server_names = {s.name for s in self.servers}
        model_names = {m.name for m in self.models}
        conv_names = {c.name for c in self.conversations}
        for t in self.targets:
            if t.server not in server_names:
                raise ValueError(
                    f"Target references unknown server '{t.server}'. "
                    f"Available: {sorted(server_names)}"
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
        backend_names = {b.name for b in self.backends}
        for t in self.targets:
            if t.backend is not None and t.backend not in backend_names:
                raise ValueError(
                    f"Target references unknown backend '{t.backend}'. "
                    f"Available: {sorted(backend_names)}"
                )
        return self

    def get_server(self, name: str) -> ServerConfig:
        for s in self.servers:
            if s.name == name:
                return s
        raise KeyError(f"Server '{name}' not found")

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

    def get_backend(self, name: str) -> BackendConfig:
        for b in self.backends:
            if b.name == name:
                return b
        raise KeyError(f"Backend '{name}' not found")
