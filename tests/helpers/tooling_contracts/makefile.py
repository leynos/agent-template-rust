"""Assert rendered Makefile contracts for generated Rust projects."""

from __future__ import annotations

import re
import tempfile
from importlib import import_module
from pathlib import Path
from typing import Any, cast


def _assert_makefile_contracts(makefile: str) -> None:
    """Assert generated Makefile tooling contracts."""
    makefile_rules = _load_and_parse_makefile_rules(makefile)
    for target in [
        "all",
        "audit",
        "build",
        "check-build-tools",
        "check-coverage-tools",
        "check-fmt",
        "check-rust-toolchain",
        "coverage",
        "fmt",
        "install-build-tools",
        "install-cranelift",
        "lint",
        "lint-actions",
        "lint-shell",
        "lint-yaml",
        "markdownlint",
        "nixie",
        "rust-audit",
        "spelling",
        "test",
        "test-ui",
        "test-workflow-contracts",
        "typecheck",
    ]:
        assert target in makefile_rules, f"expected generated Makefile target {target}"
    assert "SHELL := bash" in makefile, (
        "expected generated Makefile to use Bash for pipefail audit recipes"
    )
    assert "TEST_CMD :=" in makefile, (
        "expected generated Makefile to define a test command fallback"
    )
    assert "nextest run,test" in makefile, (
        "expected generated Makefile to fall back to cargo test without cargo-nextest"
    )
    assert "$(CARGO) $(TEST_CMD)" in makefile, (
        "expected generated Makefile test target to use the selected test command"
    )
    assert "test: export RUSTFLAGS := $(DEV_RUST_FLAGS)" in makefile, (
        "expected generated Makefile test target to export Rust flags once"
    )
    assert "RUSTDOC_FLAGS ?=" in makefile, (
        "expected generated Makefile to preserve inherited Rustdoc flags"
    )
    assert (
        "RUSTDOC_FLAGS := --cfg docsrs -D warnings $(POLONIUS_FLAGS) $(RUSTDOC_FLAGS)"
    ) in makefile, (
        "expected generated Makefile to require docsrs cfg and deny Rustdoc warnings"
    )
    assert (
        'RUSTDOCFLAGS="$(RUSTDOC_FLAGS)" $(CARGO) test --doc --workspace --all-features'
    ) in makefile, (
        "expected generated Makefile test target to run doctests with Rustdoc flags"
    )
    assert (
        'PATH="$(BUILD_TOOLS_PATH)" RUSTDOCFLAGS="$(RUSTDOC_FLAGS)" '
        'RUSTFLAGS="$(DEV_RUST_FLAGS)" $(CARGO) doc --no-deps'
    ) in makefile, (
        "expected generated Makefile lint target to deny Rustdoc warnings with "
        "the pinned build tools on PATH"
    )
    assert (
        'PATH="$(BUILD_TOOLS_PATH)" RUSTFLAGS="$(DEV_RUST_FLAGS)" '
        "$(CARGO) clippy $(CLIPPY_FLAGS)"
    ) in makefile, (
        "expected generated Makefile lint target to run Clippy with the "
        "development flags and the pinned build tools on PATH"
    )
    assert (
        "coverage: check-coverage-tools ## Generate lcov coverage with lld" in makefile
    ), "expected generated Makefile to include an lld-backed coverage target"
    assert "COVERAGE_LINKER_FLAGS ?= -fuse-ld=lld" in makefile, (
        "expected generated Makefile coverage target to select lld"
    )
    assert 'CFLAGS="$(COVERAGE_LINKER_FLAGS)"' in makefile, (
        "expected generated Makefile coverage target to set CFLAGS"
    )
    assert 'LDFLAGS="$(COVERAGE_LINKER_FLAGS)"' in makefile, (
        "expected generated Makefile coverage target to set LDFLAGS"
    )
    assert "$(WHITAKER) --all -- $(CARGO_FLAGS)" in makefile, (
        "expected generated Makefile lint target to run Whitaker"
    )
    assert "TYPOS_CONFIG_BUILDER_VERSION ?= v0.1.3" in makefile, (
        "expected generated Makefile to pin the shared spelling gate version"
    )
    assert (
        "git+https://github.com/leynos/typos-config-builder.git"
        "@$(TYPOS_CONFIG_BUILDER_VERSION)"
    ) in makefile, "expected generated Makefile to resolve the gate from the pinned ref"
    assert "+$(MAKE) spelling" in makefile, (
        "expected generated comprehensive and Markdown gates to enforce spelling"
    )
    assert "$(TYPOS_CONFIG_BUILDER) gate --repository .\n" in makefile, (
        "expected generated spelling gate to run the shared builder gate"
    )
    assert "--scope" not in makefile, (
        "expected generated spelling gate to use the default Markdown scope"
    )
    assert "git rev-parse --is-inside-work-tree" in makefile, (
        "expected generated spelling gate to require a Git repository"
    )
    assert "$$(git ls-files)" in makefile, (
        "expected generated spelling gate to require staged files"
    )
    assert "scripts/generate_typos_config.py" not in makefile, (
        "expected generated Makefile to drop the retired vendored generator"
    )
    assert 'echo "Whitaker binary: $(WHITAKER)"' in makefile, (
        "expected generated Makefile lint target to log Whitaker resolution"
    )
    assert 'echo "coverage linker flags: $(COVERAGE_LINKER_FLAGS)"' in makefile, (
        "expected generated Makefile coverage target to log linker flags"
    )
    assert "audit: rust-audit ## Audit dependencies for known vulnerabilities" in (
        makefile
    ), "expected generated Makefile to expose audit as the public audit target"
    assert "rust-audit: ## Audit the Rust workspace for known vulnerabilities" in (
        makefile
    ), "expected generated Makefile to expose rust-audit implementation target"
    assert "$(CARGO) metadata --no-deps --format-version 1 | python3 -c" in makefile, (
        "expected generated audit target to derive workspace metadata with python3"
    )
    assert 'printf "Audit metadata phase: deriving workspace manifests\\n"' in (
        makefile
    ), "expected generated audit target to mark metadata extraction"
    assert 'printf "Auditing Rust workspace %s\\n" "$$workspace_root"' in makefile, (
        "expected generated audit target to log the derived workspace root"
    )
    assert 'printf "Workspace Rust manifest %s\\n"' in makefile, (
        "expected generated audit target to log workspace member manifests"
    )
    assert "for advisory in $$CARGO_AUDIT_IGNORES" in makefile, (
        "expected generated audit target to read documented cargo audit ignores"
    )
    assert 'audit_flags+=(--ignore "$$advisory")' in makefile, (
        "expected generated audit target to translate ignores into cargo-audit flags"
    )
    assert 'printf "Audit execution phase: running cargo audit\\n"' in makefile, (
        "expected generated audit target to mark cargo-audit execution"
    )
    assert "Audit failures may indicate RustSec advisories" in makefile, (
        "expected generated audit target to document failure scenarios"
    )
    assert '(cd "$$workspace_root" && $(CARGO) audit "$${audit_flags[@]}")' in (
        makefile
    ), (
        "expected generated audit target to run cargo audit with translated ignores "
        "from the workspace root"
    )
    assert "INHERITED_RUST_FLAGS := $(RUSTFLAGS)" in makefile, (
        "expected generated Makefile to capture RUSTFLAGS inherited from the "
        "environment before composing its own flags"
    )
    assert (
        "RUST_FLAGS := $(INHERITED_RUST_FLAGS) -D warnings $(RUST_FLAGS)" in makefile
    ), "expected generated Makefile flags to append inherited RUSTFLAGS"
    assert "DEV_CODEGEN_FLAGS ?= -Zthreads=8 -Zcodegen-backend=cranelift" in makefile, (
        "expected generated Makefile to route the development backend through "
        "rustc flags"
    )
    assert (
        "DEV_RUST_FLAGS ?= $(RUST_FLAGS) $(POLONIUS_FLAGS) $(DEV_CODEGEN_FLAGS) "
        "$(DEV_LINKER_FLAGS)" in makefile
    ), "expected generated development flags to compose codegen and linker flags"
    preflights = {
        "test": "check-build-tools",
        "test-ui": "check-build-tools",
        "typecheck": "check-build-tools",
        "lint": "check-build-tools",
        "coverage": "check-coverage-tools",
        "fmt": "check-rust-toolchain",
        "check-fmt": "check-rust-toolchain",
        "target/debug/$(TARGET)": "check-build-tools",
    }
    for target, prerequisite in preflights.items():
        rules = re.findall(
            rf"^{re.escape(target)}:([^\n]*)", makefile, flags=re.MULTILINE
        )
        assert any(prerequisite in rule.split() for rule in rules), (
            f"expected generated {target} target to preflight {prerequisite} "
            "before compiling"
        )
    release_rules = re.findall(r"^release:([^\n]*)", makefile, flags=re.MULTILINE)
    assert len(release_rules) == 1, (
        "expected generated Makefile to define one release rule"
    )
    release_prerequisites = release_rules[0].split()
    assert "target/release/$(TARGET)" in release_prerequisites, (
        "expected generated release target to build the release binary"
    )
    if "check-rust-toolchain" in release_prerequisites:
        assert release_prerequisites.index(
            "check-rust-toolchain"
        ) < release_prerequisites.index("target/release/$(TARGET)"), (
            "expected generated release target to preflight the toolchain before "
            "compiling"
        )
    assert (
        "CV005_CONTRACTS_REF ?= 38905b4b2caec5b049438e6dc3f3f6b36c04d2df"
    ) in makefile, (
        "expected generated Makefile to pin the shared workflow contract checker"
    )
    assert (
        "git+https://github.com/leynos/shared-actions@$(CV005_CONTRACTS_REF)"
        "\\#subdirectory=packages/cv005-contracts"
    ) in makefile, (
        "expected the generated checker to resolve from the pinned shared revision"
    )
    assert "$(CV005_CONTRACTS) check --repository ." in makefile, (
        "expected generated Makefile to run the pinned shared CV-005 checker"
    )
    assert "test-workflow-contracts: ## Check the shared CV-005 workflow contracts" in (
        makefile
    ), "expected generated Makefile to expose the workflow contract target"
    assert "all: check-fmt lint test test-workflow-contracts" in makefile, (
        "expected the comprehensive gate to run the workflow contract checker"
    )
    assert "MDTABLEFIX ?= mdtablefix" in makefile, (
        "expected generated Makefile to name the Markdown formatter as an "
        "overridable tool"
    )
    assert "MDTABLEFIX_SELECT = --git --include-untracked" in makefile, (
        "expected generated Markdown formatting to select Git-visible files"
    )
    assert "MDTABLEFIX_RULES = --wrap --renumber --breaks --ellipsis --fences" in (
        makefile
    ), "expected generated Markdown formatting to use the shared rule set"
    assert (
        "$(MDTABLEFIX) --in-place $(MDTABLEFIX_SELECT) $(MDTABLEFIX_RULES)" in makefile
    ), "expected generated fmt target to rewrite the selected Markdown in place"
    assert (
        "$(MDTABLEFIX) --check $(MDTABLEFIX_SELECT) $(MDTABLEFIX_RULES)" in makefile
    ), "expected generated check-fmt target to verify the selected Markdown"
    assert "mdformat-all" not in makefile, (
        "expected generated Makefile to drop the undeclared formatter wrapper"
    )
    assert "UI_TEST_TARGETS :=" in makefile, (
        "expected generated Makefile to define the UI test target list"
    )
    assert "tests/compile_*.rs" in makefile, (
        "expected generated Makefile to discover compile-time UI test targets"
    )
    assert (
        "UI_TEST_CMD := $(if $(filter nextest run,$(TEST_CMD)),"
        "$(TEST_CMD) --profile ui,$(TEST_CMD))" in makefile
    ), "expected generated test-ui target to select the serialized nextest profile"
    assert (
        'PATH="$(BUILD_TOOLS_PATH)" RUSTFLAGS="$(DEV_RUST_FLAGS)" $(CARGO) '
        "$(UI_TEST_CMD) $(addprefix --test ,$(UI_TEST_TARGETS))" in makefile
    ), "expected generated test-ui target to run the discovered targets"
    assert (
        'CHECK_BUILD_TOOLS ?= PATH="$(BUILD_TOOLS_PATH)" scripts/check-build-tools.sh'
    ) in makefile, (
        "expected generated capability preflight to be overridable and to run "
        "the checker rather than an installer"
    )
    assert (
        'BUILD_TOOLS_PREFIX="$(BUILD_TOOLS_PREFIX)" scripts/install-build-tools.sh'
    ) in makefile, "expected generated Makefile to expose the pinned tool installer"
    assert 'RUSTFLAGS="$(RELEASE_RUST_FLAGS)" $(RELEASE_CARGO) build' in makefile, (
        "expected generated release target to keep its flag route free of the "
        "development codegen backend"
    )


