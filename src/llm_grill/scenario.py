"""YAML scenario loader with Pydantic validation."""

from __future__ import annotations

from pathlib import Path

import yaml

from llm_grill.config import ScenarioConfig


def load_scenario(path: Path) -> ScenarioConfig:
    """Load and validate a YAML scenario file."""
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")
    raw = yaml.safe_load(path.read_text())
    config = ScenarioConfig.model_validate(raw)
    for conv in config.conversations:
        for msg in conv.turns:
            msg.resolve(path.parent)
    return config
