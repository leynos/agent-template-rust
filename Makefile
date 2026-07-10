.PHONY: help spelling test

MAKEFLAGS += --no-print-directory

UV := $(shell command -v uvx 2>/dev/null)
TYPOS_VERSION ?= 1.48.0
TYPOS := uv tool run typos@$(TYPOS_VERSION)
WITH_ACT ?= 0
ACT_TEST_ENV = $(if $(filter 1 true yes on,$(WITH_ACT)),RUN_ACT_VALIDATION=1,)

test: ## Run template tests
	@if [ -z "$(strip $(UV))" ]; then \
		echo "uvx is required to run template tests. Install uv from https://docs.astral.sh/uv/getting-started/installation/" >&2; \
		exit 1; \
	fi
	$(ACT_TEST_ENV) $(UV) --with pytest-copier --with pyyaml --with syrupy --with make-parser --with hypothesis pytest tests/

spelling: ## Enforce en-GB-oxendict spelling in parent and template prose
	uv run scripts/generate_typos_config.py
	find . -type f \( -name '*.md' -o -name '*.md.jinja' \) -not -path './.git/*' -print0 | \
		xargs -0 $(TYPOS) --config typos.toml --force-exclude

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS=":.*?## "; printf "Available targets:\n"} {printf "  %-15s %s\n", $$1, $$2}'
