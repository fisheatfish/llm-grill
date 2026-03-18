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

.PHONY: test ## 🧪 Run the full test suite
test: install
	uv run pytest

.PHONY: test-cov ## 🧪 Run tests with coverage report
test-cov: install
	uv run pytest --disable-warnings --cov=llm_bench --cov-fail-under 90 --cov-report=term-missing

.PHONY: lint ## 🕵 Run lint and format on all packages
lint:
	uv run ruff check . --fix
	uv run ruff format .

.PHONY: check ## 🕵 Run lint check without fixing
check:
	uv run ruff check .

.PHONY: build ## 📦 Build distributable package
build: install
	uv build
