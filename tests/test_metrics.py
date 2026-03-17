"""
Tests for metrics.py.
Tests RequestMetrics serialization, aggregation (mean/p95), conversation metrics,
and ramp-level grouping helpers.
"""

from __future__ import annotations

import json

import pytest

from llm_bench.metrics import (
    RequestMetrics,
    aggregate,
    aggregate_conversations,
    group_by_level,
    is_ramp_run,
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
    concurrent_users_level: int = 0,
    **kwargs: object,
) -> RequestMetrics:
    """Build a RequestMetrics instance with sensible defaults for testing."""
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
        concurrent_users_level=concurrent_users_level,
        **kwargs,
    )


class TestRampHelpers:
    """Tests for is_ramp_run() and group_by_level() helpers."""

    def test_should_detect_non_ramp_when_all_levels_zero(self):
        """
        Should return False when all results have concurrent_users_level=0.

        Given: Three results with level=0
        When: Calling is_ramp_run()
        Then: Returns False
        """
        # Given
        results = [_make_result(concurrent_users_level=0) for _ in range(3)]

        # When / Then
        assert is_ramp_run(results) is False

    def test_should_detect_non_ramp_when_single_level(self):
        """
        Should return False when all results share one non-zero level.

        Given: Three results all at level=5
        When: Calling is_ramp_run()
        Then: Returns False
        """
        # Given
        results = [_make_result(concurrent_users_level=5) for _ in range(3)]

        # When / Then
        assert is_ramp_run(results) is False

    def test_should_detect_ramp_when_multiple_levels(self):
        """
        Should return True when results span multiple concurrency levels.

        Given: Results at levels 1, 5, and 10
        When: Calling is_ramp_run()
        Then: Returns True
        """
        # Given
        results = [
            _make_result(concurrent_users_level=1),
            _make_result(concurrent_users_level=5),
            _make_result(concurrent_users_level=10),
        ]

        # When / Then
        assert is_ramp_run(results) is True

    def test_should_group_by_server_model_level(self):
        """
        Should create distinct groups keyed by (server, model, level).

        Given: Results from two servers at different levels
        When: Calling group_by_level()
        Then: Groups are keyed correctly
        """
        # Given
        results = [
            _make_result(server="s1", concurrent_users_level=1),
            _make_result(server="s1", concurrent_users_level=5),
            _make_result(server="s2", concurrent_users_level=1),
        ]

        # When
        groups = group_by_level(results)

        # Then
        assert set(groups.keys()) == {("s1", "mdl", 1), ("s1", "mdl", 5), ("s2", "mdl", 1)}

    def test_should_count_results_per_group(self):
        """
        Should place correct number of results in each group.

        Given: Two results at level=1 and one at level=5
        When: Calling group_by_level()
        Then: Counts match
        """
        # Given
        results = [
            _make_result(concurrent_users_level=1),
            _make_result(concurrent_users_level=1),
            _make_result(concurrent_users_level=5),
        ]

        # When
        groups = group_by_level(results)

        # Then
        assert len(groups[("srv", "mdl", 1)]) == 2
        assert len(groups[("srv", "mdl", 5)]) == 1


class TestRequestMetrics:
    """Tests for RequestMetrics serialization."""

    def test_should_serialize_to_valid_jsonl(self):
        """
        Should produce valid JSON with correct field values.

        Given: A successful RequestMetrics
        When: Calling to_jsonl()
        Then: Output is valid JSON with expected fields
        """
        # Given
        metrics = _make_result()

        # When
        parsed = json.loads(metrics.to_jsonl())

        # Then
        assert parsed["scenario"] == "s"
        assert parsed["success"] is True

    def test_should_serialize_failed_result(self):
        """
        Should serialize a failed result with success=False.

        Given: A failed RequestMetrics
        When: Checking success field
        Then: success is False
        """
        # Given / When
        metrics = _make_result(success=False)

        # Then
        assert not metrics.success

    def test_should_include_gpu_fields_in_jsonl(self):
        """
        Should include run_id, and gpu_metrics in JSONL output.

        Given: A RequestMetrics with GPU-related fields set
        When: Serializing to JSONL
        Then: All GPU fields are present in output
        """
        # Given
        metrics = RequestMetrics(
            scenario="s",
            target_server="srv",
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
            run_id="abc12345",
            gpu_util_pct=85.0,
            gpu_mem_used_mib=4000,
        )

        # When
        parsed = json.loads(metrics.to_jsonl())

        # Then
        assert parsed["run_id"] == "abc12345"
        assert parsed["gpu_util_pct"] == 85.0


