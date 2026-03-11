.PHONY: install test test-cov lint fmt fix build clean ci-check

# Install all dependencies including dev extras
install:
	uv sync --all-extras

# Run the full test suite
test:
	uv run pytest

# Run tests with coverage report
test-cov:
	uv run pytest --cov=llm_bench --cov-report=term-missing

# Lint with ruff
lint:
	uv run ruff check src tests

# Lint with auto-fix
lint-fix:
	uv run ruff check --fix src tests

# Format with ruff
fmt:
	uv run ruff format src tests

# Format check (no write — même comportement que la CI)
fmt-check:
	uv run ruff format --check src tests

# Auto-fix lint + format en une commande
fix: lint-fix fmt

# Reproduit exactement la CI en local (lint + format check + tests + build)
ci-check: lint fmt-check test build

# Build distributable package
build:
	uv build

# Remove generated artifacts
clean:
	rm -rf dist .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
