# CLAUDE.md — llm-grill

Source of truth for build and development. Optimized for Claude Code.

---

## Project

Python CLI benchmark for LLM inference servers.
Measures TTFT, TPOT, E2E latency, throughput, success rate, KV cache effectiveness (turn-to-turn ratio, hit rate, usage), and GPU metrics (utilization, memory, power) via SSH across multi-conversation multi-server scenarios.

**Architecture decisions**: `docs/adr/` (001: custom tool rationale, 002: architecture)
**Implementation plan**: `docs/plan/implementation-plan.md` (not versioned)

---

## Stack

| Role | Lib | Min version |
|---|---|---|
| CLI | typer | 0.12 |
| Display | rich | 13 |
| Config validation | pydantic | 2 |
| Async HTTP + SSE | httpx | 0.27 |
| Concurrency | anyio | 4 |
| Scenarios | pyyaml | 6 |
| Tests | pytest + pytest-asyncio + respx | 8 / 0.23 / 0.21 |
| Packaging | uv + hatchling | — |

---

## Structure

```
src/llm_grill/
├── __init__.py       # __version__
├── cli.py            # Typer app — commands: run, ping, show-scenario, report
├── config.py         # Pydantic: BackendConfig, BenchmarkTarget, ModelConfig, ScenarioConfig, ConversationTemplate
├── scenario.py       # YAML scenario loading and validation
├── clients/
│   ├── __init__.py   # Client factory — get_client() returns the right subclass per backend
│   ├── base.py       # Abstract class BaseClient (methods: complete, health, backend_metrics)
│   ├── vllm.py       # vLLM client (Prometheus /metrics endpoint)
│   ├── sglang.py     # SGLang client (Prometheus /metrics endpoint)
│   ├── llamacpp.py   # llama.cpp / llama-server client
│   ├── litellm.py    # LiteLLM client (gateway)
│   └── prometheus.py # Shared Prometheus scraping helper
├── metrics.py        # dataclass RequestMetrics + AggregatedMetrics + aggregation (p50/p95/p99)
├── runner.py         # Orchestration: anyio concurrency, conversation turn management
├── gpu_monitor.py    # GPU metrics collection via SSH
└── report.py         # Incremental JSONL writing + CSV export + Rich table

scenarios/            # YAML scenario files
tests/                # pytest — one file per src module
docs/adr/             # Versioned ADRs
docs/plan/            # Unversioned plans (.gitignore)
```

> **Note — `openai` backend**: The `openai` backend type reuses the vLLM client, since both
> speak the same OpenAI-compatible API. No dedicated `clients/openai.py` is needed.

---

## Make commands

```bash
make install      # uv sync --all-extras
make test         # pytest
make test-cov     # pytest with coverage
make lint         # ruff check --fix + ruff format (whole repo)
make check        # ruff check without fixing (CI-style)
make build        # uv build
```

---

## CLI commands

```bash
llm-grill run scenarios/foo.yaml [--output results.jsonl] [--format jsonl|csv] [--verbose] [--quiet]
llm-grill ping scenarios/foo.yaml
llm-grill show-scenario scenarios/foo.yaml
llm-grill report results.jsonl [--format table|json|csv] [--output out.csv] [--no-conversations]
```

---

## Scenario format (YAML)

