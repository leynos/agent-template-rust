.PHONY: help check-fmt fmt interrogate lint spelling typecheck test

MAKEFLAGS += --no-print-directory

UV := $(shell command -v uvx 2>/dev/null)
TYPOS_CONFIG_BUILDER_VERSION ?= v0.1.3
TYPOS_CONFIG_BUILDER = uv tool run --from \
	"git+https://github.com/leynos/typos-config-builder.git@$(TYPOS_CONFIG_BUILDER_VERSION)" \
	typos-config-builder
WITH_ACT ?= 0
ACT_TEST_ENV = $(if $(filter 1 true yes on,$(WITH_ACT)),RUN_ACT_VALIDATION=1,)
PYTEST_DEPS = --with pytest-copier --with pyyaml --with syrupy --with make-parser --with hypothesis
MYPY_DEPS = $(PYTEST_DEPS) --with types-PyYAML
REQUIRE_UVX = @if [ -z "$(strip $(UV))" ]; then echo "uvx is required to run template tests. Install uv from https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1; fi

MDLINT ?= $(shell command -v markdownlint-cli2 2>/dev/null || printf '%s' "$$HOME/.bun/bin/markdownlint-cli2")
# `make fmt` and `make check-fmt` call mdtablefix directly. `--git` selects the
# Markdown files Git tracks and `--include-untracked` adds the untracked files
# Git does not ignore, so a new document is formatted before it is staged.
# Both modes need mdtablefix 0.6.0 or later; CI pins the version at the
# install-mdtablefix step.
MDTABLEFIX ?= mdtablefix
MDTABLEFIX_SELECT = --git --include-untracked
MDTABLEFIX_RULES = --wrap --renumber --breaks --ellipsis --fences

test: ## Run template tests
	@if [ -z "$(strip $(UV))" ]; then \
		echo "uvx is required to run template tests. Install uv from https://docs.astral.sh/uv/getting-started/installation/" >&2; \
		exit 1; \
	fi
	$(ACT_TEST_ENV) $(UV) $(PYTEST_DEPS) pytest tests/

check-fmt: ## Verify parent Python formatting
	$(REQUIRE_UVX)
	$(UV) --with ruff ruff format --check tests/
	$(MDTABLEFIX) --check $(MDTABLEFIX_SELECT) $(MDTABLEFIX_RULES)

fmt: ## Format parent Python tests
	$(REQUIRE_UVX)
	$(UV) --with ruff ruff format tests/
	$(MDTABLEFIX) --in-place $(MDTABLEFIX_SELECT) $(MDTABLEFIX_RULES)
	$(MDLINT) --fix "**/*.md"

# The repository's Python is the parent test suite under tests/. Interrogate
# scans each target recursively, subject to its default exclusions.
INTERROGATE_VERSION ?= 1.7.0
INTERROGATE_TARGETS ?= tests
# Level 2 prints a MISSED row per undocumented definition, which the
# `interrogate` recipe below looks for: the rounded percentage alone can pass a
# lone gap.
INTERROGATE_FLAGS ?= -vv --fail-under 100
# Cargo target directories hold build output, generated stubs and scratch
# crates that the repository does not own. Interrogate 1.7.0 resolves each
# `--exclude` to an absolute path and skips a file when its path matches
# "<exclude>*" under fnmatch, where `*` also crosses `/`. A pattern must
# therefore end in `/*`: a bare `target` would also skip `target_utils.py`.
# `target/*` prunes the root directory and `*/target/*` a nested crate's.
# `CARGO_TARGET_DIR` and `CARGO_BUILD_TARGET_DIR` are excluded too, with the
# fnmatch metacharacters in their values escaped so that they match literally.
fnmatch_escape = $(subst ?,[?],$(subst *,[*],$(subst [,[[],$(1))))
INTERROGATE_EXCLUDES ?= --exclude 'target/*' --exclude '*/target/*' \
	$(foreach dir,$(strip $(CARGO_TARGET_DIR) $(CARGO_BUILD_TARGET_DIR)),--exclude '$(call fnmatch_escape,$(dir))/*')
INTERROGATE ?= uv tool run --python 3.13 --from 'interrogate==$(INTERROGATE_VERSION)' interrogate

# Interrogate rounds its percentage to one decimal, so `--fail-under 100` alone
# can pass a lone gap in a large repository. This recipe also fails when `grep`
# finds a MISSED row in the report on standard output, which `-vv` or higher
# prints for each undocumented definition.
interrogate: ## Enforce complete Python docstring coverage
	@report="$$($(INTERROGATE) $(INTERROGATE_FLAGS) $(INTERROGATE_EXCLUDES) $(INTERROGATE_TARGETS))"; \
	  status=$$?; \
	  printf '%s\n' "$$report"; \
	  test "$$status" -eq 0 || exit "$$status"; \
	  if printf '%s\n' "$$report" | grep -q '| *MISSED *|'; then \
	    printf '%s\n' 'interrogate: undocumented definitions remain; see the MISSED rows above' >&2; \
	    exit 1; \
	  fi

lint: ## Lint parent Python tests
	$(MAKE) interrogate
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
