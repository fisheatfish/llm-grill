# CLAUDE.md — llm-bench

Source de vérité pour le build et le développement. Optimisé pour Claude Code.

---

## Projet

CLI Python de benchmark pour serveurs d'inférence LLM.
Mesure TTFT, TPOT, latence E2E, throughput, success rate sur des scénarios multi-conversations multi-serveurs.

**Décisions d'architecture** : `docs/adr/001-architecture-cli-llm-bench.md`
**Plan d'implémentation** : `docs/plan/implementation-plan.md` (non versionné)

---

## Stack

| Rôle | Lib | Version min |
|---|---|---|
| CLI | typer | 0.12 |
| Affichage | rich | 13 |
| Validation config | pydantic | 2 |
| HTTP async + SSE | httpx | 0.27 |
| Concurrence | anyio | 4 |
| Scénarios | pyyaml | 6 |
| Tests | pytest + pytest-asyncio + respx | 8 / 0.23 / 0.21 |
| Packaging | uv + hatchling | — |

---

## Structure

```
src/llm_bench/
├── __init__.py       # __version__
├── cli.py            # app Typer — commandes : run, ping, show-scenario, report
├── config.py         # Pydantic : ServerConfig, ModelConfig, ScenarioConfig, ConversationTemplate
├── scenario.py       # Chargement et validation des fichiers YAML
├── clients/
│   ├── base.py       # Classe abstraite BaseClient (méthodes : chat_stream, health, metrics_raw)
│   ├── vllm.py       # Client vLLM (endpoint /metrics Prometheus)
│   ├── sglang.py     # Client SGLang (endpoint /get_server_info)
│   ├── llamacpp.py   # Client llama.cpp / llama-server
│   └── litellm.py    # Client LiteLLM (gateway)
├── metrics.py        # dataclass RequestMetrics + fonctions d'agrégation
├── runner.py         # Orchestration : concurrence anyio, gestion des tours de conversation
└── report.py         # Écriture JSONL incrémentale + export CSV + tableau Rich

scenarios/            # Fichiers YAML de scénarios
tests/                # pytest — un fichier par module src
docs/adr/             # ADRs versionnés
docs/plan/            # Plans non versionnés (.gitignore)
```

---

## Commandes Make

```bash
make install      # uv sync --all-extras
make test         # pytest
make lint         # ruff check src tests
make fmt          # ruff format src tests
make build        # uv build
make clean        # supprime dist/ __pycache__ .pytest_cache
```

---

## Commandes CLI

```bash
llm-bench run scenarios/foo.yaml [--output results.jsonl] [--format jsonl|csv] [--verbose]
llm-bench ping --scenario scenarios/foo.yaml
llm-bench show-scenario scenarios/foo.yaml
llm-bench report results.jsonl [--format csv|table]
```

---

## Format scénario (YAML)

```yaml
name: string                        # identifiant du scénario
description: string                 # optionnel
servers:
  - name: string
    url: http://host:port           # base URL (sans /v1)
    api_key: string                 # défaut "none"
    backend: vllm|sglang|llamacpp|litellm|openai
    timeout: float                  # secondes, défaut 120
models:
  - name: string                    # model_id exact tel qu'attendu par le serveur
    max_tokens: int                 # défaut 512
    temperature: float              # défaut 0.0
conversations:
  - name: string
    description: string
    turns:
      - role: system|user|assistant
        content: string
targets:                            # combinaisons à benchmarker
  - server: string                  # doit matcher servers[].name
    model: string                   # doit matcher models[].name
    conversation: string            # doit matcher conversations[].name
load:
  concurrent_users: int             # défaut 1
  iterations: int                   # défaut 1 (par user)
  ramp_up_seconds: float            # défaut 0.0
  think_time_seconds: float         # pause entre les tours, défaut 0.0
```

---

## Format de sortie JSONL

Une ligne JSON par requête complète :

```json
{
  "scenario": "string",
  "target_server": "string",
  "target_model": "string",
  "conversation": "string",
  "turn": 0,
  "iteration": 0,
  "user_id": 0,
  "timestamp_start": "ISO8601",
  "ttft_s": 0.0,
  "tpot_s": 0.0,
  "e2e_latency_s": 0.0,
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "tokens_per_second": 0.0,
  "success": true,
  "error": null,
  "backend_metrics": {}            // métriques spécifiques au backend si disponibles
}
```

Lecture pandas : `pd.read_json("results.jsonl", lines=True)`
Lecture polars : `pl.read_ndjson("results.jsonl")`

---

## Clients backend

Chaque client hérite de `BaseClient` (ABC) et implémente :

- `complete(messages, model_config) -> StreamResult` — stream SSE, mesure TTFT/TPOT/E2E
- `health() -> bool` — vérification connectivité (timeout court : 10s)
- `backend_metrics() -> dict` — métriques propriétaires (Prometheus scrape pour vLLM/SGLang)

La mesure TTFT se fait côté client :
- `t0` = juste avant l'envoi de la requête HTTP
- `t_first` = réception du premier chunk SSE non-vide
- `t_last` = réception du token `[DONE]`
- TTFT = `t_first - t0`
- E2E = `t_last - t0`
- TPOT = `(E2E - TTFT) / max(completion_tokens - 1, 1)`

---

## Conventions de code

- Classes courtes (< 80 lignes). Une responsabilité par classe.
- Async partout dans les clients et le runner (`anyio.create_task_group` pour la concurrence).
- Pas de print direct — `rich.console.Console` uniquement.
- Validation à l'entrée via Pydantic. Pas de validation défensive dans le cœur.
- `from __future__ import annotations` dans tous les modules.
- Imports groupés : stdlib → third-party → local.

---

## Tests

```
tests/
├── conftest.py          # fixtures : ScenarioConfig mock, respx mock server
├── test_config.py       # validation Pydantic, chargement YAML
├── test_metrics.py      # calculs TTFT/TPOT/agrégation
├── test_clients.py      # clients avec respx (SSE mock)
└── test_runner.py       # orchestration, concurrence
```

Couverture cible : > 80 % sur `src/llm_bench/`.

---

## Fichiers à ne pas versionner

Ajouter au `.gitignore` :
- `docs/plan/`
- `results/`
- `*.jsonl`
- `.env`
