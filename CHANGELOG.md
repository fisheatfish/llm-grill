# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.6.0] - 2026-03-17

### Added
- **GPU metrics collection** — `GpuMonitor` polls `nvidia-smi` over SSH at configurable intervals (default 2s), captures per-GPU snapshots (memory, utilization, temperature, power, PCIe gen/width, SM clock) and attaches nearest-timestamp match to each request result
- **`gpu_monitoring: true`** flag on `BackendConfig` — enables GPU metrics collection ; SSH host is extracted from `url` automatically (`ssh_host` remains as optional override for bastion/management network setups)
- **GPU metrics as top-level fields** in `RequestMetrics` — `gpu_mem_used_mib`, `gpu_mem_total_mib`, `gpu_util_pct`, `gpu_temp_c_max`, `gpu_power_w_total`, `gpu_mem_util_pct_avg`
- **SGLang Prometheus scraping** — `SglangClient` now fetches `/metrics` (Prometheus) for `cache_hit_rate` and `num_running_reqs` in addition to `/server_info` for KV cache usage — fixes previously always-null values
- **Multi-GPU support** — `GpuSnapshot` includes per-device details for multi-GPU setups
- **ADR 002** — documents why a custom tool was built vs existing alternatives (LLMPerf, GenAI-Perf, Locust, vLLM benchmark_serving.py)

### Changed
- **`RequestMetrics`, `AggregatedMetrics`, `ConversationMetrics` migrated from `@dataclass` to Pydantic `BaseModel`** — enables `model_dump()`, `model_dump_json()`, `model_validate_json()` ; `asdict()` calls replaced by `model_dump()`, `to_jsonl()` now uses `model_dump_json()`
- **`servers` + `backends` merged into `backends`** — single YAML section replaces the redundant `servers`/`backends` split ; `ServerConfig` removed, `BackendConfig` is now the unified config (carries `url`, `api_key`, `timeout`, `type`, `ssh_host`, `ssh_user`, `gpu_monitoring`)
- **`BenchmarkTarget` simplified** — `server` (required) + `backend` (optional) replaced by a single required `backend` field referencing `backends[].name`
- **Flat `RequestMetrics`** — `backend_metrics: dict` and `gpu_metrics: dict` removed ; all metrics are top-level typed fields (`kv_cache_usage`, `cache_hit_rate`, `requests_running`, `requests_waiting`, `gpu_*`) — `pd.read_json(lines=True)` gives columns directly
- **Canonical backend metric keys** — all clients now return the same keys (`kv_cache_usage`, `cache_hit_rate`, `requests_running`, `requests_waiting`) regardless of backend ; no more `vllm:` prefixes or `num_running_reqs` vs `num_requests_running` inconsistency

### Removed
- `ServerConfig` class — replaced by `BackendConfig`
- `BackendConfig.to_server_config()` bridge method — no longer needed
- `BackendConfig.gpu_type` and `BackendConfig.model_dtype` fields — unused after flat metrics refactor
- `ScenarioConfig.servers` field and `get_server()` method — replaced by `backends` and `get_backend()`
- `RequestMetrics.backend_metrics` and `RequestMetrics.gpu_metrics` nested dicts
- `_flatten()` helper in `report.py` — no more nested dicts to flatten
- `_extract_backend_metric()` in `metrics.py` — replaced by direct attribute access

### Fixed
- SGLang `cache_hit_rate` and `num_running_reqs` always null — now scraped from `/metrics` Prometheus endpoint
- `insitu-scaleway-devstral.yaml` targets referenced non-existent `server: gateway` — now correctly point to backend names

## [0.5.1] - 2026-03-11

### Fixed
- In ramp mode (`ramp_levels`), the **Conversation Quality Metrics** table (KV cache hit rate, turn-to-turn ratio, context growth factor) was not displayed after the Load Ramp Results table — a premature `return` in `_print_results` and a misplaced `else` in `report` hid the conversation metrics
- `llm-grill report --format table` command: same fix — the conversation table was inside the `else` block and thus ignored in ramp mode

