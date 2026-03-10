"""Tests for metrics.py — RequestMetrics, aggregation, conversation metrics."""

from __future__ import annotations

import json

import pytest

from llm_bench.metrics import (
    RequestMetrics,
    aggregate,
    aggregate_conversations,
)


def _make_result(
    success: bool = True,
    ttft: float = 0.1,
    tpot: float = 0.02,
    e2e: float = 0.5,
    completion_tokens: int = 20,
    turn: int = 0,
    conversation: str = "c",
    server: str = "srv",
    backend_metrics: dict | None = None,
) -> RequestMetrics:
    return RequestMetrics(
        scenario="s",
        target_server=server,
        target_model="mdl",
        conversation=conversation,
        turn=turn,
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
        backend_metrics=backend_metrics or {},
    )


# ---------------------------------------------------------------------------
# RequestMetrics
# ---------------------------------------------------------------------------


class TestRequestMetrics:
    def test_to_jsonl_is_valid_json(self) -> None:
        m = _make_result()
        parsed = json.loads(m.to_jsonl())
        assert parsed["scenario"] == "s"
        assert parsed["success"] is True

    def test_failed_result(self) -> None:
        m = _make_result(success=False)
        assert not m.success


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------


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
        with pytest.raises(ValueError):
            aggregate([], total_duration_s=1.0)

    def test_p95_single_value(self) -> None:
        results = [_make_result(ttft=0.5)]
        agg = aggregate(results, total_duration_s=1.0)
        assert agg.ttft_p95_s == 0.5


# ---------------------------------------------------------------------------
# aggregate_conversations
# ---------------------------------------------------------------------------


class TestAggregateConversations:
    def test_single_turn_no_ratio(self) -> None:
        results = [_make_result(turn=0, ttft=0.1)]
        conv = aggregate_conversations(results)
        assert len(conv) == 1
        assert conv[0].turn_to_turn_ratio is None  # only one turn
        assert conv[0].context_growth_factor is None

    def test_multi_turn_ratio(self) -> None:
        # turn 0 TTFT=0.4s, turn 1 TTFT=0.2s → ratio = 0.2/0.4 = 0.5 (cache helps)
        results = [
            _make_result(turn=0, ttft=0.4, e2e=1.0),
            _make_result(turn=1, ttft=0.2, e2e=0.8),
        ]
        conv = aggregate_conversations(results)
        assert len(conv) == 1
        c = conv[0]
        assert c.turn_to_turn_ratio == pytest.approx(0.5)
        assert c.context_growth_factor == pytest.approx(0.8)

    def test_context_growth_increases(self) -> None:
        # E2E grows with context
        results = [
            _make_result(turn=0, e2e=0.5),
            _make_result(turn=1, e2e=0.8),
            _make_result(turn=2, e2e=1.2),
        ]
        conv = aggregate_conversations(results)
        assert conv[0].context_growth_factor == pytest.approx(1.2 / 0.5)

    def test_grouped_by_server_and_conversation(self) -> None:
        results = [
            _make_result(server="vllm", conversation="c1", turn=0),
            _make_result(server="sglang", conversation="c1", turn=0),
        ]
        conv = aggregate_conversations(results)
        assert len(conv) == 2
        servers = {c.target_server for c in conv}
        assert servers == {"vllm", "sglang"}

    def test_kv_cache_hit_rate_sglang(self) -> None:
        results = [
            _make_result(backend_metrics={"cache_hit_rate": 0.75}),
            _make_result(backend_metrics={"cache_hit_rate": 0.85}),
        ]
        conv = aggregate_conversations(results)
        assert conv[0].kv_cache_hit_rate_mean == pytest.approx(0.80)

    def test_kv_cache_usage_vllm(self) -> None:
        results = [
            _make_result(backend_metrics={"vllm:gpu_cache_usage_perc": 0.30}),
            _make_result(backend_metrics={"vllm:gpu_cache_usage_perc": 0.50}),
        ]
        conv = aggregate_conversations(results)
        assert conv[0].kv_cache_usage_mean == pytest.approx(0.40)

    def test_missing_backend_metrics_returns_none(self) -> None:
        results = [_make_result(backend_metrics={})]
        conv = aggregate_conversations(results)
        assert conv[0].kv_cache_hit_rate_mean is None
        assert conv[0].kv_cache_usage_mean is None

    def test_failed_requests_excluded_from_turn_metrics(self) -> None:
        results = [
            _make_result(turn=0, ttft=0.1, success=True),
            _make_result(turn=0, ttft=999.0, success=False),
        ]
        conv = aggregate_conversations(results)
        assert conv[0].ttft_by_turn[0] == pytest.approx(0.1)
