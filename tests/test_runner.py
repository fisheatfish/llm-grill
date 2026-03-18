"""
Tests for runner.py.
Tests orchestration: ConversationRunner, RampRunner, BenchmarkRunner,
metric collection, concurrent users, and metrics client delegation.
"""

from __future__ import annotations

import pytest

from llm_bench.clients.base import StreamResult
from llm_bench.config import LoadConfig, ScenarioConfig
from llm_bench.metrics import RequestMetrics
from llm_bench.runner import BenchmarkRunner, ConversationRunner, RampRunner


@pytest.fixture()
def mock_stream_result() -> StreamResult:
    """Create a successful StreamResult for mocking client.complete()."""
    return StreamResult(
        content="response",
        ttft_s=0.05,
        e2e_latency_s=0.3,
        tpot_s=0.01,
        prompt_tokens=10,
        completion_tokens=8,
        tokens_per_second=26.0,
    )


@pytest.fixture()
def mock_client(mocker, mock_stream_result):
    """Create a fully mocked async client with context manager support."""
    client = mocker.AsyncMock()
    client.__aenter__ = mocker.AsyncMock(return_value=client)
    client.__aexit__ = mocker.AsyncMock(return_value=None)
    client.complete = mocker.AsyncMock(return_value=mock_stream_result)
    client.backend_metrics = mocker.AsyncMock(return_value={})
    mocker.patch("llm_bench.runner.get_client", return_value=client)
    return client


class TestConversationRunner:
    """Tests for single conversation execution."""

    async def test_should_produce_one_metric_per_user_turn(
        self,
        scenario: ScenarioConfig,
        mock_client,
    ):
        """
        Should collect one RequestMetrics for a single-turn conversation.

        Given: A single-turn conversation and a mocked client
        When: Running the conversation
        Then: One successful metric is collected with correct values
        """
        # Given
        collected: list[RequestMetrics] = []

        backend = scenario.get_backend("test-vllm")
        model = scenario.get_model("test-model")
        conv = scenario.get_conversation("simple")

        runner = ConversationRunner(
            backend=backend,
            model=model,
            conversation=conv,
            scenario_name="test-scenario",
            user_id=0,
            iteration=0,
            think_time=0.0,
            on_result=collected.append,
        )

        # When
        await runner.run()

        # Then
        assert len(collected) == 1
        assert collected[0].success is True
        assert collected[0].ttft_s == 0.05
        assert collected[0].turn == 0

    async def test_should_record_failure_when_client_raises(
        self,
        scenario: ScenarioConfig,
        mock_client,
    ):
        """
        Should record a failed metric when client.complete() raises.

        Given: A client that raises on complete()
        When: Running the conversation
        Then: One failed metric is collected with the error message
        """
        # Given
        mock_client.complete = mock_client.complete.__class__(
            side_effect=Exception("connection refused")
        )
        collected: list[RequestMetrics] = []
        backend = scenario.get_backend("test-vllm")
        model = scenario.get_model("test-model")
        conv = scenario.get_conversation("simple")

        runner = ConversationRunner(
            backend=backend,
            model=model,
            conversation=conv,
            scenario_name="test-scenario",
            user_id=0,
            iteration=0,
            think_time=0.0,
            on_result=collected.append,
        )

        # When
        await runner.run()

        # Then
        assert len(collected) == 1
        assert collected[0].success is False
        assert "connection refused" in collected[0].error