## [0.5.0] - 2026-03-11

### Added
- **Load Ramp** (`ramp_levels`) — new optional field in `LoadConfig` to test multiple concurrency levels in a single run (`ramp_levels: [1, 5, 10, 20, 50]`)
- `ramp_pause_seconds` in `LoadConfig` — configurable pause between each level (default: 10s)
- `RampRunner` in `runner.py` — iterates levels sequentially, each `RequestMetrics` is tagged with `concurrent_users_level`
- `concurrent_users_level: int` on `RequestMetrics` (default `0` — backward-compatible with existing JSONL files)
- `group_by_level()` in `metrics.py` — groups results by `(server, model, concurrent_users_level)`
- `is_ramp_run()` in `metrics.py` — auto-detects whether a JSONL file contains multiple distinct levels
- `print_ramp_table()` in `report.py` — dedicated Rich table: Server | Model | Users | Requests | Success% | TTFT mean | TTFT p95 | E2E mean | E2E p95 | Tok/s total, sorted by (server, model, level)
- `llm-grill run` and `llm-grill report --format table` auto-detect ramp mode and display the dedicated table
- `llm-grill show-scenario` displays `ramp_levels` and `ramp_pause_seconds` when present

### Changed
- `BenchmarkRunner.run()` delegates to `RampRunner` when `ramp_levels` is set; classic path unchanged otherwise

## [0.4.2] - 2026-03-11

### Fixed
- `SglangClient.backend_metrics()`: `kvcache` now extracted recursively from the nested `/server_info` response (value was not at root level); normalized from 0-100 to 0-1 for consistency with vLLM
- `VllmClient.backend_metrics()`: metric renamed `vllm:gpu_cache_usage_perc` → `vllm:kv_cache_usage_perc` in vLLM >= 0.4 — both names are now supported (fallback to old name for backward compatibility)

### Added
- **KV cache hit rate for vLLM**: computed from Prometheus counters `prefix_cache_hits_total / prefix_cache_queries_total` — available without extra configuration if `enable_prefix_caching=True`
- **KV cache hit rate for SGLang**: extracted from `cache_hit_rate` in `/server_info` — requires `--enable-cache-report` at SGLang server startup
- `metrics.py`: `kv_cache_usage_mean` looks up `vllm:kv_cache_usage_perc`, `vllm:gpu_cache_usage_perc`, `kv_cache_usage` (SGLang) in order

## [0.4.1] - 2026-03-11

### Fixed
- `BaseClient.complete()`: `list index out of range` crash on SSE chunks with `choices: []` — llama-server sends this chunk at end of stream before `[DONE]`; the LiteLLM gateway silently filtered it, masking the bug in indirect access

## [0.4.0] - 2026-03-11

### Added
- `api_key` in `BackendConfig` supports `${VAR_NAME}` syntax — the environment variable is resolved at scenario load time; explicit error if missing
- `scenarios/scaleway-devstral.yaml` revised for LiteLLM gateway architecture: single gateway server, routing via model aliases (`devstral-small-llama`, `devstral-small-vllm`, `devstral-small-sglang`)
- `scenarios/insitu-scaleway-devstral.yaml` — template scenario for in-situ execution from the gateway server (direct backend access, KV cache metrics available)
- `README.md`: **API keys** section (`${VAR}` syntax) and **LiteLLM gateway routing** section (model aliases pattern)
- `DEVELOPER.md`: Troubleshooting entries for 401 Unauthorized and LiteLLM ping timeout

### Fixed
- `LiteLLMClient.health()` overrides `BaseClient.health()` to use `/health/liveliness` first — avoids the 10s timeout caused by `/health` which triggers inference calls to all configured models

### Changed
- `README.md`: simplified Install section (removed unavailable PyPI instructions, source-only installation)

## [0.3.0] - 2026-03-10

