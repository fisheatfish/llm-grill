"""
Tests for cli.py.
Tests all Typer commands (--version, show-scenario, ping, report, run)
via CliRunner, covering success paths and error handling.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from llm_grill.cli import app
from llm_grill.metrics import RequestMetrics
from llm_grill.report import JsonlWriter

cli_runner = CliRunner()


@pytest.fixture()
def valid_scenario_file(tmp_path: Path) -> Path:
    """Create a valid YAML scenario file on disk."""
    data = {
        "name": "test",
        "backends": [{"name": "b1", "url": "http://localhost:8000", "type": "vllm"}],
        "models": [{"name": "m1", "max_tokens": 128}],
        "conversations": [{"name": "c1", "turns": [{"role": "user", "content": "hello"}]}],
        "targets": [{"backend": "b1", "model": "m1", "conversation": "c1"}],
    }
    f = tmp_path / "scenario.yaml"
    f.write_text(yaml.dump(data))
    return f


@pytest.fixture()
def results_file(tmp_path: Path) -> Path:
    """Create a JSONL results file with one successful metric."""
    path = tmp_path / "results.jsonl"
    m = RequestMetrics(
        scenario="test",
        target_server="b1",
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


class TestVersion:
    """Tests for the --version flag."""

    def test_should_display_version_string(self):
        """
        Should print the version and exit successfully.

        Given: No arguments except --version
        When: Invoking the CLI
        Then: Exit code is 0 and output contains the version
        """
        # When
        result = cli_runner.invoke(app, ["--version"])

        # Then
        assert result.exit_code == 0
        assert "0.1.1" in result.output


class TestShowScenario:
    """Tests for the show-scenario command."""

    def test_should_display_scenario_details_when_valid(self, valid_scenario_file: Path):
        """
        Should print scenario name and server info for a valid file.

        Given: A valid scenario YAML file
        When: Running show-scenario
        Then: Exit code is 0 and output contains scenario and server names
        """
        # When
        result = cli_runner.invoke(app, ["show-scenario", str(valid_scenario_file)])

        # Then
        assert result.exit_code == 0
        assert "test" in result.output
        assert "b1" in result.output

    def test_should_exit_1_when_file_missing(self, tmp_path: Path):
        """
        Should exit with code 1 when scenario file does not exist.

        Given: A path to a non-existent file
        When: Running show-scenario
        Then: Exit code is 1
        """
        # When
        result = cli_runner.invoke(app, ["show-scenario", str(tmp_path / "nope.yaml")])

        # Then
        assert result.exit_code == 1

    def test_should_exit_1_when_schema_invalid(self, tmp_path: Path):
        """
        Should exit with code 1 when YAML is missing required fields.

        Given: A YAML file with only the name field
        When: Running show-scenario
        Then: Exit code is 1
        """
        # Given
        f = tmp_path / "bad.yaml"
        f.write_text("name: test\n")

        # When
        result = cli_runner.invoke(app, ["show-scenario", str(f)])

        # Then
        assert result.exit_code == 1


class TestPing:
    """Tests for the ping command."""

    def test_should_exit_1_when_file_missing(self, tmp_path: Path):
        """
        Should exit with code 1 when scenario file does not exist.

        Given: A path to a non-existent file
        When: Running ping
        Then: Exit code is 1
        """
        # When
        result = cli_runner.invoke(app, ["ping", str(tmp_path / "nope.yaml")])

        # Then
        assert result.exit_code == 1


class TestReport:
    """Tests for the report command."""

    def test_should_exit_1_when_results_file_missing(self, tmp_path: Path):
        """
        Should exit with code 1 when results file does not exist.

        Given: A path to a non-existent JSONL file
        When: Running report
        Then: Exit code is 1
        """
        # When
        result = cli_runner.invoke(app, ["report", str(tmp_path / "nope.jsonl")])

        # Then
        assert result.exit_code == 1

    def test_should_exit_1_when_results_file_empty(self, tmp_path: Path):
        """
        Should exit with code 1 when results file is empty.

        Given: An empty JSONL file
        When: Running report
        Then: Exit code is 1
        """
        # Given
        f = tmp_path / "empty.jsonl"
        f.write_text("")

        # When
        result = cli_runner.invoke(app, ["report", str(f)])

        # Then
        assert result.exit_code == 1

    def test_should_display_table_with_server_info(self, results_file: Path):
        """
        Should print a summary table containing the server name.

        Given: A valid JSONL results file
        When: Running report with default format (table)
        Then: Exit code is 0 and server name appears in output
        """
        # When
        result = cli_runner.invoke(app, ["report", str(results_file)])

        # Then
        assert result.exit_code == 0
        assert "b1" in result.output

    def test_should_output_json_with_summary_key(self, results_file: Path):
        """
        Should output JSON containing a "summary" key.

        Given: A valid JSONL results file
        When: Running report --format json
        Then: Exit code is 0 and output contains "summary"
        """
        # When
        result = cli_runner.invoke(app, ["report", str(results_file), "--format", "json"])

        # Then
        assert result.exit_code == 0
        assert "summary" in result.output

    def test_should_create_csv_file(self, results_file: Path, tmp_path: Path):
        """
        Should create a CSV file at the specified output path.

        Given: A valid JSONL results file and an output path
        When: Running report --format csv --output
        Then: Exit code is 0 and the CSV file exists
        """
        # Given
        out = tmp_path / "out.csv"

        # When
        result = cli_runner.invoke(
            app, ["report", str(results_file), "--format", "csv", "--output", str(out)]
        )

        # Then
        assert result.exit_code == 0
        assert out.exists()

    def test_should_respect_no_conversations_flag(self, results_file: Path):
        """
        Should succeed when --no-conversations flag is passed.

        Given: A valid JSONL results file
        When: Running report --no-conversations
        Then: Exit code is 0
        """
        # When
        result = cli_runner.invoke(app, ["report", str(results_file), "--no-conversations"])

        # Then
        assert result.exit_code == 0


class TestRun:
    """Tests for the run command error paths."""

    def test_should_exit_1_when_scenario_missing(self, tmp_path: Path):
        """
        Should exit with code 1 when scenario file does not exist.

        Given: A path to a non-existent scenario
        When: Running run
        Then: Exit code is 1
        """
        # When
        result = cli_runner.invoke(app, ["run", str(tmp_path / "nope.yaml")])

        # Then
        assert result.exit_code == 1

    def test_should_exit_1_when_scenario_invalid(self, tmp_path: Path):
        """
        Should exit with code 1 when scenario YAML is invalid.

        Given: A YAML file missing required fields
        When: Running run
        Then: Exit code is 1
        """
        # Given
        f = tmp_path / "bad.yaml"
        f.write_text("name: test\n")

        # When
        result = cli_runner.invoke(app, ["run", str(f)])

        # Then
        assert result.exit_code == 1
