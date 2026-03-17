"""Benchmark orchestration — concurrent users, sequential iterations, metric collection."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

import anyio

from llm_bench.clients import get_client
from llm_bench.clients.base import BaseClient
from llm_bench.config import (
    BenchmarkTarget,
    ConversationTemplate,
    LoadConfig,
    Message,
    ModelConfig,
    ScenarioConfig,
    ServerConfig,
)
from llm_bench.gpu_monitor import GpuMonitor
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
        metrics_client: BaseClient | None = None,
        gpu_monitor: GpuMonitor | None = None,
        run_id: str = "",
        gpu_type: str | None = None,
        model_dtype: str | None = None,
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
        self.metrics_client = metrics_client
        self.gpu_monitor = gpu_monitor
        self.run_id = run_id
        self.gpu_type = gpu_type
        self.model_dtype = model_dtype
        self.gpu_host: str | None = None

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

                perf_ts = time.perf_counter()
                try:
                    result = await client.complete(history, self.model)
                    if self.metrics_client is not None:
                        backend_m = await self.metrics_client.backend_metrics()
                    else:
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

                gpu_m: dict = {}
                if self.gpu_monitor is not None and self.gpu_host:
                    nearest = self.gpu_monitor.get_nearest(self.gpu_host, perf_ts)
                    if nearest:
                        gpu_m = nearest

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
                        concurrent_users_level=self.concurrent_users_level,
                        run_id=self.run_id,
                        gpu_type=self.gpu_type,
                        model_dtype=self.model_dtype,
                        # Backend metrics (flat)
                        kv_cache_usage=backend_m.get("kv_cache_usage"),
                        cache_hit_rate=backend_m.get("cache_hit_rate"),
                        requests_running=backend_m.get("requests_running"),
                        requests_waiting=backend_m.get("requests_waiting"),
                        # GPU metrics (flat)
                        gpu_mem_used_mib=gpu_m.get("gpu_mem_used_mib"),
                        gpu_mem_total_mib=gpu_m.get("gpu_mem_total_mib"),
                        gpu_util_pct=gpu_m.get("gpu_util_pct"),
                        gpu_temp_c_max=gpu_m.get("gpu_temp_c_max"),
                        gpu_power_w_total=gpu_m.get("gpu_power_w_total"),
                        gpu_mem_util_pct_avg=gpu_m.get("gpu_mem_util_pct_avg"),
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
        metrics_clients: dict[str, BaseClient] | None = None,
        gpu_monitor: GpuMonitor | None = None,
    ) -> None:
        self.scenario = scenario
        self.target = target
        self.on_result = on_result
        self.metrics_clients = metrics_clients or {}
        self.gpu_monitor = gpu_monitor

    async def run(self, concurrent_users_level: int = 0) -> list[RequestMetrics]:
        server = self.scenario.get_server(self.target.server)
        model = self.scenario.get_model(self.target.model)
        conversation = self.scenario.get_conversation(self.target.conversation)
        load = self.scenario.load
        results: list[RequestMetrics] = []

        metrics_client = (
            self.metrics_clients.get(self.target.backend) if self.target.backend else None
        )
        backend_cfg = None
        if self.target.backend and self.scenario.backends:
            try:
                backend_cfg = self.scenario.get_backend(self.target.backend)
            except KeyError:
                pass

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
                    metrics_client,
                    backend_cfg,
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
        metrics_client: BaseClient | None = None,
        backend_cfg: object | None = None,
    ) -> None:
        """Ramp-up delay + sequential iterations for one virtual user."""
        if load.ramp_up_seconds and user_id > 0:
            delay = load.ramp_up_seconds / load.concurrent_users * user_id
            await anyio.sleep(delay)

        from llm_bench.config import BackendConfig

        gpu_type = backend_cfg.gpu_type if isinstance(backend_cfg, BackendConfig) else None
        model_dtype = backend_cfg.model_dtype if isinstance(backend_cfg, BackendConfig) else None
        gpu_host = backend_cfg.ssh_host if isinstance(backend_cfg, BackendConfig) else None

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
                metrics_client=metrics_client,
                gpu_monitor=self.gpu_monitor,
                run_id=self.scenario.run_id,
                gpu_type=gpu_type,
                model_dtype=model_dtype,
            )
            runner.gpu_host = gpu_host
            await runner.run()


class RampRunner:
    """Iterates over ramp_levels, running each level sequentially with a pause between."""

    def __init__(
        self,
        scenario: ScenarioConfig,
        on_result: ResultCallback,
        metrics_clients: dict[str, BaseClient] | None = None,
        gpu_monitor: GpuMonitor | None = None,
    ) -> None:
        self.scenario = scenario
        self.on_result = on_result
        self.metrics_clients = metrics_clients or {}
        self.gpu_monitor = gpu_monitor

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
                target_runner = TargetRunner(
                    level_scenario,
                    target,
                    self.on_result,
                    metrics_clients=self.metrics_clients,
                    gpu_monitor=self.gpu_monitor,
                )
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
        metrics_clients: dict[str, BaseClient] = {}
        gpu_monitor: GpuMonitor | None = None

        for cfg in self.scenario.backends:
            client = get_client(cfg.to_server_config())
            await client.__aenter__()
            metrics_clients[cfg.name] = client

        if any(b.ssh_host for b in self.scenario.backends):
            gpu_monitor = GpuMonitor(self.scenario.backends)

        try:
            if self.scenario.load.ramp_levels:
                return await self._run_with_gpu(
                    RampRunner(self.scenario, self.on_result, metrics_clients, gpu_monitor),
                    gpu_monitor,
                )

            all_results: list[RequestMetrics] = []
            t_start = time.perf_counter()

            async with anyio.create_task_group() as tg:
                if gpu_monitor:
                    await gpu_monitor.start(tg)

                for target in self.scenario.targets:
                    target_runner = TargetRunner(
                        self.scenario,
                        target,
                        self.on_result,
                        metrics_clients=metrics_clients,
                        gpu_monitor=gpu_monitor,
                    )
                    results = await target_runner.run()
                    all_results.extend(results)

                if gpu_monitor:
                    gpu_monitor.stop()

            total_duration = time.perf_counter() - t_start
            logger.info(
                "Benchmark complete in %.1fs, %d requests", total_duration, len(all_results)
            )
            return all_results, total_duration
        finally:
            for client in metrics_clients.values():
                await client.__aexit__(None, None, None)

    async def _run_with_gpu(
        self,
        ramp_runner: RampRunner,
        gpu_monitor: GpuMonitor | None,
    ) -> tuple[list[RequestMetrics], float]:
        async with anyio.create_task_group() as tg:
            if gpu_monitor:
                await gpu_monitor.start(tg)
            result = await ramp_runner.run()
            if gpu_monitor:
                gpu_monitor.stop()
        return result
