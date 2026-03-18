# Contributing to llm-bench

## Setup

```bash
git clone https://github.com/fisheatfish/llm-bench.git
cd llm-bench
make install
make test
```

## Make targets

| Target | Description |
|---|---|
| `make install` | Install all dependencies including dev extras |
| `make test` | Run the full test suite |
| `make test-cov` | Run tests with coverage (>90% required) |
| `make lint` | Auto-fix lint + format |
| `make check` | Lint check without fixing (CI-style) |
| `make build` | Build distributable package |

## Workflow

1. Branch from `main`: `git checkout -b feat/my-feature`
2. Write code + tests
3. `make lint` then `make test`
4. Open a PR against `main`

## Code conventions

- `from __future__ import annotations` in all modules
- Async everywhere in clients and runner (`anyio`)
- No direct `print` — use `rich.console.Console`
- Input validation via Pydantic, no defensive validation in core
- Short classes (< 80 lines), single responsibility
- Grouped imports: stdlib, third-party, local

## Tests

```
tests/
├── conftest.py       # shared fixtures
├── test_config.py    # Pydantic validation, YAML loading
├── test_metrics.py   # TTFT/TPOT/aggregation
├── test_clients.py   # clients with respx (SSE mock)
├── test_report.py    # CSV export, Rich tables
└── test_runner.py    # orchestration, concurrency
```

- Use **Given / When / Then** pattern in docstrings
- Use `pytest-mock` (`mocker` fixture), not `unittest.mock`
- Use `respx` for HTTP mocking
- Target coverage: >80% on `src/llm_bench/`

## Adding a new backend

1. Create `src/llm_bench/clients/mybackend.py` inheriting `BaseClient`
2. Implement `backend_metrics()` (optionally override `health()`)
3. Add the enum value in `config.py` -> `Backend`
4. Register it in `clients/__init__.py` -> `_REGISTRY`
5. Add tests in `tests/test_clients.py`

`BaseClient.complete()` handles SSE streaming generically — only override if the backend deviates from the OpenAI SSE format.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.
