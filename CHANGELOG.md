# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.2.0] - 2026-03-10

### Added
- `ConversationMetrics` dataclass — per-conversation quality metrics
- `aggregate_conversations()` — groups results by (server, model, conversation) and computes:
  - **Turn-to-Turn Latency Ratio** — mean(TTFT turn > 0) / mean(TTFT turn 0); < 1 indicates KV cache benefit
  - **Context Growth Factor** — mean(E2E last turn) / mean(E2E first turn); > 1 indicates latency increase with context
  - **KV Cache Hit Rate** — averaged from SGLang `/get_server_info` (`cache_hit_rate`)
  - **KV Cache Usage** — averaged from vLLM `/metrics` (`vllm:gpu_cache_usage_perc`)
- `print_conversation_table()` in `report.py` — Rich table for conversation metrics
- `llm-bench report --no-conversations` flag to hide conversation metrics table
- `--format json` now includes both `summary` and `conversations` sections
- Fixed invalid TOML syntax in `pyproject.toml` authors field

## [0.1.0] - 2026-03-10

### Added
- `llm-bench run` — benchmark a YAML scenario, write results to JSONL
- `llm-bench ping` — test server connectivity
- `llm-bench show-scenario` — validate and display a scenario file
- `llm-bench report` — generate summary table, JSON, or CSV from a results file
- Backend clients for vLLM, SGLang, llama.cpp, and LiteLLM
- Client-side TTFT, TPOT, and E2E latency measurement via SSE streaming
- JSONL output format (streamable, pandas/Polars compatible)
- CSV export via `--format csv` or `llm-bench report --format csv`
- YAML scenario format with multi-turn conversations, concurrent users, and ramp-up
- Example scenario for Scaleway infrastructure (Devstral-Small-2-24B, 3 backends)
- Prometheus scraping for vLLM (`/metrics`) and SGLang (`/get_server_info`)