```yaml
name: string                        # scenario identifier
description: string                 # optional
backends:
  - name: string
    url: http://host:port           # base URL (without /v1)
    type: vllm|sglang|llamacpp|litellm|openai
    api_key: string                 # "none" | literal key | ${ENV_VAR}
    timeout: float                  # seconds, default 120 — applies per HTTP request
    gpu_monitoring: bool            # default false — enable GPU metrics via SSH
    ssh_host: string                # optional — for GPU metrics collection
    ssh_user: string                # default "root"
models:
  - name: string                    # exact model_id as expected by the server
    max_tokens: int                 # default 512
    temperature: float              # default 0.0
    top_p: float                    # default 1.0
conversations:
  - name: string
    description: string
    turns:
      - role: system|user|assistant
        content: string
targets:                            # combinations to benchmark
  - backend: string                 # must match backends[].name
    model: string                   # must match models[].name
    conversation: string            # must match conversations[].name
load:
  concurrent_users: int             # default 1
  iterations: int                   # default 1 (per user)
  ramp_up_seconds: float            # default 0.0 — linear spread: user N starts at
                                    #   (ramp_up_seconds / concurrent_users) * N seconds
  think_time_seconds: float         # pause between turns, default 0.0
  ramp_levels: [int, ...]          # optional — list of concurrency levels to test sequentially
  ramp_pause_seconds: float         # pause between ramp levels, default 10.0
```

---

## JSONL output format

One JSON line per completed request:

```json
{
  "scenario": "string",
  "target_server": "string",
  "target_model": "string",
  "conversation": "string",
  "turn": 0,
  "iteration": 0,
  "user_id": 0,
  "timestamp_start": "ISO8601",
  "ttft_s": 0.0,
  "tpot_s": 0.0,
  "e2e_latency_s": 0.0,
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "tokens_per_second": 0.0,
  "success": true,
  "error": null,
  "concurrent_users_level": 0,
  "run_id": "string",
  "kv_cache_usage": null,
  "cache_hit_rate": null,
  "requests_running": null,
  "requests_waiting": null,
  "gpu_mem_used_mib": null,
  "gpu_util_pct": null,
  "gpu_temp_c_max": null,
  "gpu_power_w_total": null
}
```

Reading with pandas: `pd.read_json("results.jsonl", lines=True)`
Reading with polars: `pl.read_ndjson("results.jsonl")`

### Aggregated metrics (via `report` command)

The report aggregates per (server, model) with: mean, median, **p95** for TTFT and E2E,
plus total tokens/s, requests/s, and success rate. Conversation-level metrics include
turn-to-turn TTFT ratio (KV cache effectiveness) and context growth factor.

---

## Backend clients

Each client inherits from `BaseClient` (ABC) and implements:

- `complete(messages, model_config) -> StreamResult` — SSE stream, measures TTFT/TPOT/E2E
- `health() -> bool` — connectivity check (short timeout: 10s)
- `backend_metrics() -> dict` — vendor-specific metrics (Prometheus scrape for vLLM/SGLang)

Client-side TTFT measurement:
- `t0` = just before sending the HTTP request
- `t_first` = reception of the first non-empty SSE chunk
- `t_last` = end of stream (after `[DONE]` or stream close)
- TTFT = `t_first - t0`
- E2E = `t_last - t0`
- TPOT = `(E2E - TTFT) / max(completion_tokens - 1, 1)`

The server-level `timeout` (default 120s) applies to each HTTP request (i.e. per conversation turn), not to the whole conversation.

---

## Code conventions

- Short classes (< 80 lines). Single responsibility per class.
- Async everywhere in clients and runner (`anyio.create_task_group` for concurrency).
- No direct print — `rich.console.Console` only.
- Input validation via Pydantic. No defensive validation in the core.
- `from __future__ import annotations` in all modules.
- Grouped imports: stdlib → third-party → local.

---

## Tests

```
tests/
├── conftest.py          # fixtures: mock ScenarioConfig, respx mock server
├── test_cli.py          # Typer commands via CliRunner
├── test_config.py       # Pydantic validation, YAML loading
├── test_metrics.py      # TTFT/TPOT/aggregation calculations
├── test_clients.py      # clients with respx (SSE mock)
├── test_gpu_monitor.py  # GPU metrics collection
├── test_report.py       # CSV export, Rich tables
└── test_runner.py       # orchestration, concurrency
```

Target coverage: > 80% on `src/llm_grill/`.

---

## Files not to version

Add to `.gitignore`:
- `docs/plan/`
- `results/`
- `*.jsonl`
- `.env`