class TestRampRunner:
    """Tests for ramp-level execution."""

    async def test_should_produce_tagged_results_per_level(
        self,
        scenario: ScenarioConfig,
        mock_client,
    ):
        """
        Should run each ramp level and tag results with concurrent_users_level.

        Given: ramp_levels=[1, 2, 3] with 1 target and 1 iteration
        When: Running the ramp
        Then: 1+2+3=6 results, each tagged with its level
        """
        # Given
        ramp_scenario = scenario.model_copy(
            update={"load": LoadConfig(ramp_levels=[1, 2, 3], ramp_pause_seconds=0.0)}
        )
        collected: list[RequestMetrics] = []

        runner = RampRunner(ramp_scenario, on_result=collected.append)

        # When
        results, duration = await runner.run()

        # Then
        assert len(results) == 6
        assert {r.concurrent_users_level for r in results} == {1, 2, 3}

    async def test_should_dispatch_to_ramp_runner_when_levels_set(
        self,
        scenario: ScenarioConfig,
        mock_client,
    ):
        """
        Should route to RampRunner when ramp_levels is defined.

        Given: A scenario with ramp_levels=[1, 2]
        When: Running via BenchmarkRunner
        Then: Results are tagged with concurrent_users_level
        """
        # Given
        ramp_scenario = scenario.model_copy(
            update={"load": LoadConfig(ramp_levels=[1, 2], ramp_pause_seconds=0.0)}
        )
        collected: list[RequestMetrics] = []

        bench = BenchmarkRunner(ramp_scenario, on_result=collected.append)

        # When
        results, _ = await bench.run()

        # Then
        assert len(results) == 3
        assert {r.concurrent_users_level for r in results} == {1, 2}


class TestConversationRunnerMetricsClient:
    """Tests for metrics client delegation in ConversationRunner."""

    async def test_should_use_metrics_client_instead_of_gateway_client(
        self,
        scenario: ScenarioConfig,
        mock_client,
        mocker,
    ):
        """
        Should call metrics_client.backend_metrics() instead of the gateway client's.

        Given: A ConversationRunner with a separate metrics_client
        When: Running the conversation
        Then: Metrics come from metrics_client, not the gateway client
        """
        # Given
        mock_metrics_client = mocker.AsyncMock()
        mock_metrics_client.backend_metrics = mocker.AsyncMock(
            return_value={"kv_cache_usage": 0.42}
        )

        collected: list[RequestMetrics] = []

        backend = scenario.get_backend("test-vllm")
        model = scenario.get_model("test-model")
        conv = scenario.get_conversation("simple")

        runner = ConversationRunner(
            backend=backend,
            model=model,
            conversation=conv,
            scenario_name="test-scenario",
            user_id=0,
            iteration=0,
            think_time=0.0,
            on_result=collected.append,
            metrics_client=mock_metrics_client,
            run_id="test1234",
        )

        # When
        await runner.run()

        # Then
        assert len(collected) == 1
        m = collected[0]
        assert m.kv_cache_usage == 0.42
        assert m.run_id == "test1234"
        # The gateway client's backend_metrics should NOT have been called
        mock_client.backend_metrics.assert_not_called()
        mock_metrics_client.backend_metrics.assert_called_once()


class TestBenchmarkRunner:
    """Tests for top-level BenchmarkRunner orchestration."""

    async def test_should_collect_all_results(
        self,
        scenario: ScenarioConfig,
        mock_client,
    ):
        """
        Should collect results from all targets and return positive duration.

        Given: A scenario with one target
        When: Running the benchmark
        Then: One result is collected and duration is non-negative
        """
        # Given
        collected: list[RequestMetrics] = []
        bench = BenchmarkRunner(scenario, on_result=collected.append)

        # When
        results, duration = await bench.run()

        # Then
        assert len(results) == 1
        assert duration >= 0

    async def test_should_produce_results_per_user_and_iteration(
        self,
        scenario: ScenarioConfig,
        mock_client,
    ):
        """
        Should produce N_users * N_iterations results.

        Given: 3 concurrent users and 2 iterations
        When: Running the benchmark
        Then: 6 results are collected
        """
        # Given
        local_scenario = scenario.model_copy(
            update={"load": LoadConfig(concurrent_users=3, iterations=2)}
        )
        collected: list[RequestMetrics] = []
        bench = BenchmarkRunner(local_scenario, on_result=collected.append)

        # When
        results, _ = await bench.run()

        # Then
        assert len(results) == 6
