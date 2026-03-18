"""
Tests for report.py.
Tests JsonlWriter lifecycle, JSONL roundtrip, CSV export with heterogeneous
backend metrics, and ramp table rendering.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from llm_grill.metrics import RequestMetrics
from llm_grill.report import JsonlWriter, export_csv, load_jsonl, print_ramp_table


def _make_result(
    scenario: str = "s",
    server: str = "srv",
    concurrent_users_level: int = 0,
    **kwargs: object,
) -> RequestMetrics:
    """Build a RequestMetrics instance with sensible defaults for testing."""
    return RequestMetrics(
        scenario=scenario,
        target_server=server,
        target_model="mdl",
        conversation="c",
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
        concurrent_users_level=concurrent_users_level,
        **kwargs,
    )


class TestJsonlWriter:
    """Tests for JsonlWriter context manager and write behavior."""

    def test_should_raise_when_write_called_without_context_manager(self, tmp_path: Path):
        """
        Should raise RuntimeError when write() is called outside context manager.

        Given: A JsonlWriter not entered via `with`
        When: Calling write()
        Then: RuntimeError is raised
        """
        # Given
        writer = JsonlWriter(tmp_path / "out.jsonl")

        # When / Then
        with pytest.raises(RuntimeError):
            writer.write(_make_result())

    def test_should_roundtrip_through_write_and_load(self, tmp_path: Path):
        """
        Should write and load back a metric with identical values.

        Given: A RequestMetrics written via JsonlWriter
        When: Loading the file with load_jsonl()
        Then: Loaded metric has same scenario and ttft values
        """
        # Given
        path = tmp_path / "out.jsonl"
        original = _make_result()

        # When
        with JsonlWriter(path) as writer:
            writer.write(original)
        loaded = load_jsonl(path)

        # Then
        assert len(loaded) == 1
        assert loaded[0].scenario == original.scenario
        assert loaded[0].ttft_s == original.ttft_s

    def test_should_handle_multiple_writes(self, tmp_path: Path):
        """
        Should write multiple metrics and load them all back.

        Given: Five metrics written sequentially
        When: Loading the file
        Then: All five are loaded
        """
        # Given
        path = tmp_path / "out.jsonl"

        # When
        with JsonlWriter(path) as writer:
            for i in range(5):
                writer.write(_make_result(scenario=f"s{i}"))
        loaded = load_jsonl(path)

        # Then
        assert len(loaded) == 5

    def test_should_create_file_on_enter(self, tmp_path: Path):
        """
        Should create the file when entering the context manager.

        Given: A path to a non-existent file
        When: Entering the JsonlWriter context
        Then: The file exists on disk
        """
        # Given
        path = tmp_path / "out.jsonl"
        assert not path.exists()

        # When
        with JsonlWriter(path):
            # Then
            assert path.exists()


class TestLoadJsonl:
    """Tests for load_jsonl() edge cases."""

    def test_should_return_empty_list_for_empty_file(self, tmp_path: Path):
        """
        Should return an empty list when the file is empty.

        Given: An empty JSONL file
        When: Calling load_jsonl()
        Then: Returns []
        """
        # Given
        path = tmp_path / "empty.jsonl"
        path.write_text("")

        # When / Then
        assert load_jsonl(path) == []

    def test_should_skip_blank_lines(self, tmp_path: Path):
        """
        Should ignore blank lines when loading JSONL.

        Given: A JSONL file with blank lines around the data
        When: Calling load_jsonl()
        Then: Returns only the valid metrics
        """
        # Given
        path = tmp_path / "out.jsonl"
        with JsonlWriter(path) as w:
            w.write(_make_result())
        path.write_text("\n" + path.read_text() + "\n")

        # When
        loaded = load_jsonl(path)

        # Then
        assert len(loaded) == 1


class TestPrintRampTable:
    """Tests for ramp table rendering."""

    def test_should_not_raise_with_valid_ramp_results(self):
        """
        Should render without errors for valid ramp results.

        Given: Results at three different concurrency levels
        When: Calling print_ramp_table()
        Then: No exception is raised
        """
        # Given
        results = [
            _make_result(server="vllm", concurrent_users_level=1),
            _make_result(server="vllm", concurrent_users_level=5),
            _make_result(server="vllm", concurrent_users_level=10),
        ]

        # When / Then (no exception)
        print_ramp_table(results)

    def test_should_sort_groups_by_server_model_level(self):
        """
        Should group and sort by (server, model, level).

        Given: Results from two servers at different levels
        When: Grouping by level
        Then: Keys are sorted by server, model, then level
        """
        # Given
        from llm_grill.metrics import group_by_level

        results = [
            _make_result(server="b-server", concurrent_users_level=10),
            _make_result(server="a-server", concurrent_users_level=5),
            _make_result(server="a-server", concurrent_users_level=1),
        ]

        # When
        groups = group_by_level(results)
        keys = sorted(groups.keys())

        # Then
        assert keys[0] == ("a-server", "mdl", 1)
        assert keys[1] == ("a-server", "mdl", 5)
        assert keys[2] == ("b-server", "mdl", 10)


class TestExportCsv:
    """Tests for CSV export functionality."""

    def test_should_create_csv_file(self, tmp_path: Path):
        """
        Should create a CSV file on disk.

        Given: One result to export
        When: Calling export_csv()
        Then: The file exists
        """
        # Given
        path = tmp_path / "out.csv"

        # When
        export_csv([_make_result()], path)

        # Then
        assert path.exists()

    def test_should_include_expected_columns(self, tmp_path: Path):
        """
        Should include standard metric columns in the CSV header.

        Given: One result to export
        When: Reading the CSV
        Then: ttft_s and success columns are present
        """
        # Given
        path = tmp_path / "out.csv"
        export_csv([_make_result()], path)

        # When
        with path.open() as f:
            row = next(csv.DictReader(f))

        # Then
        assert "ttft_s" in row
        assert "success" in row

    def test_should_not_create_file_when_results_empty(self, tmp_path: Path):
        """
        Should not create a file when results list is empty.

        Given: An empty results list
        When: Calling export_csv()
        Then: No file is created
        """
        # Given
        path = tmp_path / "out.csv"

        # When
        export_csv([], path)

        # Then
        assert not path.exists()

    def test_should_flatten_heterogeneous_backend_metrics(self, tmp_path: Path):
        """
        Should include all backend_metrics keys as columns across all rows.

        Given: Two results with different backend_metrics keys
        When: Exporting to CSV
        Then: Both keys appear as columns in all rows
        """
        # Given
        results = [
            _make_result(server="vllm", kv_cache_usage=0.3),
            _make_result(server="sglang", cache_hit_rate=0.8),
        ]
        path = tmp_path / "out.csv"

        # When
        export_csv(results, path)
        with path.open() as f:
            rows = list(csv.DictReader(f))

        # Then
        assert len(rows) == 2
        assert "kv_cache_usage" in rows[0]
        assert "cache_hit_rate" in rows[0]
