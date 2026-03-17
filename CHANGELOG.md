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
- **`servers` + `backends` merged into `backends`** — single YAML section replaces the redundant `servers`/`backends` split ; `ServerConfig` removed, `BackendConfig` is now the unified config (carries `url`, `api_key`, `timeout`, `type`, `ssh_host`, `ssh_user`, `gpu_monitoring`)
- **`BenchmarkTarget` simplified** — `server` (required) + `backend` (optional) replaced by a single required `backend` field referencing `backends[].name`
- **Flat `RequestMetrics`** — `backend_metrics: dict` and `gpu_metrics: dict` removed ; all metrics are top-level typed fields (`kv_cache_usage`, `cache_hit_rate`, `requests_running`, `requests_waiting`, `gpu_*`) — `pd.read_json(lines=True)` gives columns directly
- **Canonical backend metric keys** — all clients now return the same keys (`kv_cache_usage`, `cache_hit_rate`, `requests_running`, `requests_waiting`) regardless of backend ; no more `vllm:` prefixes or `num_running_reqs` vs `num_requests_running` inconsistency
- `gpu_type` and `model_dtype` removed from config and output — these are infrastructure metadata, not benchmark data

### Removed
- `ServerConfig` class — replaced by `BackendConfig`
- `BackendConfig.to_server_config()` bridge method — no longer needed
- `ScenarioConfig.servers` field and `get_server()` method
- `RequestMetrics.backend_metrics` and `RequestMetrics.gpu_metrics` nested dicts
- `_flatten()` helper in `report.py` — no more nested dicts to flatten
- `_extract_backend_metric()` in `metrics.py` — replaced by direct attribute access

### Fixed
- SGLang `cache_hit_rate` and `num_running_reqs` always null — now scraped from `/metrics` Prometheus endpoint
- `insitu-scaleway-devstral.yaml` targets referenced non-existent `server: gateway` — now correctly point to backend names

## [0.5.1] - 2026-03-11

### Fixed
- En mode ramp (`ramp_levels`), la table **Conversation Quality Metrics** (KV cache hit rate, turn-to-turn ratio, context growth factor) n'était pas affichée après la table Load Ramp Results — un `return` prématuré dans `_print_results` et un `else` mal placé dans `report` masquaient les métriques conversationnelles
- Commande `llm-bench report --format table` : même correctif — la table conversation était dans le bloc `else` et donc ignorée en mode ramp

## [0.5.0] - 2026-03-11

### Added
- **Load Ramp** (`ramp_levels`) — nouveau champ optionnel dans `LoadConfig` permettant de tester plusieurs niveaux de concurrence en une seule exécution (`ramp_levels: [1, 5, 10, 20, 50]`)
- `ramp_pause_seconds` dans `LoadConfig` — pause configurable entre chaque niveau (défaut : 10 s)
- `RampRunner` dans `runner.py` — itère les niveaux séquentiellement, chaque `RequestMetrics` est taggé avec `concurrent_users_level`
- `concurrent_users_level: int` sur `RequestMetrics` (défaut `0` — rétrocompatible avec les JSONL existants)
- `group_by_level()` dans `metrics.py` — groupe les résultats par `(server, model, concurrent_users_level)`
- `is_ramp_run()` dans `metrics.py` — détecte automatiquement si un fichier JSONL contient plusieurs niveaux distincts
- `print_ramp_table()` dans `report.py` — table Rich dédiée : Server | Model | Users | Requests | Success% | TTFT mean | TTFT p95 | E2E mean | E2E p95 | Tok/s total, triée par (server, model, level)
- `llm-bench run` et `llm-bench report --format table` détectent automatiquement le mode ramp et affichent la table dédiée
- `llm-bench show-scenario` affiche `ramp_levels` et `ramp_pause_seconds` si présents

### Changed
- `BenchmarkRunner.run()` délègue à `RampRunner` quand `ramp_levels` est défini ; chemin classique inchangé sinon

## [0.4.2] - 2026-03-11

### Fixed
- `SglangClient.backend_metrics()` : `kvcache` désormais extrait récursivement dans la réponse imbriquée de `/server_info` (la valeur n'était pas au niveau racine) ; normalisé de 0-100 vers 0-1 pour cohérence avec vLLM
- `VllmClient.backend_metrics()` : métrique renommée `vllm:gpu_cache_usage_perc` → `vllm:kv_cache_usage_perc` dans vLLM >= 0.4 — les deux noms sont maintenant supportés (fallback sur l'ancien nom pour rétrocompatibilité)

### Added
- **KV cache hit rate pour vLLM** : calculé depuis les counters Prometheus `prefix_cache_hits_total / prefix_cache_queries_total` — disponible sans configuration supplémentaire si `enable_prefix_caching=True`
- **KV cache hit rate pour SGLang** : extraction de `cache_hit_rate` depuis `/server_info` — nécessite `--enable-cache-report` au démarrage du serveur SGLang
- `metrics.py` : `kv_cache_usage_mean` cherche successivement `vllm:kv_cache_usage_perc`, `vllm:gpu_cache_usage_perc`, `kv_cache_usage` (SGLang)

## [0.4.1] - 2026-03-11

### Fixed
- `BaseClient.complete()` : crash `list index out of range` sur les chunks SSE avec `choices: []` — llama-server envoie ce chunk en fin de stream avant `[DONE]` ; la gateway LiteLLM le filtrait silencieusement, masquant le bug en accès indirect

## [0.4.0] - 2026-03-11

### Added
- `api_key` dans `ServerConfig` supporte la syntaxe `${VAR_NAME}` — la variable d'environnement est résolue au chargement du scénario ; erreur explicite si absente
- `scenarios/scaleway-devstral.yaml` revu pour architecture LiteLLM gateway : un seul serveur gateway, routing par alias modèle (`devstral-small-llama`, `devstral-small-vllm`, `devstral-small-sglang`)
- `scenarios/insitu-scaleway-devstral.yaml` — scénario template pour exécution in-situ depuis le serveur gateway (accès direct aux backends, métriques KV cache disponibles)
- `README.md` : sections **API keys** (syntaxe `${VAR}`) et **LiteLLM gateway routing** (pattern model aliases)
- `DEVELOPER.md` : entrées Troubleshooting pour 401 Unauthorized et ping timeout LiteLLM

### Fixed
- `LiteLLMClient.health()` surcharge `BaseClient.health()` pour utiliser `/health/liveliness` en priorité — évite le timeout de 10 s causé par `/health` qui déclenche des appels d'inférence sur tous les modèles configurés

### Changed
- `README.md` : section Install simplifiée (suppression des instructions PyPI non disponibles, installation depuis les sources uniquement)

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
  - **KV Cache Hit Rate** — averaged from SGLang `/server_info` (`cache_hit_rate`)
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
- Prometheus scraping for vLLM (`/metrics`) and SGLang (`/server_info`)
