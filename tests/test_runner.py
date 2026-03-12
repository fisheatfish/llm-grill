"""Tests for runner.py — orchestration and metric collection."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from llm_bench.clients.base import StreamResult
from llm_bench.config import LoadConfig, ScenarioConfig
from llm_bench.metrics import RequestMetrics
from llm_bench.runner import BenchmarkRunner, ConversationRunner, RampRunner


def _mock_stream_result() -> StreamResult:
    return StreamResult(
        content="response",
        ttft_s=0.05,
        e2e_latency_s=0.3,
        tpot_s=0.01,
        prompt_tokens=10,
        completion_tokens=8,
        tokens_per_second=26.0,
    )


@pytest.mark.asyncio
class TestConversationRunner:
    async def test_single_turn_produces_metric(
        self,
        scenario: ScenarioConfig,
        mocker,
    ) -> None:
        collected: list[RequestMetrics] = []

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.complete = AsyncMock(return_value=_mock_stream_result())
        mock_client.backend_metrics = AsyncMock(return_value={})

        mocker.patch("llm_bench.runner.get_client", return_value=mock_client)

        server = scenario.get_server("test-vllm")
        model = scenario.get_model("test-model")
        conv = scenario.get_conversation("simple")

        runner = ConversationRunner(
            server=server,
            model=model,
            conversation=conv,
            scenario_name="test-scenario",
            user_id=0,
            iteration=0,
            think_time=0.0,
            on_result=collected.append,
        )
        await runner.run()

        assert len(collected) == 1
        m = collected[0]
        assert m.success is True
        assert m.ttft_s == 0.05
        assert m.turn == 0

    async def test_client_error_produces_failed_metric(
        self,
        scenario: ScenarioConfig,
        mocker,
    ) -> None:
        collected: list[RequestMetrics] = []

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.complete = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.backend_metrics = AsyncMock(return_value={})

        mocker.patch("llm_bench.runner.get_client", return_value=mock_client)

        server = scenario.get_server("test-vllm")
        model = scenario.get_model("test-model")
        conv = scenario.get_conversation("simple")

        runner = ConversationRunner(
            server=server,
            model=model,
            conversation=conv,
            scenario_name="test-scenario",
            user_id=0,
            iteration=0,
            think_time=0.0,
            on_result=collected.append,
        )
        await runner.run()

        assert len(collected) == 1
        assert collected[0].success is False
        assert "connection refused" in collected[0].error


@pytest.mark.asyncio
class TestRampRunner:
    async def test_ramp_produces_tagged_results(
        self,
        scenario: ScenarioConfig,
        mocker,
    ) -> None:
        """RampRunner levels=[1,2,3] × 1 target × 1 iter = 1+2+3=6 results, each tagged."""
        ramp_scenario = scenario.model_copy(
            update={"load": LoadConfig(ramp_levels=[1, 2, 3], ramp_pause_seconds=0.0)}
        )
        collected: list[RequestMetrics] = []

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.complete = AsyncMock(return_value=_mock_stream_result())
        mock_client.backend_metrics = AsyncMock(return_value={})

        mocker.patch("llm_bench.runner.get_client", return_value=mock_client)

        runner = RampRunner(ramp_scenario, on_result=collected.append)
        results, duration = await runner.run()

        # 1 + 2 + 3 users × 1 iteration × 1 turn each
        assert len(results) == 6
        assert {r.concurrent_users_level for r in results} == {1, 2, 3}

    async def test_benchmark_runner_dispatches_to_ramp(
        self,
        scenario: ScenarioConfig,
        mocker,
    ) -> None:
        """BenchmarkRunner routes to RampRunner when ramp_levels is set."""
        ramp_scenario = scenario.model_copy(
            update={"load": LoadConfig(ramp_levels=[1, 2], ramp_pause_seconds=0.0)}
        )
        collected: list[RequestMetrics] = []

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.complete = AsyncMock(return_value=_mock_stream_result())
        mock_client.backend_metrics = AsyncMock(return_value={})

        mocker.patch("llm_bench.runner.get_client", return_value=mock_client)

        bench = BenchmarkRunner(ramp_scenario, on_result=collected.append)
        results, _ = await bench.run()

        # 1 + 2 users × 1 iteration × 1 turn each
        assert len(results) == 3
        assert {r.concurrent_users_level for r in results} == {1, 2}


@pytest.mark.asyncio
class TestBenchmarkRunner:
    async def test_run_collects_all_results(
        self,
        scenario: ScenarioConfig,
        mocker,
    ) -> None:
        collected: list[RequestMetrics] = []

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.complete = AsyncMock(return_value=_mock_stream_result())
        mock_client.backend_metrics = AsyncMock(return_value={})

        mocker.patch("llm_bench.runner.get_client", return_value=mock_client)

        bench = BenchmarkRunner(scenario, on_result=collected.append)
        results, duration = await bench.run()

        assert len(results) == 1
        assert duration >= 0

    async def test_concurrent_users(
        self,
        scenario: ScenarioConfig,
        mocker,
    ) -> None:
        """With 3 concurrent users × 2 iterations, expect 6 results."""
        local_scenario = scenario.model_copy(
            update={"load": LoadConfig(concurrent_users=3, iterations=2)}
        )
        collected: list[RequestMetrics] = []

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.complete = AsyncMock(return_value=_mock_stream_result())
        mock_client.backend_metrics = AsyncMock(return_value={})

        mocker.patch("llm_bench.runner.get_client", return_value=mock_client)

        bench = BenchmarkRunner(local_scenario, on_result=collected.append)
        results, _ = await bench.run()

        assert len(results) == 6
