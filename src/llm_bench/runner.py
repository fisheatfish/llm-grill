"""Benchmark orchestration — concurrent users, sequential iterations, metric collection."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

import anyio

from llm_bench.clients import get_client
from llm_bench.config import (
    BenchmarkTarget,
    ConversationTemplate,
    LoadConfig,
    Message,
    ModelConfig,
    ScenarioConfig,
    ServerConfig,
)
from llm_bench.metrics import RequestMetrics

logger = logging.getLogger(__name__)

ResultCallback = Callable[[RequestMetrics], None]


class ConversationRunner:
    """Runs one full multi-turn conversation for a single (user, iteration) pair."""

    def __init__(
        self,
        server: ServerConfig,
        model: ModelConfig,
        conversation: ConversationTemplate,
        scenario_name: str,
        user_id: int,
        iteration: int,
        think_time: float,
        on_result: ResultCallback,
        concurrent_users_level: int = 0,
    ) -> None:
        self.server = server
        self.model = model
        self.conversation = conversation
        self.scenario_name = scenario_name
        self.user_id = user_id
        self.iteration = iteration
        self.think_time = think_time
        self.on_result = on_result
        self.concurrent_users_level = concurrent_users_level

    async def run(self) -> None:
        history: list[Message] = []
        turn_index = 0

        async with get_client(self.server) as client:
            for msg in self.conversation.turns:
                if msg.role in ("system", "user"):
                    history.append(msg)

                if msg.role != "user":
                    continue

                ts = datetime.now(UTC).isoformat()
                success = True
                error: str | None = None

                try:
                    result = await client.complete(history, self.model)
                    backend_m = await client.backend_metrics()
                    history.append(Message(role="assistant", content=result.content))
                except Exception as exc:
                    result = None
                    backend_m = {}
                    success = False
                    error = str(exc)
                    logger.warning(
                        "Request failed server=%s user=%d iter=%d turn=%d: %s",
                        self.server.name,
                        self.user_id,
                        self.iteration,
                        turn_index,
                        exc,
                    )

                self.on_result(
                    RequestMetrics(
                        scenario=self.scenario_name,
                        target_server=self.server.name,
                        target_model=self.model.name,
                        conversation=self.conversation.name,
                        turn=turn_index,
                        iteration=self.iteration,
                        user_id=self.user_id,
                        timestamp_start=ts,
                        ttft_s=result.ttft_s if result else 0.0,
                        tpot_s=result.tpot_s if result else 0.0,
                        e2e_latency_s=result.e2e_latency_s if result else 0.0,
                        prompt_tokens=result.prompt_tokens if result else 0,
                        completion_tokens=result.completion_tokens if result else 0,
                        tokens_per_second=result.tokens_per_second if result else 0.0,
                        success=success,
                        error=error,
                        backend_metrics=backend_m,
                        concurrent_users_level=self.concurrent_users_level,
                    )
                )
                turn_index += 1

                if self.think_time > 0:
                    await anyio.sleep(self.think_time)


class TargetRunner:
    """Runs all users concurrently, each executing their iterations sequentially."""

    def __init__(
        self,
        scenario: ScenarioConfig,
        target: BenchmarkTarget,
        on_result: ResultCallback,
    ) -> None:
        self.scenario = scenario
        self.target = target
        self.on_result = on_result

    async def run(self, concurrent_users_level: int = 0) -> list[RequestMetrics]:
        server = self.scenario.get_server(self.target.server)
        model = self.scenario.get_model(self.target.model)
        conversation = self.scenario.get_conversation(self.target.conversation)
        load = self.scenario.load
        results: list[RequestMetrics] = []

        def collect(m: RequestMetrics) -> None:
            results.append(m)
            self.on_result(m)

        logger.info(
            "Target %s/%s/%s — %d users × %d iterations",
            self.target.server,
            self.target.model,
            self.target.conversation,
            load.concurrent_users,
            load.iterations,
        )

        async with anyio.create_task_group() as tg:
            for user_id in range(load.concurrent_users):
                tg.start_soon(
                    self._run_user,
                    server,
                    model,
                    conversation,
                    load,
                    user_id,
                    collect,
                    concurrent_users_level,
                )

        return results

    async def _run_user(
        self,
        server: ServerConfig,
        model: ModelConfig,
        conversation: ConversationTemplate,
        load: LoadConfig,
        user_id: int,
        on_result: ResultCallback,
        concurrent_users_level: int = 0,
    ) -> None:
        """Ramp-up delay + sequential iterations for one virtual user."""
        if load.ramp_up_seconds and user_id > 0:
            delay = load.ramp_up_seconds / load.concurrent_users * user_id
            await anyio.sleep(delay)

        for iteration in range(load.iterations):
            runner = ConversationRunner(
                server=server,
                model=model,
                conversation=conversation,
                scenario_name=self.scenario.name,
                user_id=user_id,
                iteration=iteration,
                think_time=load.think_time_seconds,
                on_result=on_result,
                concurrent_users_level=concurrent_users_level,
            )
            await runner.run()


class RampRunner:
    """Iterates over ramp_levels, running each level sequentially with a pause between."""

    def __init__(self, scenario: ScenarioConfig, on_result: ResultCallback) -> None:
        self.scenario = scenario
        self.on_result = on_result

    async def run(self) -> tuple[list[RequestMetrics], float]:
        load = self.scenario.load
        levels = load.ramp_levels or []
        all_results: list[RequestMetrics] = []
        t_start = time.perf_counter()

        for i, level in enumerate(levels):
            level_load = load.model_copy(update={"concurrent_users": level})
            level_scenario = self.scenario.model_copy(update={"load": level_load})
            logger.info("Ramp level %d: %d concurrent users", i + 1, level)

            for target in level_scenario.targets:
                target_runner = TargetRunner(level_scenario, target, self.on_result)
                results = await target_runner.run(concurrent_users_level=level)
                all_results.extend(results)

            if i < len(levels) - 1 and load.ramp_pause_seconds > 0:
                logger.info("Pausing %.1fs before next level", load.ramp_pause_seconds)
                await anyio.sleep(load.ramp_pause_seconds)

        total_duration = time.perf_counter() - t_start
        logger.info("Ramp complete in %.1fs, %d requests", total_duration, len(all_results))
        return all_results, total_duration


class BenchmarkRunner:
    """Top-level runner — iterates over all targets in a scenario."""

    def __init__(self, scenario: ScenarioConfig, on_result: ResultCallback) -> None:
        self.scenario = scenario
        self.on_result = on_result

    async def run(self) -> tuple[list[RequestMetrics], float]:
        if self.scenario.load.ramp_levels:
            return await RampRunner(self.scenario, self.on_result).run()

        all_results: list[RequestMetrics] = []
        t_start = time.perf_counter()

        for target in self.scenario.targets:
            target_runner = TargetRunner(self.scenario, target, self.on_result)
            results = await target_runner.run()
            all_results.extend(results)

        total_duration = time.perf_counter() - t_start
        logger.info("Benchmark complete in %.1fs, %d requests", total_duration, len(all_results))
        return all_results, total_duration
