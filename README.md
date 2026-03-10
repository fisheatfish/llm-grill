# llm-bench

CLI for benchmarking LLM inference servers: vLLM, SGLang, llama.cpp, LiteLLM.

Measures **TTFT**, **TPOT**, **end-to-end latency**, **throughput**, **success rate**, and **KV cache quality metrics** on multi-turn conversation scenarios.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![CI](https://github.com/your-org/llm-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/llm-bench/actions/workflows/ci.yml)

---

## Install

Requires **Python 3.11+**.

### From PyPI (recommended)

```bash
pip install llm-bench
```

With [uv](https://docs.astral.sh/uv/) (faster):

```bash
# as a global tool
uv tool install llm-bench

# or inside a project
uv add llm-bench
```

### From source

```bash
git clone https://github.com/your-org/llm-bench.git
cd llm-bench
pip install -e .
```

With uv:

```bash
git clone https://github.com/your-org/llm-bench.git
cd llm-bench
uv sync
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### Verify installation

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

After the run, two tables are printed automatically:

- **Benchmark Summary** — latency, throughput, success rate per server/model
- **Conversation Quality Metrics** — KV cache hit rate, turn-to-turn latency ratio, context growth factor

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

---

## Metrics

### Latency & throughput

| Metric | Description |
|---|---|
| **TTFT** | Time to First Token — from request sent to first token received (client-side, includes network) |
| **TPOT** | Time Per Output Token — `(E2E - TTFT) / (completion_tokens - 1)` |
| **E2E latency** | Total time from request to last token |
| **tokens/s per request** | `completion_tokens / E2E latency` |
| **total tokens/s** | Total completion tokens across all requests / total benchmark duration |
| **success rate** | % of requests completed without error |

### Conversation quality (multi-turn)

These metrics are computed per `(server, model, conversation)` group and displayed in a separate table.

| Metric | Description | Interpretation |
|---|---|---|
| **Turn-to-Turn Ratio** | `mean(TTFT turn > 0) / mean(TTFT turn 0)` | < 1 → KV cache is active and reducing prefill time |
| **Context Growth Factor** | `mean(E2E last turn) / mean(E2E first turn)` | > 1 → latency increases as context grows |
| **KV Cache Hit Rate** | Fraction of prompt tokens served from KV cache | SGLang only, from `/get_server_info` |
| **KV Cache Usage** | GPU KV cache capacity used | vLLM only, from `/metrics` (Prometheus) |

A Turn-to-Turn Ratio close to 0 on a multi-turn scenario confirms the server is effectively reusing cached prefill tokens. Comparing this value between vLLM and SGLang on the same conversation directly measures KV cache efficiency.

---

## Scenario format (YAML)

```yaml
name: my-scenario
description: Optional description

servers:
  - name: gpu-vllm
    url: http://gpu-vllm:8000
    api_key: none          # optional
    backend: vllm          # vllm | sglang | llamacpp | litellm | openai
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
  - server: gpu-vllm
    model: devstral-small-2-24b
    conversation: multi-turn-debug

load:
  concurrent_users: 10
  iterations: 3
  ramp_up_seconds: 5.0
  think_time_seconds: 0.0
```

Each entry in `turns` with `role: user` triggers a real inference request. The conversation history (including assistant responses) is carried forward across turns, so the server sees a growing context — which is what drives KV cache and context growth metrics.

---

## Output format (JSONL)

One JSON object per request, written incrementally to disk during execution:

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
  "backend_metrics": {
    "vllm:gpu_cache_usage_perc": 0.34,
    "vllm:num_requests_running": 8.0
  }
}
```

The file is valid even if the benchmark is interrupted — each line is a complete, independent record.

**Read with pandas:**

```python
import pandas as pd

df = pd.read_json("results.jsonl", lines=True)

# Latency by server
print(df.groupby("target_server")[["ttft_s", "e2e_latency_s", "tokens_per_second"]].mean())

# Turn-to-turn latency ratio (manual)
print(df.groupby(["target_server", "conversation", "turn"])["ttft_s"].mean())
```

**Read with Polars:**

```python
import polars as pl

df = pl.read_ndjson("results.jsonl")
print(df.group_by("target_server").agg(pl.col("ttft_s").mean()))
```

---

## Scaleway example

See `scenarios/scaleway-devstral.yaml` for a complete benchmark of Devstral-Small-2-24B across three backends (llama-server GGUF on L40S, vLLM BF16 on H100, SGLang BF16 on H100), including single-turn, multi-turn, and long-context scenarios.
