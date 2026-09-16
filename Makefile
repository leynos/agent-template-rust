.PHONY: help check-fmt fmt lint spelling typecheck test

MAKEFLAGS += --no-print-directory

UV := $(shell command -v uvx 2>/dev/null)
TYPOS_CONFIG_BUILDER_VERSION ?= v0.1.1
TYPOS_CONFIG_BUILDER = uv tool run --from \
	"git+https://github.com/leynos/typos-config-builder.git@$(TYPOS_CONFIG_BUILDER_VERSION)" \
	typos-config-builder
WITH_ACT ?= 0
ACT_TEST_ENV = $(if $(filter 1 true yes on,$(WITH_ACT)),RUN_ACT_VALIDATION=1,)
PYTEST_DEPS = --with pytest-copier --with pyyaml --with syrupy --with make-parser --with hypothesis
MYPY_DEPS = $(PYTEST_DEPS) --with types-PyYAML
REQUIRE_UVX = @if [ -z "$(strip $(UV))" ]; then echo "uvx is required to run template tests. Install uv from https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1; fi

test: ## Run template tests
	@if [ -z "$(strip $(UV))" ]; then \
		echo "uvx is required to run template tests. Install uv from https://docs.astral.sh/uv/getting-started/installation/" >&2; \
		exit 1; \
	fi
	$(ACT_TEST_ENV) $(UV) $(PYTEST_DEPS) pytest tests/

check-fmt: ## Verify parent Python formatting
	$(REQUIRE_UVX)
	$(UV) --with ruff ruff format --check tests/

fmt: ## Format parent Python tests
	$(REQUIRE_UVX)
	$(UV) --with ruff ruff format tests/
	mdformat-all

lint: ## Lint parent Python tests
	$(REQUIRE_UVX)
	$(UV) --with ruff ruff check tests/

typecheck: ## Type-check parent Python tests
	$(REQUIRE_UVX)
	$(UV) --with mypy $(MYPY_DEPS) mypy tests/

spelling: ## Enforce en-GB-oxendict spelling in parent and template prose
	$(TYPOS_CONFIG_BUILDER) gate --repository . --scope all

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS=":.*?## "; printf "Available targets:\n"} {printf "  %-15s %s\n", $$1, $$2}'