### Fixed (code review — MAJOR)
- `Message.role` is now typed as `Literal["system", "user", "assistant"]` — typos are caught at scenario validation
- `ScenarioConfig` validates that references in `targets` exist in `servers`, `models`, `conversations`
- `LoadConfig.ramp_up_seconds` and `think_time_seconds` reject negative values (`ge=0`)
- `t_last` is now always updated after the SSE stream ends, even without a `[DONE]` token
- Malformed SSE chunks silently ignored (`json.JSONDecodeError` caught)
- `total_duration` in `llm-grill report` correctly computed via `estimate_total_duration()` (timestamps + E2E) instead of `max(e2e_latency)`
- User iterations are now sequential — ramp-up is applied per user within its own coroutine
- `export_csv` uses the union of all keys (heterogeneous `backend_metrics` columns across servers)
- `JsonlWriter` opens the file in `__enter__`, not in `__init__`
- Version synchronized via hatchling `dynamic = ["version"]` — single source in `__init__.py`

### Added
- `estimate_total_duration()` in `metrics.py` — wall-clock duration from timestamps
- `group_by_target()` in `metrics.py` — shared helper, removes duplicated pattern
- `clients/prometheus.py` — shared Prometheus parser between vLLM and llama.cpp
- `--verbose / -v` on the CLI — enables debug logging (`logging.basicConfig`)
- `--version` displays `0.3.0`
- `tests/test_cli.py` — coverage of all 4 commands via `CliRunner`
- `tests/test_report.py` — coverage of `JsonlWriter`, `load_jsonl`, `export_csv`
- `src/llm_grill/py.typed` — PEP 561 marker (`Typing :: Typed` classifier honored)
- `pytest-cov` in dev dependencies
- `ruff format --check` in CI

### Changed
- Clients: `health()` implemented in `BaseClient` (10s timeout) — subclasses only override when needed
- Clients: unnecessary `__init__` removed from VllmClient, SglangClient, LiteLLMClient
- Clients: `Authorization` header omitted when `api_key` is `"none"`
- Structured logging added in `runner.py` and `clients/base.py`
- CLAUDE.md: method `chat_stream` → `complete`, CLI syntax corrected

## [0.2.0] - 2026-03-10

### Added
- `ConversationMetrics` dataclass — per-conversation quality metrics
- `aggregate_conversations()` — groups results by (server, model, conversation) and computes:
  - **Turn-to-Turn Latency Ratio** — mean(TTFT turn > 0) / mean(TTFT turn 0); < 1 indicates KV cache benefit
  - **Context Growth Factor** — mean(E2E last turn) / mean(E2E first turn); > 1 indicates latency increase with context
  - **KV Cache Hit Rate** — averaged from SGLang `/server_info` (`cache_hit_rate`)
  - **KV Cache Usage** — averaged from vLLM `/metrics` (`vllm:gpu_cache_usage_perc`)
- `print_conversation_table()` in `report.py` — Rich table for conversation metrics
- `llm-grill report --no-conversations` flag to hide conversation metrics table
- `--format json` now includes both `summary` and `conversations` sections
- Fixed invalid TOML syntax in `pyproject.toml` authors field

## [0.1.0] - 2026-03-10

### Added
- `llm-grill run` — benchmark a YAML scenario, write results to JSONL
- `llm-grill ping` — test server connectivity
- `llm-grill show-scenario` — validate and display a scenario file
- `llm-grill report` — generate summary table, JSON, or CSV from a results file
- Backend clients for vLLM, SGLang, llama.cpp, and LiteLLM
- Client-side TTFT, TPOT, and E2E latency measurement via SSE streaming
- JSONL output format (streamable, pandas/Polars compatible)
- CSV export via `--format csv` or `llm-grill report --format csv`
- YAML scenario format with multi-turn conversations, concurrent users, and ramp-up
- Example scenario for Scaleway infrastructure (Devstral-Small-2-24B, 3 backends)
- Prometheus scraping for vLLM (`/metrics`) and SGLang (`/server_info`)
