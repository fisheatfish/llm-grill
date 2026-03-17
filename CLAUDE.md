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
    api_key: string                 # "none" | clé littérale | ${ENV_VAR}
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

## GPU Monitoring (nvidia-smi via SSH)

Le `GpuMonitor` collecte les métriques GPU (mémoire, utilisation, température, puissance) en exécutant `nvidia-smi` via SSH sur les serveurs cibles.

### Activation dans le scénario YAML

```yaml
servers:
  - name: gpu-llama
    url: http://172.16.0.3:8080
    backend: llamacpp
    gpu_monitoring: true          # active le polling nvidia-smi
    ssh_host: 172.16.0.3         # optionnel, extrait de l'URL si absent
    ssh_user: root               # défaut : root
```

### Prérequis SSH

La machine qui lance `llm-bench` (gateway) doit pouvoir faire `ssh root@<serveur-gpu>` **sans mot de passe**.

1. Vérifier qu'une clé existe sur la gateway : `ls ~/.ssh/id_ed25519.pub`
2. Chercher une clé d'instance Scaleway : `ls ~/.ssh/instance_keys/`
3. Copier la clé autorisée sur le serveur GPU :
   ```bash
   # Depuis une machine ayant déjà accès au serveur GPU :
   cat /root/.ssh/authorized_keys   # sur la gateway
   # Ajouter la clé pub dans /root/.ssh/authorized_keys du serveur GPU
   ```
4. Tester : `ssh -o ConnectTimeout=5 root@172.16.0.3 "nvidia-smi --query-gpu=index --format=csv,noheader"`

> **Note** : `ssh-copy-id` ne fonctionne pas si le serveur GPU refuse déjà l'auth par mot de passe. Il faut copier la clé via un autre canal (console Scaleway, autre machine avec accès).

### Debug

- Lancer avec `--verbose` pour voir les logs du `GpuMonitor`
- Si les champs `gpu_*` sont tous `null` dans le JSONL → le SSH ne fonctionne pas ou `gpu_monitoring` n'est pas activé

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
