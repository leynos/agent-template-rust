"""Assert rendered tooling contracts for generated Rust project variants."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

import make_parser

from tests.helpers.generated_files import (
    parse_yaml_mapping,
    require_mapping,
    require_sequence,
)
from tests.helpers.rendering import APP


def assert_documentation_navigation_contracts(
    docs_contents: str, repository_layout: str, flavour: str
) -> None:
    """Assert generated documentation navigation and layout contracts."""
    assert "[Documentation contents](contents.md)" in docs_contents, (
        "expected generated contents file to link to itself"
    )
    assert "[Repository layout](repository-layout.md)" in docs_contents, (
        "expected generated contents file to link to the layout reference"
    )
    assert "[Documentation style guide](documentation-style-guide.md)" in (
        docs_contents
    ), "expected generated contents file to link to the style guide"
    assert "docs/contents.md" in repository_layout, (
        "expected generated layout to document the contents file"
    )
    assert "docs/repository-layout.md" in repository_layout, (
        "expected generated layout to document itself"
    )
    assert "Cargo.toml" in repository_layout, (
        "expected generated layout to document Cargo metadata"
    )
    assert "Makefile" in repository_layout, (
        "expected generated layout to document public command entrypoints"
    )
    assert "checks. - `" not in repository_layout, (
        "expected generated layout bullets to render on separate lines"
    )
    assert "responsibilities. - `" not in repository_layout, (
        "expected generated layout flavour bullets to render on separate lines"
    )

    if flavour == APP:
        assert ".github/workflows/release.yml" in repository_layout, (
            "expected app layout to document the release workflow"
        )
        assert "src/main.rs" in repository_layout, (
            "expected app layout to document the executable entrypoint"
        )
        assert "src/lib.rs" not in repository_layout, (
            "expected app layout to omit the library crate root"
        )
    else:
        assert ".github/workflows/release.yml" not in repository_layout, (
            "expected lib layout to omit the app release workflow"
        )
        assert "src/lib.rs" in repository_layout, (
            "expected lib layout to document the library crate root"
        )
        assert "src/main.rs" not in repository_layout, (
            "expected lib layout to omit the executable entrypoint"
        )


def assert_generated_tooling_contracts(
    *,
    package: dict[str, Any],
    metadata: dict[str, Any],
    flavour: str,
    makefile: str,
    cargo_config: str,
    dev_target: str,
    rust_toolchain: str,
    parsed_ci_workflow: dict[str, Any],
    ci_workflow: str,
    docs_contents: str,
    repository_layout: str,
    readme: str,
    test_stub: str,
    release_workflow: str | None,
) -> None:
    """Assert generated tooling contracts from a single validator."""
    _assert_cargo_package_contracts(package, metadata, flavour)
    _assert_makefile_contracts(makefile, flavour)
    _assert_cargo_config_contracts(cargo_config, dev_target, rust_toolchain)
    _assert_ci_workflow_contracts(parsed_ci_workflow, ci_workflow, test_stub)
    assert_documentation_navigation_contracts(
        docs_contents, repository_layout, flavour
    )
    assert "[Documentation contents](docs/contents.md)" in readme, (
        "expected generated README to link to the documentation contents"
    )
    assert "[User guide](docs/users-guide.md)" in readme, (
        "expected generated README to link to the user guide"
    )
    assert "[Developer guide](docs/developers-guide.md)" in readme, (
        "expected generated README to link to the developer guide"
    )
    if release_workflow is not None:
        _assert_release_workflow_contracts(release_workflow)


def assert_ci_coverage_action_contract(ci_workflow: str) -> None:
    """Assert generated CI coverage inputs used by act validation."""
    parsed_ci_workflow = parse_yaml_mapping(ci_workflow, "CI workflow")
    jobs = require_mapping(parsed_ci_workflow, "jobs", "CI workflow")
    build_test = require_mapping(jobs, "build-test", "CI workflow jobs")
    steps = require_sequence(build_test, "steps", "CI build-test job")
    checkout_steps = [
        step
        for step in steps
        if isinstance(step, dict)
        and str(step.get("uses", "")).startswith("actions/checkout@")
    ]
    assert checkout_steps, "expected CI checkout steps"
    assert all(
        isinstance(step.get("with"), dict)
        and step["with"].get("persist-credentials") is False
        for step in checkout_steps
    ), "expected CI checkout steps to disable credential persistence"
    coverage_steps = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == "Test and Measure Coverage"
    ]
    assert len(coverage_steps) == 1, "expected one shared coverage action step"
    coverage_step = coverage_steps[0]
    assert (
        coverage_step.get("uses")
        == "leynos/shared-actions/.github/actions/generate-coverage"
        "@e4c6b0e200a057edf927c45c298e7ddf229b3934"
    ), "expected CI to use the pinned shared coverage action"
    coverage_inputs = require_mapping(coverage_step, "with", "coverage step")
    assert coverage_inputs.get("output-path") == "lcov.info", (
        "expected CI coverage output path to match the act assertion"
    )
    assert coverage_inputs.get("format") == "lcov", (
        "expected CI coverage format to match the CodeScene upload"
    )


def _assert_cargo_package_contracts(
    package: dict[str, Any], metadata: dict[str, Any], flavour: str
) -> None:
    """Assert generated Cargo package metadata contracts."""
    assert package.get("description") == "ToolingExample package used by template tests.", (
        "expected generated Cargo.toml to include package description"
    )
    assert package.get("repository") == "https://github.com/example/tooling_example", (
        "expected generated Cargo.toml to include repository URL"
    )
    assert package.get("homepage") == "https://example.com/tooling_example", (
        "expected generated Cargo.toml to include homepage URL"
    )
    assert package.get("keywords") == ["rust", "template"], (
        "expected generated Cargo.toml to include package keywords"
    )
    assert package.get("categories") == ["development-tools"], (
        "expected generated Cargo.toml to include package categories"
    )
    assert package.get("license") == "ISC", (
        "expected generated Cargo.toml to include ISC licence"
    )

    if flavour == APP:
        binstall = metadata.get("binstall")
        assert isinstance(binstall, dict), (
            "expected app flavour Cargo.toml to include binstall metadata"
        )
        assert (
            binstall.get("pkg-url")
            == "https://github.com/example/tooling_example/releases/download/"
            "v{ version }/tooling_example-{ target }{ binary-ext }"
        ), "expected app flavour binstall metadata to include package URL"
        assert binstall.get("pkg-fmt") == "bin", (
            "expected app flavour binstall metadata to describe binary artifacts"
        )
        assert binstall.get("disabled-strategies") == ["quick-install", "compile"], (
            "expected app flavour binstall metadata to disable unsupported strategies"
        )
    else:
        assert "binstall" not in metadata, (
            "expected lib flavour Cargo.toml to omit binstall metadata"
        )


def _assert_makefile_contracts(makefile: str, flavour: str) -> None:
    """Assert generated Makefile tooling contracts."""
    makefile_rules = _parse_makefile_rules(makefile)
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
    if flavour != APP:
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
    assert 'printf "Auditing Rust workspace %s\\n" "$$workspace_root"' in makefile, (
        "expected generated audit target to log the derived workspace root"
    )
    assert 'printf "Workspace Rust manifest %s\\n"' in makefile, (
        "expected generated audit target to log workspace member manifests"
    )
    assert '(cd "$$workspace_root" && $(CARGO) audit)' in makefile, (
        "expected generated audit target to run cargo audit once at workspace root"
    )


def _assert_cargo_config_contracts(
    cargo_config: str, dev_target: str, rust_toolchain: str
) -> None:
    """Assert generated Cargo config and toolchain contracts."""
    assert 'codegen-backend = "cranelift"' in cargo_config, (
        "expected generated cargo config to enable Cranelift"
    )
    if "linux" in dev_target:
        assert f"[target.{dev_target}]" in cargo_config, (
            "expected generated cargo config to include Linux target settings"
        )
        assert 'link-arg=-fuse-ld=mold' in cargo_config, (
            "expected generated cargo config to use mold linker for Linux"
        )
    else:
        assert f"[target.{dev_target}]" not in cargo_config, (
            "expected generated cargo config to avoid mold target blocks "
            "for non-Linux targets"
        )
        assert 'link-arg=-fuse-ld=mold' not in cargo_config, (
            "expected generated cargo config to avoid mold for non-Linux targets"
        )

    assert "rustc-codegen-cranelift-preview" in rust_toolchain, (
        "expected generated rust-toolchain to include Cranelift component"
    )
    assert "llvm-tools-preview" in rust_toolchain, (
        "expected generated rust-toolchain to include llvm tools component"
    )


def _assert_ci_workflow_contracts(
    parsed_ci_workflow: dict[str, Any],
    ci_workflow: str,
    test_stub: str,
) -> None:
    """Assert generated CI workflow and adjacent documentation contracts."""
    jobs = require_mapping(parsed_ci_workflow, "jobs", "CI workflow")
    assert "act-validation" in jobs, (
        "expected generated CI workflow to include a separate act-validation job"
    )
    act_validation = require_mapping(jobs, "act-validation", "CI workflow jobs")
    act_steps = require_sequence(act_validation, "steps", "CI act-validation job")
    assert any(
        isinstance(step, dict)
        and isinstance(step.get("with"), dict)
        and step["with"].get("persist-credentials") is False
        for step in act_steps
    ), "expected generated act-validation job checkout to disable credentials"
    assert "ACT_VERSION: v0.2.80" in ci_workflow, (
        "expected generated CI workflow to pin the act release"
    )
    assert "act_Linux_x86_64.tar.gz" in ci_workflow, (
        "expected generated CI workflow to install the act Linux binary"
    )
    assert "docker info" in ci_workflow, (
        "expected generated CI workflow to verify Docker before act validation"
    )
    assert "make test WITH_ACT=1" in ci_workflow, (
        "expected generated CI workflow to run an act-enabled test gate"
    )
    checkout_steps = extract_checkout_steps(jobs)
    assert checkout_steps, "expected generated CI workflow to check out sources"
    assert all(
        step.get("with", {}).get("persist-credentials") is False
        for step in checkout_steps
    ), "expected generated CI checkout steps to disable credential persistence"

    assert "Cache Whitaker installation" in ci_workflow, (
        "expected generated CI workflow to cache Whitaker installation"
    )
    assert (
        "leynos/shared-actions/.github/actions/setup-rust"
        "@e4c6b0e200a057edf927c45c298e7ddf229b3934" in ci_workflow
    ), "expected generated CI workflow to use the pinned shared setup-rust action"
    assert "cargo-nextest" in ci_workflow, (
        "expected generated CI workflow to install cargo-nextest"
    )
    assert "cargo binstall --no-confirm cargo-audit" in ci_workflow, (
        "expected generated CI workflow to install cargo-audit"
    )
    assert "Setup Python for audit manifest extraction" in ci_workflow, (
        "expected generated CI workflow to install Python for audit metadata parsing"
    )
    assert "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405" in (
        ci_workflow
    ), "expected generated CI workflow to pin setup-python for audit parsing"
    assert "make audit" in ci_workflow, (
        "expected generated CI workflow to run the dependency audit gate"
    )
    assert "coverage uses lld for llvm-tools compatibility" in ci_workflow, (
        "expected generated CI workflow to document mold and lld roles"
    )
    assert "clang lld mold" in ci_workflow, (
        "expected generated CI workflow to install clang, lld, and mold"
    )
    assert "fuse-ld=lld" in ci_workflow, (
        "expected generated CI workflow coverage to use lld linker flags"
    )
    assert "CFLAGS: -fuse-ld=lld" in ci_workflow, (
        "expected generated CI workflow coverage to set CFLAGS for lld"
    )
    assert "LDFLAGS: -fuse-ld=lld" in ci_workflow, (
        "expected generated CI workflow coverage to set LDFLAGS for lld"
    )
    assert "Whitaker cache hit:" in ci_workflow, (
        "expected generated CI workflow to log Whitaker cache status"
    )
    assert "Installing Whitaker installer at" in ci_workflow, (
        "expected generated CI workflow to log Whitaker installation"
    )
    assert "Whitaker binary:" in ci_workflow, (
        "expected generated CI workflow to log Whitaker binary resolution"
    )
    assert "Log coverage linker configuration" in ci_workflow, (
        "expected generated CI workflow to log coverage linker configuration"
    )

    assert "Delete this file as soon as the project has real" in test_stub, (
        "expected generated test stub to explain when to delete it"
    )


def _assert_release_workflow_contracts(release_workflow: str) -> None:
    """Assert generated release workflow contracts."""
    parsed_release_workflow = parse_yaml_mapping(release_workflow, "release workflow")
    jobs = require_mapping(parsed_release_workflow, "jobs", "release workflow")
    release_checkout_steps = extract_checkout_steps(jobs)
    assert release_checkout_steps, "expected app release workflow to check out sources"
    assert all(
        step.get("with", {}).get("persist-credentials") is False
        for step in release_checkout_steps
    ), "expected release workflow checkout steps to disable credentials"
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
        in release_workflow
    ), "expected app release workflow to use pinned upload-artifact action"
    cross_revision = "88f49ff79e777bef6d3564531636ee4d3cc2f8d2"
    assert f"CROSS_REVISION: {cross_revision}" in release_workflow, (
        "expected app release workflow to pin cross to an immutable revision"
    )
    assert 'cargo install cross --git https://github.com/cross-rs/cross --rev "$' in (
        release_workflow
    ), "expected app release workflow to install cross by immutable revision"
    assert "--tag" not in release_workflow, (
        "expected app release workflow not to install cross by mutable tag"
    )
    assert "aarch64-pc-windows-gnullvm" not in release_workflow, (
        "expected app release workflow to omit unsupported cross targets"
    )
    assert 'key: cross-${{ env.CROSS_REVISION }}' in release_workflow, (
        "expected app release workflow to cache cross by revision"
    )
    assert "files: |" in release_workflow, (
        "expected app release workflow to upload release files"
    )


def extract_checkout_steps(jobs: dict[str, Any]) -> list[dict[str, Any]]:
    """Return checkout steps from a parsed GitHub Actions jobs mapping."""
    return [
        step
        for job in jobs.values()
        if isinstance(job, dict)
        for step in job.get("steps", [])
        if isinstance(step, dict)
        and step.get("uses", "").startswith("actions/checkout@")
    ]


def _parse_makefile_rules(makefile: str) -> dict[str, list[str]]:
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
