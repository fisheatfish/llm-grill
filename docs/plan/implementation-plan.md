# Implementation Plan — llm-bench

> Non versionné. Mis à jour au fil des sprints.

## Stack retenue (ADR-001)

- CLI: Typer + Rich
- HTTP: httpx async + SSE streaming
- Config/Validation: Pydantic v2
- Format scénarios: JSON
- Client: unique (OpenAI-compatible)
- Packaging: uv + hatchling

## Structure du projet

```
llm-bench/
├── src/llm_bench/
│   ├── __init__.py
│   ├── cli.py           # Commandes Typer
│   ├── config.py        # Schémas Pydantic
│   ├── client.py        # Client httpx async SSE
│   ├── runner.py        # Orchestration benchmark
│   ├── metrics.py       # Calcul et agrégation métriques
│   └── report.py        # Export CSV/JSON + affichage Rich
├── scenarios/
│   └── scaleway-devstral.json
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_metrics.py
│   ├── test_client.py
│   └── test_runner.py
├── docs/adr/
├── docs/plan/            (non versionné)
├── pyproject.toml
├── Makefile
├── CLAUDE.md
├── README.md
└── DEVELOPER.md
```

## Commandes CLI

| Commande | Description |
|---|---|
| `llm-bench run` | Lance un benchmark complet |
| `llm-bench ping` | Teste la connectivité aux serveurs |
| `llm-bench show-scenario` | Affiche et valide un fichier de scénario |
| `llm-bench report` | Génère un rapport depuis un fichier de résultats |

## Phases

### Phase 1 — Socle (v0.1)
- [x] Structure projet, pyproject.toml, Makefile
- [x] config.py : schémas Pydantic (ServerConfig, ModelConfig, ScenarioConfig)
- [x] client.py : client httpx SSE, mesure TTFT
- [x] metrics.py : RequestMetrics, agrégation
- [x] runner.py : orchestration séquentielle + concurrence (anyio)
- [x] report.py : export CSV/JSON, tableau Rich
- [x] cli.py : commandes run, ping, show-scenario, report
- [x] Tests unitaires
- [x] Scénario exemple Scaleway

### Phase 2 — Métriques avancées (v0.2)
- [ ] Scraping métriques Prometheus (KV cache hit rate, queue depth)
- [ ] Turn-to-Turn Latency Ratio
- [ ] Context Growth Impact
- [ ] Cache Hit Rate via Prometheus

### Phase 3 — Distribution (v0.3)
- [ ] Guide packaging
- [ ] CI/CD GitHub Actions
- [ ] Publication PyPI
