"""YAML scenario loader with Pydantic validation."""

from __future__ import annotations

from pathlib import Path

import yaml

from llm_bench.config import ScenarioConfig


def load_scenario(path: Path) -> ScenarioConfig:
    """Load and validate a YAML scenario file."""
    raw = yaml.safe_load(path.read_text())
    return ScenarioConfig.model_validate(raw)


def load_scenarios(paths: list[Path]) -> list[ScenarioConfig]:
    return [load_scenario(p) for p in paths]
