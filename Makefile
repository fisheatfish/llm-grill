.SILENT:
.DEFAULT_GOAL := help

help:
	echo "Please use \`make \033[36m<target>\033[0m\`"
	echo "\t where \033[36m<target>\033[0m is one of"
	grep -E '^\.PHONY: [a-zA-Z_-]+ .*?## .*$$' $(MAKEFILE_LIST) \
		| sort | awk 'BEGIN {FS = "(: |##)"}; {printf "• \033[36m%-30s\033[0m %s\n", $$2, $$3}'

.PHONY: install ## Install all dependencies including dev extras
install:
	uv sync --all-extras

.PHONY: test ## Run the full test suite
test:
	uv run pytest

.PHONY: test-cov ## Run tests with coverage report
test-cov:
	uv run pytest --cov=llm_bench --cov-report=term-missing

.PHONY: lint ## Lint with ruff
lint:
	uv run ruff check src tests

.PHONY: lint-fix ## Lint with auto-fix
lint-fix:
	uv run ruff check --fix src tests

.PHONY: fmt ## Format with ruff
fmt:
	uv run ruff format src tests

.PHONY: fmt-check ## Format check (no write — même comportement que la CI)
fmt-check:
	uv run ruff format --check src tests

.PHONY: fix ## Auto-fix lint + format en une commande
fix: lint-fix fmt

.PHONY: ci-check ## Reproduit exactement la CI en local (lint + format check + tests + build)
ci-check: lint fmt-check test build

.PHONY: build ## Build distributable package
build:
	uv build

.PHONY: clean ## Remove generated artifacts
clean:
	rm -rf dist .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
