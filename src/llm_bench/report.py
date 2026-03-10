"""JSONL writer, CSV export, and Rich table rendering."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from rich.console import Console
from rich.table import Table

from llm_bench.metrics import AggregatedMetrics, ConversationMetrics, RequestMetrics

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
            results.append(RequestMetrics(**json.loads(line)))
    return results


def export_csv(results: list[RequestMetrics], path: Path) -> None:
    """Export results to CSV (flattens backend_metrics).

    Uses the union of all row keys as columns so that heterogeneous
    backend_metrics across servers don't silently drop values.
    """
    if not results:
        return
    rows = [_flatten(asdict(r)) for r in results]
    all_keys: dict[str, None] = {}  # ordered set via insertion order
    for row in rows:
        all_keys.update(dict.fromkeys(row.keys()))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_keys), restval="")
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

    for a in aggregations:
        table.add_row(
            a.target_server,
            a.target_model,
            str(a.total_requests),
            f"{a.success_rate * 100:.1f}%",
            f"{a.ttft_mean_s * 1000:.0f} ms",
            f"{a.ttft_p95_s * 1000:.0f} ms",
            f"{a.tpot_mean_s * 1000:.0f} ms",
            f"{a.e2e_mean_s * 1000:.0f} ms",
            f"{a.total_tokens_per_second:.1f}",
        )

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


def print_aggregated_json(
    aggregations: list[AggregatedMetrics],
    conv_metrics: list[ConversationMetrics] | None = None,
) -> None:
    data: dict = {"summary": [a.to_dict() for a in aggregations]}
    if conv_metrics:
        data["conversations"] = [c.to_dict() for c in conv_metrics]
    console.print_json(json.dumps(data))


def _flatten(d: dict, prefix: str = "") -> dict:
    """Recursively flatten nested dicts for CSV export."""
    result: dict = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten(v, prefix=f"{key}."))
        else:
            result[key] = v
    return result
