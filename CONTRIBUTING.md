# Contributing to llm-bench

Thank you for your interest in contributing.

---

## Getting started

1. Fork the repository and clone your fork.
2. Install dependencies:

```bash
uv sync --all-extras
```

3. Run the test suite to verify your setup:

```bash
make test
```

---

## Development workflow

- **Branch**: create a feature branch from `main` (`git checkout -b feat/my-feature`).
- **Code style**: `make fmt` (ruff format) before committing. `make lint` must pass.
- **Tests**: add tests for any new behaviour. Coverage target is >80% on `src/llm_bench/`.
- **Commits**: use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
- **Pull request**: open a PR against `main` with a description of what changed and why.

---

## Adding a new backend

See the **Adding a new backend** section in [DEVELOPER.md](DEVELOPER.md).

---

## Reporting bugs

Open an issue with:
- `llm-bench --version` output
- The command you ran and the scenario file (redact credentials)
- The full error message / traceback

---

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