class TestAggregate:
    """Tests for the aggregate() function."""

    def test_should_compute_correct_mean_ttft(self):
        """
        Should compute mean TTFT across all successful results.

        Given: Three results with TTFT 0.1, 0.2, 0.3
        When: Aggregating
        Then: Mean TTFT is 0.2
        """
        # Given
        results = [_make_result(ttft=0.1), _make_result(ttft=0.2), _make_result(ttft=0.3)]

        # When
        agg = aggregate(results, total_duration_s=1.0)

        # Then
        assert agg.total_requests == 3
        assert agg.success_count == 3
        assert agg.error_count == 0
        assert agg.success_rate == 1.0
        assert abs(agg.ttft_mean_s - 0.2) < 1e-9

    def test_should_handle_partial_failures(self):
        """
        Should count failures and compute correct success rate.

        Given: One success and one failure
        When: Aggregating
        Then: success_rate is 0.5 and error_count is 1
        """
        # Given
        results = [_make_result(success=True), _make_result(success=False)]

        # When
        agg = aggregate(results, total_duration_s=1.0)

        # Then
        assert agg.success_rate == 0.5
        assert agg.error_count == 1

    def test_should_compute_requests_per_second(self):
        """
        Should divide successful requests by total duration.

        Given: 10 successful results over 2.0 seconds
        When: Aggregating
        Then: requests_per_second is 5.0
        """
        # Given
        results = [_make_result() for _ in range(10)]

        # When
        agg = aggregate(results, total_duration_s=2.0)

        # Then
        assert agg.requests_per_second == 5.0

    def test_should_raise_when_results_empty(self):
        """
        Should raise ValueError when no results to aggregate.

        Given: Empty results list
        When: Calling aggregate()
        Then: ValueError is raised
        """
        # When / Then
        with pytest.raises(ValueError):
            aggregate([], total_duration_s=1.0)

    def test_should_return_value_as_p95_when_single_result(self):
        """
        Should return the single value as p95 when only one result.

        Given: One result with TTFT=0.5
        When: Aggregating
        Then: ttft_p95 is 0.5
        """
        # Given
        results = [_make_result(ttft=0.5)]

        # When
        agg = aggregate(results, total_duration_s=1.0)

        # Then
        assert agg.ttft_p95_s == 0.5


