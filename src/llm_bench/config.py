"""Pydantic schemas for servers, models, and benchmark scenarios."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, PositiveFloat, PositiveInt, model_validator


class Backend(str, Enum):
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


class BenchmarkTarget(BaseModel):
    server: str
    model: str
    conversation: str


class ScenarioConfig(BaseModel):
    name: str
    description: str = ""
    servers: list[ServerConfig]
    models: list[ModelConfig]
    conversations: list[ConversationTemplate]
    targets: list[BenchmarkTarget]
    load: LoadConfig = Field(default_factory=LoadConfig)

    @model_validator(mode="after")
    def validate_target_references(self) -> ScenarioConfig:
        server_names = {s.name for s in self.servers}
        model_names = {m.name for m in self.models}
        conv_names = {c.name for c in self.conversations}
        for t in self.targets:
            if t.server not in server_names:
                raise ValueError(
                    f"Target references unknown server '{t.server}'. Available: {sorted(server_names)}"
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
