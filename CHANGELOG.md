# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.3.0] - 2026-03-10

### Fixed (code review — MAJEUR)
- `Message.role` est maintenant typé `Literal["system", "user", "assistant"]` — les typos sont détectées à la validation du scénario
- `ScenarioConfig` valide que les références dans `targets` existent bien dans `servers`, `models`, `conversations`
- `LoadConfig.ramp_up_seconds` et `think_time_seconds` rejettent les valeurs négatives (`ge=0`)
- `t_last` est maintenant toujours mis à jour après la fin du stream SSE, même sans token `[DONE]`
- Chunks SSE malformés ignorés gracieusement (`json.JSONDecodeError` capturée)
- `total_duration` dans `llm-bench report` calculé correctement via `estimate_total_duration()` (timestamps + E2E) au lieu de `max(e2e_latency)`
- Iterations d'un user désormais séquentielles — le ramp-up est appliqué par user dans sa propre coroutine
- `export_csv` utilise l'union de toutes les clés (colonnes `backend_metrics` hétérogènes entre serveurs)
- `JsonlWriter` ouvre le fichier dans `__enter__` et non dans `__init__`
- Version synchronisée via hatchling `dynamic = ["version"]` — source unique dans `__init__.py`

### Added
- `estimate_total_duration()` dans `metrics.py` — durée wall-clock à partir des timestamps
- `group_by_target()` dans `metrics.py` — helper partagé, supprime le pattern dupliqué
- `clients/prometheus.py` — parser Prometheus partagé entre vLLM et llama.cpp
- `--verbose / -v` sur la CLI — active le logging debug (`logging.basicConfig`)
- `--version` affiche `0.3.0`
- `tests/test_cli.py` — couverture des 4 commandes via `CliRunner`
- `tests/test_report.py` — couverture de `JsonlWriter`, `load_jsonl`, `export_csv`
- `src/llm_bench/py.typed` — marker PEP 561 (classifier `Typing :: Typed` honoré)
- `pytest-cov` dans les dépendances dev
- `ruff format --check` dans la CI

### Changed
- Clients : `health()` implémenté dans `BaseClient` (timeout 10 s) — les sous-classes ne le surchargent que si nécessaire
- Clients : `__init__` inutiles supprimés dans VllmClient, SglangClient, LiteLLMClient
- Clients : `Authorization` header omis quand `api_key` est `"none"`
- Logging structuré ajouté dans `runner.py` et `clients/base.py`
- CLAUDE.md : méthode `chat_stream` → `complete`, syntaxe CLI corrigée

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
