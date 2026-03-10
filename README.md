# llm-bench

CLI for benchmarking LLM inference servers: vLLM, SGLang, llama.cpp, LiteLLM.

Measures **TTFT**, **TPOT**, **end-to-end latency**, **throughput**, and **success rate** on multi-turn conversation scenarios.

---

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install llm-bench
# or in a project venv:
uv add llm-bench
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

**3. Generate a report**

```bash
llm-bench report results.jsonl
llm-bench report results.jsonl --format csv --output summary.csv
```

---

## Commands

| Command | Description |
|---|---|
| `llm-bench run <scenario>` | Run a benchmark, stream results to JSONL |
| `llm-bench ping <scenario>` | Test server connectivity |
| `llm-bench show-scenario <scenario>` | Validate and display a scenario |
| `llm-bench report <results.jsonl>` | Generate a summary table or CSV |

### `run` options

| Option | Default | Description |
|---|---|---|
| `--output / -o` | `results-<name>.jsonl` | Output file path |
| `--format / -f` | `jsonl` | `jsonl` or `csv` |
| `--quiet / -q` | off | Suppress progress display |

### `report` options

| Option | Default | Description |
|---|---|---|
| `--format / -f` | `table` | `table`, `json`, or `csv` |
| `--output / -o` | — | Output path for CSV format |

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
  - name: code-review
    turns:
      - role: system
        content: "You are an expert developer."
      - role: user
        content: "Review this function: def add(a, b): return a + b"

targets:
  - server: gpu-vllm
    model: devstral-small-2-24b
    conversation: code-review

load:
  concurrent_users: 10
  iterations: 3
  ramp_up_seconds: 5.0
  think_time_seconds: 0.0
```

---

## Output format (JSONL)

One JSON object per request, written incrementally:

```json
{
  "scenario": "my-scenario",
  "target_server": "gpu-vllm",
  "target_model": "devstral-small-2-24b",
  "conversation": "code-review",
  "turn": 0,
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
  "backend_metrics": {}
}
```

**Read with pandas:**

```python
import pandas as pd
df = pd.read_json("results.jsonl", lines=True)
print(df.groupby("target_server")[["ttft_s", "e2e_latency_s", "tokens_per_second"]].mean())
```

**Read with Polars:**

```python
import polars as pl
df = pl.read_ndjson("results.jsonl")
```

---

## Metrics

| Metric | Description |
|---|---|
| **TTFT** | Time to First Token — from request sent to first token received |
| **TPOT** | Time Per Output Token — decode time / (completion_tokens - 1) |
| **E2E latency** | Total time from request to last token |
| **tokens/s** | Completion tokens / E2E latency, per request |
| **total tokens/s** | Total completion tokens / total benchmark duration |
| **success rate** | % of requests that completed without error |

---

## Scaleway example

See `scenarios/scaleway-devstral.yaml` for a complete example benchmarking Devstral-Small-2-24B across three backends (llama-server GGUF, vLLM BF16, SGLang BF16).