class TestAggregateConversations:
    """Tests for conversation-level metric aggregation."""

    def test_should_return_no_ratio_for_single_turn(self):
        """
        Should return None for turn_to_turn_ratio when only one turn exists.

        Given: A single-turn result
        When: Aggregating conversations
        Then: turn_to_turn_ratio and context_growth_factor are None
        """
        # Given
        results = [_make_result(turn=0, ttft=0.1)]

        # When
        conv = aggregate_conversations(results)

        # Then
        assert len(conv) == 1
        assert conv[0].turn_to_turn_ratio is None
        assert conv[0].context_growth_factor is None

    def test_should_compute_turn_ratio_below_1_when_cache_helps(self):
        """
        Should compute ratio < 1 when later turns have lower TTFT (KV cache benefit).

        Given: Turn 0 TTFT=0.4s, Turn 1 TTFT=0.2s
        When: Aggregating conversations
        Then: turn_to_turn_ratio is 0.5
        """
        # Given
        results = [
            _make_result(turn=0, ttft=0.4, e2e=1.0),
            _make_result(turn=1, ttft=0.2, e2e=0.8),
        ]

        # When
        conv = aggregate_conversations(results)

        # Then
        assert conv[0].turn_to_turn_ratio == pytest.approx(0.5)
        assert conv[0].context_growth_factor == pytest.approx(0.8)

    def test_should_compute_context_growth_above_1_when_latency_increases(self):
        """
        Should compute context_growth_factor > 1 when E2E grows with turns.

        Given: Three turns with increasing E2E latency
        When: Aggregating conversations
        Then: context_growth_factor equals last/first E2E ratio
        """
        # Given
        results = [
            _make_result(turn=0, e2e=0.5),
            _make_result(turn=1, e2e=0.8),
            _make_result(turn=2, e2e=1.2),
        ]

        # When
        conv = aggregate_conversations(results)

        # Then
        assert conv[0].context_growth_factor == pytest.approx(1.2 / 0.5)

    def test_should_group_by_server_and_conversation(self):
        """
        Should create separate conversation metrics per (server, conversation).

        Given: Results from two different servers
        When: Aggregating conversations
        Then: Two separate conversation metrics are returned
        """
        # Given
        results = [
            _make_result(server="vllm", conversation="c1", turn=0),
            _make_result(server="sglang", conversation="c1", turn=0),
        ]

        # When
        conv = aggregate_conversations(results)

        # Then
        assert len(conv) == 2
        servers = {c.target_server for c in conv}
        assert servers == {"vllm", "sglang"}

    def test_should_average_kv_cache_hit_rate_from_sglang(self):
        """
        Should compute mean cache_hit_rate from SGLang backend metrics.

        Given: Two results with cache_hit_rate 0.75 and 0.85
        When: Aggregating conversations
        Then: kv_cache_hit_rate_mean is 0.80
        """
        # Given
        results = [
            _make_result(cache_hit_rate=0.75),
            _make_result(cache_hit_rate=0.85),
        ]

        # When
        conv = aggregate_conversations(results)

        # Then
        assert conv[0].kv_cache_hit_rate_mean == pytest.approx(0.80)

    def test_should_average_kv_cache_usage_from_vllm(self):
        """
        Should compute mean gpu_cache_usage_perc from vLLM backend metrics.

        Given: Two results with cache usage 0.30 and 0.50
        When: Aggregating conversations
        Then: kv_cache_usage_mean is 0.40
        """
        # Given
        results = [
            _make_result(kv_cache_usage=0.30),
            _make_result(kv_cache_usage=0.50),
        ]

        # When
        conv = aggregate_conversations(results)

        # Then
        assert conv[0].kv_cache_usage_mean == pytest.approx(0.40)

    def test_should_return_none_when_no_backend_metrics(self):
        """
        Should return None for KV cache metrics when backend_metrics is empty.

        Given: A result with empty backend_metrics
        When: Aggregating conversations
        Then: Both KV cache metrics are None
        """
        # Given
        results = [_make_result(backend_metrics={})]

        # When
        conv = aggregate_conversations(results)

        # Then
        assert conv[0].kv_cache_hit_rate_mean is None
        assert conv[0].kv_cache_usage_mean is None

    def test_should_exclude_failed_requests_from_turn_metrics(self):
        """
        Should only use successful requests when computing per-turn metrics.

        Given: One successful result (TTFT=0.1) and one failed (TTFT=999)
        When: Aggregating conversations
        Then: Turn TTFT reflects only the successful request
        """
        # Given
        results = [
            _make_result(turn=0, ttft=0.1, success=True),
            _make_result(turn=0, ttft=999.0, success=False),
        ]

        # When
        conv = aggregate_conversations(results)

        # Then
        assert conv[0].ttft_by_turn[0] == pytest.approx(0.1)
