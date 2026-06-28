.PHONY: help test

MAKEFLAGS += --no-print-directory

UV := $(shell command -v uvx 2>/dev/null)
WITH_ACT ?= 0
ACT_TEST_ENV = $(if $(filter 1 true yes on,$(WITH_ACT)),RUN_ACT_VALIDATION=1,)

test: ## Run template tests
	@if [ -z "$(strip $(UV))" ]; then \
		echo "uvx is required to run template tests. Install uv from https://docs.astral.sh/uv/getting-started/installation/" >&2; \
		exit 1; \
	fi
	$(ACT_TEST_ENV) $(UV) --with pytest-copier --with pyyaml --with syrupy --with make-parser --with hypothesis --with mdast pytest tests/

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS=":.*?## "; printf "Available targets:\n"} {printf "  %-15s %s\n", $$1, $$2}'
