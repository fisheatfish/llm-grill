"""Tests for metrics.py — RequestMetrics and aggregation."""

from __future__ import annotations

import json

from llm_bench.metrics import RequestMetrics, aggregate


def _make_result(
    success: bool = True,
    ttft: float = 0.1,
    tpot: float = 0.02,
    e2e: float = 0.5,
    completion_tokens: int = 20,
) -> RequestMetrics:
    return RequestMetrics(
        scenario="s",
        target_server="srv",
        target_model="mdl",
        conversation="c",
        turn=0,
        iteration=0,
        user_id=0,
        timestamp_start="2026-01-01T00:00:00+00:00",
        ttft_s=ttft,
        tpot_s=tpot,
        e2e_latency_s=e2e,
        prompt_tokens=10,
        completion_tokens=completion_tokens,
        tokens_per_second=completion_tokens / e2e,
        success=success,
    )


class TestRequestMetrics:
    def test_to_jsonl_is_valid_json(self) -> None:
        m = _make_result()
        line = m.to_jsonl()
        parsed = json.loads(line)
        assert parsed["scenario"] == "s"
        assert parsed["success"] is True

    def test_failed_result(self) -> None:
        m = _make_result(success=False)
        assert not m.success


class TestAggregate:
    def test_basic_aggregation(self) -> None:
        results = [_make_result(ttft=0.1), _make_result(ttft=0.2), _make_result(ttft=0.3)]
        agg = aggregate(results, total_duration_s=1.0)
        assert agg.total_requests == 3
        assert agg.success_count == 3
        assert agg.error_count == 0
        assert agg.success_rate == 1.0
        assert abs(agg.ttft_mean_s - 0.2) < 1e-9

    def test_partial_failures(self) -> None:
        results = [_make_result(success=True), _make_result(success=False)]
        agg = aggregate(results, total_duration_s=1.0)
        assert agg.success_rate == 0.5
        assert agg.error_count == 1

    def test_requests_per_second(self) -> None:
        results = [_make_result() for _ in range(10)]
        agg = aggregate(results, total_duration_s=2.0)
        assert agg.requests_per_second == 5.0

    def test_empty_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            aggregate([], total_duration_s=1.0)

    def test_p95_with_single_value(self) -> None:
        results = [_make_result(ttft=0.5)]
        agg = aggregate(results, total_duration_s=1.0)
        assert agg.ttft_p95_s == 0.5
