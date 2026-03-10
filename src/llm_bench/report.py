"""JSONL writer, CSV export, and Rich table rendering."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from rich.console import Console
from rich.table import Table

from llm_bench.metrics import AggregatedMetrics, RequestMetrics

console = Console()


class JsonlWriter:
    """Incrementally writes RequestMetrics to a JSONL file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = path.open("w", encoding="utf-8")

    def write(self, m: RequestMetrics) -> None:
        self._fh.write(m.to_jsonl() + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> JsonlWriter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def load_jsonl(path: Path) -> list[RequestMetrics]:
    """Read a JSONL results file back into RequestMetrics objects."""
    results = []
    for line in path.read_text().splitlines():
        if line.strip():
            results.append(RequestMetrics(**json.loads(line)))
    return results


def export_csv(results: list[RequestMetrics], path: Path) -> None:
    """Export results to CSV (flattens backend_metrics)."""
    if not results:
        return
    rows = [_flatten(asdict(r)) for r in results]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
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


def print_aggregated_json(aggregations: list[AggregatedMetrics]) -> None:
    data = [a.to_dict() for a in aggregations]
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
