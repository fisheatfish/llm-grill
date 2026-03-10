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


def aggregate(results: list[RequestMetrics], total_duration_s: float) -> AggregatedMetrics:
    if not results:
        raise ValueError("No results to aggregate")

    successful = [r for r in results if r.success]
    n = len(results)
    n_ok = len(successful)

    def _p95(values: list[float]) -> float:
        if len(values) < 2:
            return values[0] if values else 0.0
        return quantiles(values, n=20)[18]  # 95th percentile

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
