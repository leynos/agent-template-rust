"""Assert rendered Makefile contracts for generated Rust projects."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import make_parser

from tests.helpers.rendering import LIB


def _assert_makefile_contracts(makefile: str, flavour: str) -> None:
    """Assert generated Makefile tooling contracts."""
    makefile_rules = _load_and_parse_makefile_rules(makefile)
    for target in [
        "all",
        "audit",
        "build",
        "check-fmt",
        "coverage",
        "fmt",
        "lint",
        "markdownlint",
        "nixie",
        "rust-audit",
        "test",
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
    if flavour == LIB:
        assert "$(CARGO) test --doc --workspace --all-features" in makefile, (
            "expected generated library Makefile test target to run doctests"
        )
    assert "coverage: ## Generate lcov coverage with lld" in makefile, (
        "expected generated Makefile to include an lld-backed coverage target"
    )
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


def _load_and_parse_makefile_rules(makefile: str) -> dict[str, list[str]]:
    """Return generated Makefile rules parsed through make-parser."""
    target_names = set(
        re.findall(r"^([a-zA-Z][a-zA-Z_-]*):", makefile, flags=re.MULTILINE)
    )
    normalised_targets = {
        target: target.replace("-", "_") for target in target_names if "-" in target
    }

    def normalise_target(match: re.Match[str]) -> str:
        target = match.group(1)
        return normalised_targets.get(target, target) + ":"

    normalised_makefile = re.sub(
        r"^([a-zA-Z][a-zA-Z_-]*):",
        normalise_target,
        makefile.replace("?=", "="),
        flags=re.MULTILINE,
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        makefile_path = Path(tmp_dir) / "Makefile"
        makefile_path.write_text(normalised_makefile, encoding="utf-8")
        parsed = make_parser.make_load(makefile_path)
    normalised_rules = parsed["rules"]
    return {
        target: normalised_rules[normalised_targets.get(target, target)]["commands"]
        for target in target_names
        if normalised_targets.get(target, target) in normalised_rules
    }
