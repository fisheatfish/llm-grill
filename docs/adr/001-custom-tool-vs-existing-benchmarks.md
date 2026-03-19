# ADR 001: Custom benchmark tool vs existing alternatives

**Date:** 2026-03-17
**Status:** Accepted
**Deciders:** Team

---

## Context

Before building llm-grill, we evaluated existing LLM inference benchmarking tools. The question is whether an existing tool could satisfy our requirements or whether a custom solution is justified.

Our core requirements:

1. **Multi-turn conversations** — benchmark KV cache effectiveness across conversation turns, not just single-shot prompts.
2. **Multi-backend observability** — collect backend-specific metrics (KV cache usage, prefix cache hit rate, queue depth) from vLLM, SGLang, llama.cpp, and LiteLLM via their native APIs.
3. **Scenario-driven** — declarative YAML scenarios describing servers, models, conversations, and load profiles in a single file.
4. **Streaming TTFT measurement** — client-side TTFT from SSE first-token, not server-reported values.
5. **JSONL output** — incremental, flat, directly loadable by pandas/polars without post-processing.
6. **GPU metrics collection** — correlate inference metrics with GPU utilization, memory, temperature, and power draw via SSH.

---

## Alternatives evaluated

### LLMPerf (Ray)

Open-source benchmark from Anyscale, focused on throughput and latency for hosted LLM APIs.

| | |
|---|---|
| Pros | Simple to run. Measures TTFT and inter-token latency. Supports OpenAI-compatible endpoints. |
| Cons | **Single-turn only** — sends independent prompts, no conversation history or KV cache measurement. No backend-specific metric scraping. No scenario file format — configuration is via CLI flags. No GPU metric collection. Output requires post-processing for analysis. |
| Gap | Requirements 1, 2, 3, 5, 6 unmet. |

### GenAI-Perf (NVIDIA)

Part of NVIDIA Triton Inference Server ecosystem. Designed for benchmarking Triton and TensorRT-LLM deployments.

| | |
|---|---|
| Pros | Robust concurrency model. Detailed latency breakdown. GPU metrics via DCGM integration. Well-maintained by NVIDIA. |
| Cons | **Triton-centric** — assumes Triton or TensorRT-LLM backend. Does not natively support vLLM, SGLang, or llama.cpp OpenAI-compatible APIs. No multi-turn conversation support. Heavy dependency chain (Triton client libraries). No declarative scenario format. |
| Gap | Requirements 1, 2, 3 unmet. Backend lock-in. |

### Locust + custom scripts

General-purpose load testing framework, adaptable to any HTTP API.

| | |
|---|---|
| Pros | Mature concurrency model (gevent). Web UI for real-time monitoring. Extensible via Python classes. Large community. |
| Cons | **No SSE streaming support** — Locust's HTTP client does not handle server-sent events, making TTFT measurement impossible without significant custom code. No concept of multi-turn conversations with history accumulation. No backend metric scraping. Every feature we need (TTFT, TPOT, conversation turns, YAML scenarios, backend metrics, GPU monitoring) would need to be built as custom Locust plugins, at which point we are building llm-grill inside Locust's abstractions rather than our own. |
| Gap | Requirements 1, 2, 3, 4, 6 unmet without substantial custom development. |

### vLLM benchmarks (benchmark_serving.py)

Built-in benchmark script shipped with vLLM.

| | |
|---|---|
| Pros | Direct integration with vLLM internals. Measures TTFT and TPOT via streaming. Synthetic and ShareGPT dataset support. |
| Cons | **vLLM-only** — cannot target SGLang, llama.cpp, or LiteLLM. Single-turn prompts only. No scenario format. No GPU metric correlation. Tightly coupled to vLLM codebase, not installable as a standalone tool. |
| Gap | Requirements 1, 2, 3, 5, 6 unmet. Backend lock-in. |

---

## Decision

Build a custom tool (llm-grill) because no existing alternative covers the combination of:

- Multi-turn conversation benchmarking with KV cache analysis
- Cross-backend metric collection (vLLM, SGLang, llama.cpp, LiteLLM)
- Declarative YAML scenario format
- Client-side SSE streaming for TTFT measurement
- Correlated GPU metrics via SSH

The closest alternative would be Locust with custom plugins, but the required customization (SSE streaming, conversation state, backend scraping, GPU monitoring) would effectively mean building our own tool within Locust's framework — adding a dependency and abstraction layer without clear benefit.

---

## Consequences

- **Maintenance cost** — we own the full codebase: HTTP client, SSE parsing, metric collection, concurrency model. No upstream to rely on for fixes.
- **No community benchmarks** — results are not directly comparable with LLMPerf or GenAI-Perf outputs. We may need to run those tools in parallel for external comparisons.
- **Flexibility** — full control over the measurement methodology, output format, and backend integrations. New backends can be added without waiting on upstream support.

---

## References

- [LLMPerf (Ray/Anyscale)](https://github.com/ray-project/llmperf)
- [GenAI-Perf (NVIDIA)](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/client/src/c%2B%2B/perf_analyzer/genai-perf/README.html)
- [Locust](https://locust.io/)
- [vLLM benchmark_serving.py](https://github.com/vllm-project/vllm/blob/main/benchmarks/benchmark_serving.py)
- ADR 002 — Architecture CLI llm-grill
