"""RequestMetrics dataclass and aggregation helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from statistics import mean, median, quantiles


@dataclass
class RequestMetrics:
    scenario: str
    target_server: str
    target_model: str
    conversation: str
    turn: int
    iteration: int
    user_id: int
    timestamp_start: str  # ISO8601
    ttft_s: float
    tpot_s: float
    e2e_latency_s: float
    prompt_tokens: int
    completion_tokens: int
    tokens_per_second: float
    success: bool
    error: str | None = None
    backend_metrics: dict = field(default_factory=dict)
    concurrent_users_level: int = 0
    run_id: str = ""
    gpu_type: str | None = None
    model_dtype: str | None = None
    gpu_metrics: dict = field(default_factory=dict)

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class AggregatedMetrics:
    scenario: str
    target_server: str
    target_model: str
    total_requests: int
    success_count: int
    error_count: int
    success_rate: float
    ttft_mean_s: float
    ttft_median_s: float
    ttft_p95_s: float
    tpot_mean_s: float
    e2e_mean_s: float
    e2e_p95_s: float
    tokens_per_second_mean: float
    total_tokens_per_second: float
    requests_per_second: float
    total_duration_s: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConversationMetrics:
    """Per-conversation quality metrics: KV cache, turn-to-turn latency, context growth."""

    scenario: str
    target_server: str
    target_model: str
    conversation: str
    ttft_by_turn: dict[int, float]  # turn index -> mean TTFT (s)
    e2e_by_turn: dict[int, float]  # turn index -> mean E2E latency (s)
    turn_to_turn_ratio: float | None  # mean(TTFT turn>0) / mean(TTFT turn=0)
    context_growth_factor: float | None  # mean(E2E last turn) / mean(E2E first turn)
    kv_cache_hit_rate_mean: float | None  # SGLang: cache_hit_rate averaged across requests
    kv_cache_usage_mean: float | None  # vLLM: gpu_cache_usage_perc averaged across requests

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def group_by_level(
    results: list[RequestMetrics],
) -> dict[tuple[str, str, int], list[RequestMetrics]]:
    """Group results by (target_server, target_model, concurrent_users_level)."""
    groups: dict[tuple[str, str, int], list[RequestMetrics]] = {}
    for r in results:
        groups.setdefault((r.target_server, r.target_model, r.concurrent_users_level), []).append(r)
    return groups


def is_ramp_run(results: list[RequestMetrics]) -> bool:
    """True if results contain more than one distinct non-zero concurrent_users_level."""
    levels = {r.concurrent_users_level for r in results if r.concurrent_users_level > 0}
    return len(levels) > 1


def group_by_target(
    results: list[RequestMetrics],
) -> dict[tuple[str, str], list[RequestMetrics]]:
    """Group results by (target_server, target_model)."""
    groups: dict[tuple[str, str], list[RequestMetrics]] = {}
    for r in results:
        groups.setdefault((r.target_server, r.target_model), []).append(r)
    return groups


def estimate_total_duration(results: list[RequestMetrics]) -> float:
    """Estimate benchmark wall-clock duration from request timestamps and E2E latencies.

    More accurate than max(e2e_latency) when requests ran concurrently.
    Falls back to 1.0 if results is empty.
    """
    if not results:
        return 1.0
    starts = [datetime.fromisoformat(r.timestamp_start).timestamp() for r in results]
    ends = [s + r.e2e_latency_s for s, r in zip(starts, results)]
    duration = max(ends) - min(starts)
    return duration if duration > 0 else 1.0


def aggregate(results: list[RequestMetrics], total_duration_s: float) -> AggregatedMetrics:
    if not results:
        raise ValueError("No results to aggregate")

    successful = [r for r in results if r.success]
    n = len(results)
    n_ok = len(successful)

    ttft_vals = [r.ttft_s for r in successful] or [0.0]
    tpot_vals = [r.tpot_s for r in successful] or [0.0]
    e2e_vals = [r.e2e_latency_s for r in successful] or [0.0]
    tps_vals = [r.tokens_per_second for r in successful] or [0.0]
    total_completion = sum(r.completion_tokens for r in successful)

    return AggregatedMetrics(
        scenario=results[0].scenario,
        target_server=results[0].target_server,
        target_model=results[0].target_model,
        total_requests=n,
        success_count=n_ok,
        error_count=n - n_ok,
        success_rate=n_ok / n if n else 0.0,
        ttft_mean_s=mean(ttft_vals),
        ttft_median_s=median(ttft_vals),
        ttft_p95_s=_p95(ttft_vals),
        tpot_mean_s=mean(tpot_vals),
        e2e_mean_s=mean(e2e_vals),
        e2e_p95_s=_p95(e2e_vals),
        tokens_per_second_mean=mean(tps_vals),
        total_tokens_per_second=total_completion / total_duration_s if total_duration_s else 0.0,
        requests_per_second=n_ok / total_duration_s if total_duration_s else 0.0,
        total_duration_s=total_duration_s,
    )


def aggregate_conversations(results: list[RequestMetrics]) -> list[ConversationMetrics]:
    """Group results by (server, model, conversation) and compute conversation-level metrics."""
    groups: dict[tuple[str, str, str], list[RequestMetrics]] = {}
    for r in results:
        key = (r.target_server, r.target_model, r.conversation)
        groups.setdefault(key, []).append(r)

    return [_compute_conversation_metrics(group) for group in groups.values()]


def _compute_conversation_metrics(results: list[RequestMetrics]) -> ConversationMetrics:
    successful = [r for r in results if r.success]
    turns = sorted({r.turn for r in successful})

    ttft_by_turn = {t: mean(r.ttft_s for r in successful if r.turn == t) for t in turns}
    e2e_by_turn = {t: mean(r.e2e_latency_s for r in successful if r.turn == t) for t in turns}

    turn_to_turn_ratio = _turn_to_turn_ratio(ttft_by_turn)
    context_growth_factor = _context_growth_factor(e2e_by_turn)
    kv_cache_hit_rate_mean = _extract_backend_metric(successful, ["cache_hit_rate"])
    kv_cache_usage_mean = _extract_backend_metric(
        successful, ["kv_cache_usage"]
    )

    r0 = results[0]
    return ConversationMetrics(
        scenario=r0.scenario,
        target_server=r0.target_server,
        target_model=r0.target_model,
        conversation=r0.conversation,
        ttft_by_turn=ttft_by_turn,
        e2e_by_turn=e2e_by_turn,
        turn_to_turn_ratio=turn_to_turn_ratio,
        context_growth_factor=context_growth_factor,
        kv_cache_hit_rate_mean=kv_cache_hit_rate_mean,
        kv_cache_usage_mean=kv_cache_usage_mean,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _p95(values: list[float]) -> float:
    if len(values) < 2:
        return values[0] if values else 0.0
    return quantiles(values, n=20)[18]


def _turn_to_turn_ratio(ttft_by_turn: dict[int, float]) -> float | None:
    """Ratio of mean TTFT for turns > 0 vs turn 0. < 1 means cache helps."""
    t0 = ttft_by_turn.get(0)
    later = [v for k, v in ttft_by_turn.items() if k > 0]
    if t0 is None or not later or t0 == 0:
        return None
    return mean(later) / t0


def _context_growth_factor(e2e_by_turn: dict[int, float]) -> float | None:
    """Ratio of last turn E2E vs first turn E2E. > 1 means latency grows with context."""
    if len(e2e_by_turn) < 2:
        return None
    first = e2e_by_turn[min(e2e_by_turn)]
    last = e2e_by_turn[max(e2e_by_turn)]
    return last / first if first else None


def _extract_backend_metric(results: list[RequestMetrics], keys: list[str]) -> float | None:
    """Average a backend_metrics field across requests, trying each key in order."""
    values: list[float] = []
    for r in results:
        for key in keys:
            val = r.backend_metrics.get(key)
            if val is not None:
                try:
                    values.append(float(val))
                except (TypeError, ValueError):
                    pass
                break
    return mean(values) if values else None
