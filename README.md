# llm-bench

CLI for benchmarking LLM inference servers: vLLM, SGLang, llama.cpp, LiteLLM.

Measures **TTFT**, **TPOT**, **end-to-end latency**, **throughput**, **success rate**, **KV cache quality metrics**, and **load ramp** (breaking-point detection) on multi-turn conversation scenarios.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![CI](https://github.com/fisheatfish/llm-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/fisheatfish/llm-bench/actions/workflows/ci.yml)

---

## Install

Requires **Python 3.11+** and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/fisheatfish/llm-bench.git
cd llm-bench
make install   # uv sync --all-extras
```

Verify:

```bash
llm-bench --version
```

---

## Quick start

**1. Check connectivity**

```bash
llm-bench ping scenarios/scaleway-devstral.yaml
```

**2. Run a benchmark**

```bash
llm-bench run scenarios/scaleway-devstral.yaml --output results.jsonl
```

After the run, tables are printed automatically:

- **Benchmark Summary** — latency, throughput, success rate per server/model
- **Conversation Quality Metrics** — KV cache hit rate, turn-to-turn latency ratio, context growth factor
- **Load Ramp Results** — (if `ramp_levels` is set) one row per (server, model, concurrency level)

**3. Generate a report from an existing results file**

```bash
# Terminal table (summary + conversation metrics)
llm-bench report results.jsonl

# JSON (both sections, pipeable)
llm-bench report results.jsonl --format json

# CSV (raw requests, pandas-ready)
llm-bench report results.jsonl --format csv --output summary.csv

# Hide conversation metrics table
llm-bench report results.jsonl --no-conversations
```

---

## Commands

| Command | Description |
|---|---|
| `llm-bench run <scenario>` | Run a benchmark, stream results to JSONL |
| `llm-bench ping <scenario>` | Test server connectivity |
| `llm-bench show-scenario <scenario>` | Validate and display a scenario |
| `llm-bench report <results.jsonl>` | Generate a report from a results file |

### `run` options

| Option | Default | Description |
|---|---|---|
| `--output / -o` | `results-<name>.jsonl` | Output file path |
| `--format / -f` | `jsonl` | `jsonl` or `csv` |
| `--quiet / -q` | off | Suppress progress and tables |

### `report` options

| Option | Default | Description |
|---|---|---|
| `--format / -f` | `table` | `table`, `json`, or `csv` |
| `--output / -o` | — | Output path for CSV format |
| `--no-conversations` | off | Hide the conversation metrics table |

### Global options

| Option | Description |
|---|---|
| `--verbose / -v` | Enable debug logging |
| `--version / -V` | Print version and exit |

---

## Scenario format (YAML)

```yaml
name: my-scenario
description: Optional description

backends:
  - name: gpu-vllm
    url: http://gpu-vllm:8000
    api_key: none                    # "none", a literal key, or ${ENV_VAR}
    type: vllm                       # vllm | sglang | llamacpp | litellm | openai
    timeout: 120.0

models:
  - name: devstral-small-2-24b
    max_tokens: 512
    temperature: 0.0

conversations:
  - name: multi-turn-debug
    turns:
      - role: system
        content: "You are an expert developer."
      - role: user
        content: "My FastAPI app returns 500 errors under load. What should I check?"
      - role: user
        content: "The DB connection pool is exhausted. How do I configure it in SQLAlchemy?"

targets:
  - backend: gpu-vllm
    model: devstral-small-2-24b
    conversation: multi-turn-debug

load:
  concurrent_users: 10
  iterations: 3
  ramp_up_seconds: 5.0
  think_time_seconds: 0.0
```

Each `role: user` turn triggers an inference request. Conversation history (including assistant responses) is carried forward, so the server sees a growing context.

### Load ramp

Add `ramp_levels` to sweep concurrency levels in a single run. When set, `concurrent_users` is ignored.

```yaml
load:
  iterations: 3
  ramp_levels: [1, 5, 10, 20, 50, 100]
  ramp_pause_seconds: 10.0   # pause between levels, default 10 s
  think_time_seconds: 0.0
```

Results are tagged with `concurrent_users_level` in the JSONL output and displayed in a **Load Ramp Results** table sorted by `(server, model, users)`.

---

## Metrics

### Latency & throughput

| Metric | Description |
|---|---|
| **TTFT** | Time to First Token — from request sent to first token received (client-side, includes network) |
| **TPOT** | Time Per Output Token — `(E2E - TTFT) / (completion_tokens - 1)` |
| **E2E latency** | Total time from request to last token |
| **tokens/s** | `completion_tokens / E2E latency` (per request) or total across all requests / benchmark duration |
| **success rate** | % of requests completed without error |

```
t0       → request sent
t_first  → first non-empty content chunk received
t_last   → stream ends ([DONE] or connection close)

TTFT   = t_first - t0
E2E    = t_last  - t0
TPOT   = (E2E - TTFT) / max(completion_tokens - 1, 1)
```

Measurement includes network round-trip. For cross-server comparisons, run from the same network location.

### Conversation quality (multi-turn)

Computed per `(server, model, conversation)` group:

| Metric | Description | Interpretation |
|---|---|---|
| **Turn-to-Turn Ratio** | `mean(TTFT turn > 0) / mean(TTFT turn 0)` | < 1 → KV cache reduces prefill time |
| **Context Growth Factor** | `mean(E2E last turn) / mean(E2E first turn)` | > 1 → latency increases with context |
| **KV Cache Hit Rate** | Prompt tokens served from cache | SGLang only (Prometheus) |
| **KV Cache Usage** | GPU KV cache capacity used | vLLM only (Prometheus) |

---

## Output format (JSONL)

One JSON object per request, written incrementally:

```json
{
  "scenario": "my-scenario",
  "target_server": "gpu-vllm",
  "target_model": "devstral-small-2-24b",
  "conversation": "multi-turn-debug",
  "turn": 1,
  "iteration": 0,
  "user_id": 3,
  "timestamp_start": "2026-03-10T14:00:00+00:00",
  "ttft_s": 0.142,
  "tpot_s": 0.018,
  "e2e_latency_s": 1.23,
  "prompt_tokens": 45,
  "completion_tokens": 64,
  "tokens_per_second": 52.0,
  "success": true,
  "error": null,
  "kv_cache_usage": 0.34,
  "requests_running": 8.0,
  "concurrent_users_level": 10
}
```

The file is valid even if the benchmark is interrupted — each line is a complete record.

**Read with pandas:**

```python
df = pd.read_json("results.jsonl", lines=True)
df.groupby("target_server")[["ttft_s", "e2e_latency_s", "tokens_per_second"]].mean()
```

**Read with polars:**

```python
df = pl.read_ndjson("results.jsonl")
df.group_by("target_server").agg(pl.col("ttft_s").mean())
```

---

## API keys

Use `${ENV_VAR}` syntax to read from environment variables at load time:

```yaml
backends:
  - name: gateway
    url: http://my-litellm-proxy:4000
    api_key: ${LITELLM_API_KEY}
    type: litellm
```

```bash
export LITELLM_API_KEY="sk-..."
llm-bench run scenarios/my-scenario.yaml
```

Never commit literal API keys in scenario files.

---

## LiteLLM gateway routing

When backends are behind a LiteLLM proxy, define one backend entry for the gateway and use **model aliases** to route:

```yaml
backends:
  - name: gateway
    url: http://my-litellm-proxy:4000
    api_key: ${LITELLM_API_KEY}
    type: litellm

models:
  - name: devstral-small-llama    # LiteLLM alias → llama.cpp
    max_tokens: 512
  - name: devstral-small-vllm     # LiteLLM alias → vLLM
    max_tokens: 512

targets:
  - backend: gateway
    model: devstral-small-llama
    conversation: short-code-question
  - backend: gateway
    model: devstral-small-vllm
    conversation: short-code-question
```

Aliases must match `model_name` values in LiteLLM's `config.yaml`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: llm_bench` | Run `make install` |
| `ValidationError` on scenario load | Run `llm-bench show-scenario file.yaml` for details |
| TTFT always < 1 ms | Server not streaming — check `stream: true` support |
| All requests `connection refused` | Run `llm-bench ping file.yaml` — check URL/port |
| `401 Unauthorized` | Set `api_key: ${MY_VAR}` and export the variable |
| `ping` times out on LiteLLM | LiteLLM `/health` does live inference — check gateway URL |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0 — see [LICENSE](LICENSE).
