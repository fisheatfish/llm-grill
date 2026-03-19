# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.1.0] - 2026-03-19

### Added
- **CLI commands** — `run`, `ping`, `show-scenario`, `report`
- **Backend clients** for vLLM, SGLang, llama.cpp, LiteLLM, and OpenAI-compatible servers — one abstract base class + one concrete client per backend with shared SSE streaming
- **Client-side latency measurement** — TTFT, TPOT, E2E latency via SSE streaming
- **Conversation quality metrics** — turn-to-turn TTFT ratio (KV cache effectiveness), context growth factor, KV cache hit rate and usage
- **Prometheus scraping** for vLLM and SGLang (`/metrics` endpoint) — KV cache usage, cache hit rate, running/waiting requests
- **GPU metrics collection** via SSH (`nvidia-smi`) — utilization, memory, temperature, power, multi-GPU support
- **Load ramp mode** (`ramp_levels`) — sweep multiple concurrency levels in a single run with auto-detected ramp results table
- **YAML scenario format** — declarative multi-turn conversations, concurrent users, ramp-up, think time, `${ENV_VAR}` API key syntax
- **JSONL output** — one record per request, streamable, directly loadable by pandas/Polars
- **Report generation** — Rich terminal tables, JSON, and CSV export
- **Example scenario** (`scenarios/example.yaml`) — ready-to-adapt template with localhost
- **CI/CD** — GitHub Actions with Python 3.11/3.12 matrix, lint, test, PyPI publish on tag, GitHub Release
