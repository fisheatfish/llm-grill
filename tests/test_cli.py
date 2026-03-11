"""Tests for cli.py — Typer commands via CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from llm_bench.cli import app
from llm_bench.metrics import RequestMetrics
from llm_bench.report import JsonlWriter

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_scenario_file(tmp_path: Path) -> Path:
    data = {
        "name": "test",
        "servers": [{"name": "s1", "url": "http://localhost:8000", "backend": "vllm"}],
        "models": [{"name": "m1", "max_tokens": 128}],
        "conversations": [{"name": "c1", "turns": [{"role": "user", "content": "hello"}]}],
        "targets": [{"server": "s1", "model": "m1", "conversation": "c1"}],
    }
    f = tmp_path / "scenario.yaml"
    f.write_text(yaml.dump(data))
    return f


@pytest.fixture()
def results_file(tmp_path: Path) -> Path:
    path = tmp_path / "results.jsonl"
    m = RequestMetrics(
        scenario="test",
        target_server="s1",
        target_model="m1",
        conversation="c1",
        turn=0,
        iteration=0,
        user_id=0,
        timestamp_start="2026-01-01T00:00:00+00:00",
        ttft_s=0.1,
        tpot_s=0.02,
        e2e_latency_s=0.5,
        prompt_tokens=10,
        completion_tokens=20,
        tokens_per_second=40.0,
        success=True,
    )
    with JsonlWriter(path) as w:
        w.write(m)
    return path


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.4.2" in result.output


# ---------------------------------------------------------------------------
# show-scenario
# ---------------------------------------------------------------------------


class TestShowScenario:
    def test_valid_scenario(self, valid_scenario_file: Path) -> None:
        result = runner.invoke(app, ["show-scenario", str(valid_scenario_file)])
        assert result.exit_code == 0
        assert "test" in result.output
        assert "s1" in result.output

    def test_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["show-scenario", str(tmp_path / "nope.yaml")])
        assert result.exit_code == 1

    def test_invalid_schema(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("name: test\n")  # missing required fields
        result = runner.invoke(app, ["show-scenario", str(f)])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------


class TestPing:
    def test_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["ping", str(tmp_path / "nope.yaml")])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


class TestReport:
    def test_missing_results_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["report", str(tmp_path / "nope.jsonl")])
        assert result.exit_code == 1

    def test_empty_results_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        result = runner.invoke(app, ["report", str(f)])
        assert result.exit_code == 1

    def test_table_format(self, results_file: Path) -> None:
        result = runner.invoke(app, ["report", str(results_file)])
        assert result.exit_code == 0
        assert "s1" in result.output

    def test_json_format(self, results_file: Path) -> None:
        result = runner.invoke(app, ["report", str(results_file), "--format", "json"])
        assert result.exit_code == 0
        assert "summary" in result.output

    def test_csv_format(self, results_file: Path, tmp_path: Path) -> None:
        out = tmp_path / "out.csv"
        result = runner.invoke(
            app, ["report", str(results_file), "--format", "csv", "--output", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()

    def test_no_conversations_flag(self, results_file: Path) -> None:
        result = runner.invoke(app, ["report", str(results_file), "--no-conversations"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


class TestRun:
    def test_missing_scenario(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["run", str(tmp_path / "nope.yaml")])
        assert result.exit_code == 1

    def test_invalid_scenario(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("name: test\n")
        result = runner.invoke(app, ["run", str(f)])
        assert result.exit_code == 1
