# Developer Guide — llm-bench

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

---

## Setup

```bash
git clone <repo>
cd llm-bench
make install   # uv sync --all-extras
```

---

## Project structure

```
src/llm_bench/
├── cli.py           # Typer commands: run, ping, show-scenario, report
├── config.py        # Pydantic schemas
├── scenario.py      # YAML loader
├── clients/
│   ├── base.py      # Abstract BaseClient + SSE streaming + TTFT measurement
│   ├── vllm.py      # vLLM (/metrics Prometheus)
│   ├── sglang.py    # SGLang (/get_server_info)
│   ├── llamacpp.py  # llama-server (/health, /metrics)
│   ├── litellm.py   # LiteLLM proxy
│   └── __init__.py  # get_client() factory
├── metrics.py       # RequestMetrics dataclass + aggregate()
├── runner.py        # ConversationRunner, TargetRunner, BenchmarkRunner
└── report.py        # JsonlWriter, export_csv, Rich tables
```

---

## Running tests

```bash
make test          # run all tests
make test-cov      # with coverage
uv run pytest tests/test_clients.py -v   # specific file
```

---

## Adding a new backend

1. Create `src/llm_bench/clients/mybackend.py` inheriting `BaseClient`.
2. Implement `health()` and `backend_metrics()`.
3. Add the new enum value in `config.py` → `Backend`.
4. Register it in `clients/__init__.py` → `_REGISTRY`.
5. Add tests in `tests/test_clients.py`.

The `complete()` method in `BaseClient` handles SSE streaming generically and should not need overriding unless the backend deviates from the OpenAI SSE format.

---

## TTFT measurement

`BaseClient.complete()` measures timing around the SSE stream:

```
t0       → request sent
t_first  → first non-empty content chunk received
t_last   → "data: [DONE]" received

TTFT   = t_first - t0
E2E    = t_last  - t0
TPOT   = (E2E - TTFT) / max(completion_tokens - 1, 1)
tok/s  = completion_tokens / E2E
```

Measurement is client-side and includes network round-trip. For cross-server comparisons, run from the same network location.

---

## Output format

Results are written as JSONL (one JSON object per line) to the output file during execution. This means partial results are available even if a benchmark is interrupted.

Schema: see `README.md` or `CLAUDE.md`.

---

## Linting and formatting

```bash
make lint   # ruff check
make fmt    # ruff format
```

---

## Building the package

```bash
make build
# output: dist/llm_bench-0.1.0-py3-none-any.whl
```

Install from wheel:

```bash
uv tool install dist/llm_bench-0.1.0-py3-none-any.whl
```

---

## Publishing to PyPI

```bash
uv build
uv publish --token $PYPI_TOKEN
```

---

## Troubleshooting

**`ModuleNotFoundError: llm_bench`**
The package is not installed. Run `make install` or `uv sync`.

**`ValidationError` on scenario load**
Run `llm-bench show-scenario your-file.yaml` for a detailed validation error. Common causes: missing required fields (`servers`, `models`, `conversations`, `targets`), invalid URL format, or a conversation with no `user` turn.

**TTFT is always very low (< 1 ms)**
The server is likely returning the full response at once (not streaming). Check that `stream: true` is supported and enabled on your server. Some LiteLLM proxy configs disable streaming.

**All requests fail with `connection refused`**
Run `llm-bench ping your-file.yaml` to diagnose per-server connectivity. Check URL and port in the scenario YAML.

**`anyio` task group errors with partial results**
If one concurrent user fails with an unhandled exception, anyio cancels the whole group. Exceptions from `client.complete()` are caught in `ConversationRunner.run()` and recorded as failed metrics — they should not propagate. If they do, file a bug with the traceback.

**`respx` mock not intercepting in tests**
Ensure the `@respx.mock` decorator is on the test method (not the class), and that the URL in the mock matches exactly the base URL in `ServerConfig` (no trailing slash).
