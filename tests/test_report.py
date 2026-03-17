"""Tests for report.py — JsonlWriter, load_jsonl, export_csv, flatten."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from llm_bench.metrics import RequestMetrics
from llm_bench.report import JsonlWriter, export_csv, load_jsonl, print_ramp_table


def _make_result(
    scenario: str = "s",
    server: str = "srv",
    concurrent_users_level: int = 0,
    **kwargs: object,
) -> RequestMetrics:
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
    def test_write_requires_context_manager(self, tmp_path: Path) -> None:
        writer = JsonlWriter(tmp_path / "out.jsonl")
        with pytest.raises(RuntimeError):
            writer.write(_make_result())

    def test_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        m = _make_result()
        with JsonlWriter(path) as writer:
            writer.write(m)
        loaded = load_jsonl(path)
        assert len(loaded) == 1
        assert loaded[0].scenario == m.scenario
        assert loaded[0].ttft_s == m.ttft_s

    def test_multiple_writes(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        with JsonlWriter(path) as writer:
            for i in range(5):
                writer.write(_make_result(scenario=f"s{i}"))
        loaded = load_jsonl(path)
        assert len(loaded) == 5

    def test_file_created_on_enter(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        assert not path.exists()
        with JsonlWriter(path):
            assert path.exists()


class TestLoadJsonl:
    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        assert load_jsonl(path) == []

    def test_blank_lines_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        m = _make_result()
        with JsonlWriter(path) as w:
            w.write(m)
        path.write_text("\n" + path.read_text() + "\n")
        loaded = load_jsonl(path)
        assert len(loaded) == 1


class TestPrintRampTable:
    def test_smoke(self) -> None:
        """print_ramp_table should not raise with valid ramp results."""
        results = [
            _make_result(server="vllm", concurrent_users_level=1),
            _make_result(server="vllm", concurrent_users_level=5),
            _make_result(server="vllm", concurrent_users_level=10),
        ]
        print_ramp_table(results)  # should not raise

    def test_sorted_by_server_model_level(self, capsys) -> None:
        """Rows appear sorted by (server, model, level) — verify via group_by_level."""
        from llm_bench.metrics import group_by_level

        results = [
            _make_result(server="b-server", concurrent_users_level=10),
            _make_result(server="a-server", concurrent_users_level=5),
            _make_result(server="a-server", concurrent_users_level=1),
        ]
        groups = group_by_level(results)
        keys = sorted(groups.keys())
        assert keys[0] == ("a-server", "mdl", 1)
        assert keys[1] == ("a-server", "mdl", 5)
        assert keys[2] == ("b-server", "mdl", 10)


class TestExportCsv:
    def test_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / "out.csv"
        export_csv([_make_result()], path)
        assert path.exists()

    def test_csv_has_expected_columns(self, tmp_path: Path) -> None:
        path = tmp_path / "out.csv"
        export_csv([_make_result()], path)
        with path.open() as f:
            reader = csv.DictReader(f)
            row = next(reader)
        assert "ttft_s" in row
        assert "success" in row

    def test_empty_results_no_file(self, tmp_path: Path) -> None:
        path = tmp_path / "out.csv"
        export_csv([], path)
        assert not path.exists()

    def test_backend_metrics_as_columns(self, tmp_path: Path) -> None:
        """Backend metrics appear as top-level CSV columns."""
        results = [
            _make_result(server="vllm", kv_cache_usage=0.3),
            _make_result(server="sglang", cache_hit_rate=0.8),
        ]
        path = tmp_path / "out.csv"
        export_csv(results, path)
        with path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert "kv_cache_usage" in rows[0]
        assert "cache_hit_rate" in rows[0]
