# ADR 001: Architecture CLI llm-bench

**Date:** 2026-03-10
**Status:** Accepted
**Deciders:** Team

---

## Context

A CLI tool is needed to benchmark LLM inference servers (vLLM, SGLang, llama.cpp via llama-server). The tool must:

- Run multi-turn conversation scenarios against multiple servers and models.
- Measure latency metrics (TTFT, TPOT, end-to-end latency), throughput, and reliability.
- Support concurrent users to simulate load.
- Output results in a format directly usable by pandas for analysis.
- Be installable as a Python package and usable both locally and against remote servers.

Key constraints:

- All target backends (vLLM, SGLang, llama.cpp, LiteLLM) expose an OpenAI-compatible REST API, but each also exposes backend-specific endpoints (metrics, health, model info).
- TTFT requires client-side measurement via streaming responses (SSE).
- The tool must remain extensible without architectural rewrites.
- Results must be streamable to disk during execution and immediately readable by pandas/Polars.

---

## Options considered

### Option A: Typer + httpx (async) + Pydantic v2 + Rich ✅

CLI built with Typer, using async httpx for HTTP with SSE streaming. Pydantic v2 validates scenario configs. Rich renders progress and results.

| | |
|---|---|
| Pros | Typer auto-generates help from type hints. httpx has native async and SSE support. Pydantic v2 is fast and produces clear validation errors. Rich is the standard for terminal UIs. |
| Cons | Typer adds a dependency layer over Click. Async streaming adds complexity to error handling. |
| Complexity | Medium |

### Option B: Click + aiohttp + dataclasses + Rich

CLI with Click, aiohttp for async HTTP, dataclasses for config validation.

| | |
|---|---|
| Pros | Click is battle-tested and stable. aiohttp is performant for high-concurrency. |
| Cons | Click requires more boilerplate than Typer. aiohttp SSE parsing requires manual implementation. dataclasses lack built-in validation, requiring manual checks. |
| Complexity | Medium |

### Option C: argparse + requests (sync) + dataclasses

Standard library CLI with synchronous HTTP requests.

| | |
|---|---|
| Pros | Zero extra CLI dependency. Simple sequential execution. |
| Cons | Sync HTTP cannot support concurrent users without threads. Blocking requests make accurate TTFT measurement harder. No built-in validation. argparse is verbose for complex CLIs. |
| Complexity | Low (initial), High (for concurrency features) |

---

## Scenario format: JSON vs YAML

### Option A: JSON

Scenarios described in `.json` files.

| | |
|---|---|
| Pros | No extra dependency. Universally supported. Directly loadable with stdlib `json`. |
| Cons | No comments. Verbose for nested structures. |
| Complexity | Trivial |

### Option B: YAML ✅

Scenarios described in `.yaml` files.

| | |
|---|---|
| Pros | Supports comments. More readable for humans. Easier to author multi-turn conversations. |
| Cons | Requires `pyyaml` or `ruamel.yaml`. YAML parsing has known security edge cases. Indentation errors are silent. |
| Complexity | Low |

---

## Client strategy: one generic client vs one per backend

### Option A: Single OpenAI-compatible client

One httpx-based client targeting the `/v1/chat/completions` endpoint, valid for all backends.

| | |
|---|---|
| Pros | No code duplication. Adding a new backend requires no client changes. Easier to maintain. |
| Cons | Cannot access backend-specific internal metrics (KV cache hit rate, queue depth) without separate Prometheus scraping. |
| Complexity | Low |

### Option B: One client per backend ✅

Dedicated client classes for vLLM, SGLang, llama.cpp, LiteLLM, sharing a common abstract base class and a shared httpx session.

| | |
|---|---|
| Pros | Can access vendor-specific APIs and internal metrics natively (KV cache hit rate, queue depth, model info). Enables richer KV cache comparison between vLLM and SGLang. |
| Cons | More code to maintain. Every new backend requires a new client implementation. |
| Complexity | High |

---

## Packaging: uv + hatchling vs setuptools

### Option A: uv + hatchling ✅

Modern packaging with `pyproject.toml`, `hatchling` as build backend, `uv` for dependency management.

| | |
|---|---|
| Pros | Fast dependency resolution. Single `pyproject.toml`. No `setup.py`. uv lockfile for reproducibility. |
| Cons | uv is newer; some CI environments may not have it pre-installed. |
| Complexity | Low |

### Option B: setuptools + pip

Traditional packaging with `setup.py` or `setup.cfg`.

| | |
|---|---|
| Pros | Universal support across all Python environments. |
| Cons | Slower dependency resolution. More configuration files. No integrated lockfile without pip-tools. |
| Complexity | Low |

---

## Output format: JSONL vs CSV vs Parquet

The output must be directly usable by pandas/Polars without post-processing.

### Option A: JSONL (JSON Lines) ✅

One JSON object per line, written incrementally as each request completes.

| | |
|---|---|
| Pros | Streamable during execution. Supports nested fields (conversation messages, per-turn metrics). `pd.read_json(lines=True)` and `pl.read_ndjson()`. Zero extra dependency. |
| Cons | Slightly more verbose than CSV. Not human-readable at a glance without tools. |
| Complexity | Trivial |

### Option B: CSV

Flat tabular format, one row per request.

| | |
|---|---|
| Pros | Universal compatibility (pandas, Excel, Google Sheets). Human-readable. |
| Cons | Cannot represent nested data (per-turn metrics require flattening). Not easily streamable mid-execution. |
| Complexity | Trivial |

### Option C: Parquet

Columnar binary format.

| | |
|---|---|
| Pros | Compressed, fast for large datasets, schema-typed. |
| Cons | Requires `pyarrow`. Not human-readable. Written only at the end, not streamable. Overkill for benchmark output volume. |
| Complexity | Low |

**Decision**: JSONL as primary output (written incrementally). CSV export available via `llm-bench report --format csv`. Parquet not implemented in v0.1.

---

## Decision

- **CLI framework**: Typer + Rich
- **HTTP client**: httpx async + SSE streaming
- **Config validation**: Pydantic v2
- **Scenario format**: YAML (with `pyyaml`)
- **Client strategy**: one abstract base class + one concrete client per backend (vLLM, SGLang, llama.cpp, LiteLLM)
- **Packaging**: uv + hatchling
- **Output format**: JSONL (primary, streamable) + CSV export on demand

---

## References

- [Typer documentation](https://typer.tiangolo.com/)
- [httpx async streaming](https://www.python-httpx.org/async/)
- [Pydantic v2 docs](https://docs.pydantic.dev/latest/)
- [OpenAI API reference - chat completions](https://platform.openai.com/docs/api-reference/chat)
- [uv documentation](https://docs.astral.sh/uv/)
- `starter.md` — project requirements
