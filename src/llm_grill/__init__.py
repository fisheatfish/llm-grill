"""llm-grill: CLI for benchmarking LLM inference servers."""

from __future__ import annotations

from llm_grill.metrics import (
    AggregatedMetrics,
    ConversationMetrics,
    RequestMetrics,
    aggregate_conversations,
    estimate_total_duration,
    group_by_target,
)
from llm_grill.metrics import (
    aggregate as _aggregate,
)

__version__ = "0.1.3"

__all__ = [
    "__version__",
    "aggregate",
    "aggregate_conversations",
    "AggregatedMetrics",
    "ConversationMetrics",
    "RequestMetrics",
]


def aggregate(jsonl: str) -> list[AggregatedMetrics]:
    """Parse JSONL benchmark output and return aggregated metrics per (server, model).

    Args:
        jsonl: Multi-line string in llm-grill JSONL format (one RequestMetrics per line).

    Returns:
        One AggregatedMetrics per distinct (target_server, target_model) combination.

    Raises:
        ValueError: If jsonl contains no valid results.
    """
    results = [
        RequestMetrics.model_validate_json(line) for line in jsonl.splitlines() if line.strip()
    ]
    if not results:
        raise ValueError("No results found in jsonl input")
    groups = group_by_target(results)
    return [_aggregate(group, estimate_total_duration(group)) for group in groups.values()]
