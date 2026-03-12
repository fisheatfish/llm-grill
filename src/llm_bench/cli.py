"""CLI entry point — Typer app with run, ping, show-scenario, report commands."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import anyio
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from llm_bench import __version__
from llm_bench.clients import get_client
from llm_bench.metrics import (
    RequestMetrics,
    aggregate,
    aggregate_conversations,
    estimate_total_duration,
    group_by_target,
    is_ramp_run,
)
from llm_bench.report import (
    JsonlWriter,
    console,
    export_csv,
    load_jsonl,
    print_aggregated_json,
    print_conversation_table,
    print_ramp_table,
    print_summary_table,
)
from llm_bench.runner import BenchmarkRunner
from llm_bench.scenario import load_scenario

app = typer.Typer(
    name="llm-bench",
    help="Benchmark LLM inference servers (vLLM, SGLang, llama.cpp, LiteLLM).",
    add_completion=False,
)
err_console = Console(stderr=True, style="bold red")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"llm-bench {__version__}")
        raise typer.Exit()


def verbose_callback(value: bool) -> None:
    if value:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(levelname)s %(name)s — %(message)s",
        )


@app.callback()
def main(
    _version: Annotated[
        bool | None,
        typer.Option("--version", "-V", callback=version_callback, is_eager=True),
    ] = None,
    _verbose: Annotated[
        bool | None,
        typer.Option(
            "--verbose", "-v", callback=verbose_callback, is_eager=True, help="Enable debug logging"
        ),
    ] = None,
) -> None:
    pass


# ---------------------------------------------------------------------------
# llm-bench run
# ---------------------------------------------------------------------------


@app.command()
def run(
    scenario: Annotated[Path, typer.Argument(help="Path to YAML scenario file")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output JSONL file")] = None,
    format: Annotated[
        str, typer.Option("--format", "-f", help="Output format: jsonl | csv")
    ] = "jsonl",
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
) -> None:
    """Run a benchmark scenario and write results to a JSONL file."""
    if not scenario.exists():
        err_console.print(f"Scenario file not found: {scenario}")
        raise typer.Exit(1)

    try:
        cfg = load_scenario(scenario)
    except Exception as exc:
        err_console.print(f"Invalid scenario: {exc}")
        raise typer.Exit(1)

    output_path = output or Path(f"results-{cfg.name}.jsonl")
    all_results: list[RequestMetrics] = []

    with JsonlWriter(output_path) as writer:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            disable=quiet,
        ) as progress:
            task_id = progress.add_task(f"Running [cyan]{cfg.name}[/]…", total=None)

            def on_result(m: RequestMetrics) -> None:
                writer.write(m)
                all_results.append(m)
                status = "[green]OK[/]" if m.success else "[red]ERR[/]"
                progress.update(
                    task_id,
                    description=(
                        f"{status} {m.target_server} | turn={m.turn} TTFT={m.ttft_s * 1000:.0f}ms"
                    ),
                )

            bench = BenchmarkRunner(cfg, on_result)
            _, total_duration = anyio.run(bench.run)

    _print_results(all_results, total_duration, quiet)

    if format == "csv":
        csv_path = output_path.with_suffix(".csv")
        export_csv(all_results, csv_path)
        if not quiet:
            console.print(f"[dim]CSV exported → {csv_path}[/]")
    elif not quiet:
        console.print(f"[dim]JSONL saved → {output_path}[/]")


# ---------------------------------------------------------------------------
# llm-bench ping
# ---------------------------------------------------------------------------


@app.command()
def ping(
    scenario: Annotated[Path, typer.Argument(help="Path to YAML scenario file")],
) -> None:
    """Test connectivity to all servers defined in a scenario."""
    if not scenario.exists():
        err_console.print(f"Scenario file not found: {scenario}")
        raise typer.Exit(1)

    cfg = load_scenario(scenario)
    console.rule("[bold]Connectivity check[/]")

    async def _check_all() -> None:
        for server in cfg.servers:
            async with get_client(server) as client:
                ok = await client.health()
            icon = "[green]✓[/]" if ok else "[red]✗[/]"
            console.print(f"  {icon}  {server.name} ({server.backend.value}) — {server.url}")

    anyio.run(_check_all)


# ---------------------------------------------------------------------------
# llm-bench show-scenario
# ---------------------------------------------------------------------------


@app.command(name="show-scenario")
def show_scenario(
    scenario: Annotated[Path, typer.Argument(help="Path to YAML scenario file")],
) -> None:
    """Display and validate a scenario file."""
    if not scenario.exists():
        err_console.print(f"Scenario file not found: {scenario}")
        raise typer.Exit(1)

    try:
        cfg = load_scenario(scenario)
    except Exception as exc:
        err_console.print(f"Validation error: {exc}")
        raise typer.Exit(1)

    console.rule(f"[bold cyan]{cfg.name}[/]")
    if cfg.description:
        console.print(f"[dim]{cfg.description}[/]\n")

    console.print("[bold]Servers[/]")
    for s in cfg.servers:
        console.print(f"  • [cyan]{s.name}[/] ({s.backend.value}) → {s.url}")

    console.print("\n[bold]Models[/]")
    for m in cfg.models:
        console.print(f"  • [magenta]{m.name}[/]  max_tokens={m.max_tokens}  temp={m.temperature}")

    console.print("\n[bold]Conversations[/]")
    for c in cfg.conversations:
        console.print(f"  • [yellow]{c.name}[/]  ({len(c.turns)} turns)")

    console.print("\n[bold]Targets[/]")
    for t in cfg.targets:
        console.print(f"  • {t.server} × {t.model} × {t.conversation}")

    load = cfg.load
    ramp_info = (
        f"  ramp_levels={load.ramp_levels}  pause={load.ramp_pause_seconds}s"
        if load.ramp_levels
        else f"  ramp={load.ramp_up_seconds}s"
    )
    console.print(
        f"\n[bold]Load[/]  concurrent={load.concurrent_users}  "
        f"iterations={load.iterations}{ramp_info}"
    )


# ---------------------------------------------------------------------------
# llm-bench report
# ---------------------------------------------------------------------------


@app.command()
def report(
    results_file: Annotated[Path, typer.Argument(help="JSONL results file")],
    format: Annotated[
        str, typer.Option("--format", "-f", help="Output format: table | json | csv")
    ] = "table",
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    no_conversations: Annotated[
        bool, typer.Option("--no-conversations", help="Hide conversation metrics table")
    ] = False,
) -> None:
    """Generate a report from a JSONL results file."""
    if not results_file.exists():
        err_console.print(f"Results file not found: {results_file}")
        raise typer.Exit(1)

    results = load_jsonl(results_file)
    if not results:
        err_console.print("Results file is empty.")
        raise typer.Exit(1)

    groups = group_by_target(results)
    total_duration = estimate_total_duration(results)
    aggregations = [aggregate(v, total_duration) for v in groups.values()]
    conv_metrics = aggregate_conversations(results)

    if format == "table":
        if is_ramp_run(results):
            print_ramp_table(results)
        else:
            print_summary_table(aggregations)
        if not no_conversations and conv_metrics:
            print_conversation_table(conv_metrics)
    elif format == "json":
        print_aggregated_json(aggregations, conv_metrics)
    elif format == "csv":
        out = output or results_file.with_suffix(".summary.csv")
        export_csv(results, out)
        console.print(f"[dim]CSV exported → {out}[/]")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _print_results(results: list[RequestMetrics], total_duration: float, quiet: bool) -> None:
    if quiet or not results:
        return
    if is_ramp_run(results):
        print_ramp_table(results)
    else:
        aggregations = [aggregate(v, total_duration) for v in group_by_target(results).values()]
        print_summary_table(aggregations)
    conv_metrics = aggregate_conversations(results)
    if conv_metrics:
        print_conversation_table(conv_metrics)
