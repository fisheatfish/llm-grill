"""JSONL writer, CSV export, and Rich table rendering."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from llm_bench.metrics import (
    AggregatedMetrics,
    ConversationMetrics,
    RequestMetrics,
    aggregate,
    estimate_total_duration,
    group_by_level,
)

console = Console()


class JsonlWriter:
    """Incrementally writes RequestMetrics to a JSONL file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: object = None

    def __enter__(self) -> JsonlWriter:
        self._fh = self.path.open("w", encoding="utf-8")
        return self

    def __exit__(self, *_: object) -> None:
        if self._fh is not None:
            self._fh.close()  # type: ignore[union-attr]
            self._fh = None

    def write(self, m: RequestMetrics) -> None:
        if self._fh is None:
            raise RuntimeError("JsonlWriter must be used as a context manager")
        self._fh.write(m.to_jsonl() + "\n")  # type: ignore[union-attr]
        self._fh.flush()  # type: ignore[union-attr]


def load_jsonl(path: Path) -> list[RequestMetrics]:
    """Read a JSONL results file back into RequestMetrics objects."""
    results = []
    for line in path.read_text().splitlines():
        if line.strip():
            results.append(RequestMetrics.model_validate_json(line))
    return results


def export_csv(results: list[RequestMetrics], path: Path) -> None:
    """Export results to CSV."""
    if not results:
        return
    rows = [r.model_dump() for r in results]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), restval="")
        writer.writeheader()
        writer.writerows(rows)


def print_summary_table(aggregations: list[AggregatedMetrics]) -> None:
    """Render a Rich summary table to the terminal."""
    table = Table(title="Benchmark Summary", show_lines=True)
    table.add_column("Server", style="cyan")
    table.add_column("Model", style="magenta")
    table.add_column("Requests", justify="right")
    table.add_column("Success %", justify="right")
    table.add_column("TTFT mean", justify="right")
    table.add_column("TTFT p95", justify="right")
    table.add_column("TPOT mean", justify="right")
    table.add_column("E2E mean", justify="right")
    table.add_column("Tok/s total", justify="right")

    # Check if any results have GPU data (passed via extra_data)
    has_gpu = getattr(print_summary_table, "_has_gpu", False)
    if has_gpu:
        table.add_column("GPU %", justify="right")

    for a in aggregations:
        row = [
            a.target_server,
            a.target_model,
            str(a.total_requests),
            f"{a.success_rate * 100:.1f}%",
            f"{a.ttft_mean_s * 1000:.0f} ms",
            f"{a.ttft_p95_s * 1000:.0f} ms",
            f"{a.tpot_mean_s * 1000:.0f} ms",
            f"{a.e2e_mean_s * 1000:.0f} ms",
            f"{a.total_tokens_per_second:.1f}",
        ]
        table.add_row(*row)

    console.print(table)


def print_conversation_table(conv_metrics: list[ConversationMetrics]) -> None:
    """Render a Rich table for conversation-level KV cache and latency metrics."""
    table = Table(title="Conversation Quality Metrics", show_lines=True)
    table.add_column("Server", style="cyan")
    table.add_column("Conversation", style="yellow")
    table.add_column("Turn→Turn ratio", justify="right")
    table.add_column("Context growth", justify="right")
    table.add_column("KV cache hit %", justify="right")
    table.add_column("KV cache usage %", justify="right")
    table.add_column("TTFT by turn (ms)", justify="left")

    for c in conv_metrics:
        ratio = f"{c.turn_to_turn_ratio:.2f}" if c.turn_to_turn_ratio is not None else "—"
        growth = f"{c.context_growth_factor:.2f}x" if c.context_growth_factor is not None else "—"
        hit = (
            f"{c.kv_cache_hit_rate_mean * 100:.1f}%"
            if c.kv_cache_hit_rate_mean is not None
            else "—"
        )
        usage = f"{c.kv_cache_usage_mean * 100:.1f}%" if c.kv_cache_usage_mean is not None else "—"
        ttft_turns = "  ".join(f"T{t}={v * 1000:.0f}" for t, v in sorted(c.ttft_by_turn.items()))
        table.add_row(
            c.target_server,
            c.conversation,
            ratio,
            growth,
            hit,
            usage,
            ttft_turns,
        )

    console.print(table)


def print_ramp_table(results: list[RequestMetrics]) -> None:
    """Render a Rich table for load ramp results, one row per (server, model, level)."""
    table = Table(title="Load Ramp Results", show_lines=True)
    table.add_column("Server", style="cyan")
    table.add_column("Model", style="magenta")
    table.add_column("Users", justify="right")
    table.add_column("Requests", justify="right")
    table.add_column("Success %", justify="right")
    table.add_column("TTFT mean", justify="right")
    table.add_column("TTFT p95", justify="right")
    table.add_column("E2E mean", justify="right")
    table.add_column("E2E p95", justify="right")
    table.add_column("Tok/s total", justify="right")

    groups = group_by_level(results)
    for key in sorted(groups.keys()):
        server, model, level = key
        group = groups[key]
        duration = estimate_total_duration(group)
        a = aggregate(group, duration)
        table.add_row(
            server,
            model,
            str(level),
            str(a.total_requests),
            f"{a.success_rate * 100:.1f}%",
            f"{a.ttft_mean_s * 1000:.0f} ms",
            f"{a.ttft_p95_s * 1000:.0f} ms",
            f"{a.e2e_mean_s * 1000:.0f} ms",
            f"{a.e2e_p95_s * 1000:.0f} ms",
            f"{a.total_tokens_per_second:.1f}",
        )

    console.print(table)


def print_aggregated_json(
    aggregations: list[AggregatedMetrics],
    conv_metrics: list[ConversationMetrics] | None = None,
) -> None:
    data: dict = {"summary": [a.to_dict() for a in aggregations]}
    if conv_metrics:
        data["conversations"] = [c.to_dict() for c in conv_metrics]
    console.print_json(json.dumps(data))
