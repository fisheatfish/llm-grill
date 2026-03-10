.PHONY: install test test-cov lint fmt build clean

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

# Format with ruff
fmt:
	uv run ruff format src tests

# Build distributable package
build:
	uv build

# Remove generated artifacts
clean:
	rm -rf dist .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