def _load_and_parse_makefile_rules(makefile: str) -> dict[str, list[str]]:
    """Return generated Makefile rules parsed through make-parser."""
    target_names = set(
        re.findall(r"^([a-zA-Z][a-zA-Z_-]*):", makefile, flags=re.MULTILINE)
    )
    normalized_targets = {
        target: target.replace("-", "_") for target in target_names if "-" in target
    }

    def normalize_target(match: re.Match[str]) -> str:
        """Rewrite a hyphenated target name with underscores, keeping the colon.

        A name without a hyphen is returned unchanged.
        """
        target = cast("str", match.group(1))
        return normalized_targets.get(target, target) + ":"

    normalized_makefile = re.sub(
        r"^([a-zA-Z][a-zA-Z_-]*):",
        normalize_target,
        makefile.replace("?=", "="),
        flags=re.MULTILINE,
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        makefile_path = Path(tmp_dir) / "Makefile"
        makefile_path.write_text(normalized_makefile, encoding="utf-8")
        make_load = import_module("make_parser").make_load
        parsed = cast("dict[str, Any]", make_load(makefile_path))
    normalized_rules = cast("dict[str, dict[str, list[str]]]", parsed["rules"])
    return {
        target: normalized_rules[normalized_targets.get(target, target)]["commands"]
        for target in target_names
        if normalized_targets.get(target, target) in normalized_rules
    }
