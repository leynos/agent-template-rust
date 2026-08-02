"""Rendered tooling contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import (
    parse_toml_file,
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
    require_optional_mapping,
    require_sequence,
)
from tests.helpers.rendering import APP, LIB, render_project
from tests.helpers.tooling_contracts import (
    assert_coverage_main_workflow_contract,
    assert_generated_tooling_contracts,
    assert_polonius_toolchain_contracts,
)
from tests.helpers.tooling_contracts.polonius import (
    _assert_coverage_workflow,
    _assert_release_workflow,
    _assert_setup_rust_rustflags,
    _assert_shared_action_passthrough_revision,
)
from tests.helpers.tooling_contracts.workflows import _assert_ci_workflow_contracts

POLONIUS_RENDER_CASES = tuple(
    (flavour, enable_polonius, dev_target)
    for flavour in (LIB, APP)
    for enable_polonius in (None, False, True)
    for dev_target in (
        "x86_64-unknown-linux-gnu",
        "aarch64-apple-darwin",
        "",
    )
)


def test_polonius_contract_rejects_stale_shared_action_revision() -> None:
    """Reject a shared action revision without the rustflags passthrough."""
    workflow = "uses: leynos/shared-actions/.github/actions/setup-rust@" + "0" * 40

    with pytest.raises(AssertionError, match="rustflags passthrough revision"):
        _assert_shared_action_passthrough_revision(workflow, "CI workflow")


def test_polonius_contract_allows_independent_shared_action_revision() -> None:
    """Allow unrelated shared actions to advance independently."""
    workflow = """uses: leynos/shared-actions/.github/actions/setup-rust@47b337e4f230b591891656534d4ffad868131740
uses: leynos/shared-actions/.github/actions/generate-coverage@0000000000000000000000000000000000000000
"""

    _assert_shared_action_passthrough_revision(workflow, "CI workflow")


def test_polonius_contract_rejects_missing_setup_rustflags() -> None:
    """Reject setup-rust when its rustflags input is absent."""
    workflow = """jobs:
  build-test:
    steps:
      - uses: leynos/shared-actions/.github/actions/setup-rust@47b337e4f230b591891656534d4ffad868131740
        with: {}
"""

    with pytest.raises(AssertionError, match="setup-rust rustflags"):
        _assert_setup_rust_rustflags(workflow, "build-test", enabled=True)


def test_polonius_contract_rejects_incorrect_coverage_log() -> None:
    """Reject a coverage diagnostic that reports the wrong flags."""
    workflow = """jobs:
  build-test:
    steps:
      - name: Log coverage linker configuration
        run: |
          echo "Coverage RUSTFLAGS: -D warnings"
      - name: Test and Measure Coverage
        env:
          RUSTFLAGS: -Zpolonius=next -C link-arg=-fuse-ld=lld
"""

    with pytest.raises(AssertionError, match="coverage log"):
        _assert_coverage_workflow(workflow, "build-test", enabled=True)


def test_polonius_contract_rejects_release_rustflags_env_override() -> None:
    """Reject a release build step that overrides setup-rust flags."""
    workflow = """jobs:
  build:
    steps:
      - uses: leynos/shared-actions/.github/actions/setup-rust@47b337e4f230b591891656534d4ffad868131740
        with:
          toolchain: nightly-2025-06-10
          rustflags: -Zpolonius=next
      - name: Log Rust compiler configuration
        run: |
          rustc --version
          printf 'Base RUSTFLAGS: %s\\n' "$RUSTFLAGS"
      - name: Build release binary
        env:
          RUSTFLAGS: -D warnings
        run: cross +nightly-2025-06-10 build --release
"""

    with pytest.raises(AssertionError, match="release build env to be absent"):
        _assert_release_workflow(
            workflow,
            '[toolchain]\nchannel = "nightly-2025-06-10"\n',
            enabled=True,
        )


@pytest.mark.parametrize(
    ("flavour", "dev_target", "enable_polonius"),
    [
        (LIB, "x86_64-unknown-linux-gnu", False),
        (APP, "x86_64-unknown-linux-gnu", True),
        (LIB, "aarch64-apple-darwin", True),
        (APP, "x86_64-unknown-linux-gnu", False),
    ],
)
def test_generated_tooling_contracts(
    tmp_path: Path,
    copier: CopierFixture,
    flavour: str,
    dev_target: str,
    enable_polonius: bool,
) -> None:
    """Generated projects include the requested Rust tooling contracts."""
    project = render_project(
        tmp_path,
        copier,
        project_name="ToolingExample",
        package_name="tooling_example",
        flavour=flavour,
        enable_polonius=enable_polonius,
        dev_target=dev_target,
    )

    project.run("make all")
    project.run("mbake validate Makefile")
    project.run("cargo metadata --format-version=1 --no-deps")

    cargo = parse_toml_file(project / "Cargo.toml")
    package = require_mapping(cargo, "package", "Cargo.toml")
    metadata = require_optional_mapping(package, "metadata", "Cargo.toml package")
    makefile = read_generated_text(project / "Makefile")
    cargo_config = read_generated_text(project / ".cargo/config.toml")
    ci_workflow = read_generated_text(project / ".github/workflows/ci.yml")
    audit_workflow = read_generated_text(project / ".github/workflows/audit.yml")
    act_workflow = read_generated_text(project / ".github/workflows/act-validation.yml")
    coverage_main_workflow = read_generated_text(
        project / ".github/workflows/coverage-main.yml"
    )
    mutation_workflow = read_generated_text(
        project / ".github/workflows/mutation-testing.yml"
    )
    docs_contents = read_generated_text(project / "docs/contents.md")
    developers_guide = read_generated_text(project / "docs/developers-guide.md")
    repository_layout = read_generated_text(project / "docs/repository-layout.md")
    readme = read_generated_text(project / "README.md")
    users_guide = read_generated_text(project / "docs/users-guide.md")
    agents = read_generated_text(project / "AGENTS.md")
    rust_toolchain = read_generated_text(project / "rust-toolchain.toml")
    test_stub = read_generated_text(project / "tests/stub.rs")
    typos_config = read_generated_text(project / "typos.toml")
    typos_overlay = read_generated_text(project / "typos.local.toml")
    spelling_generator = read_generated_text(
        project / "scripts/generate_typos_config.py"
    )
    spelling_core = read_generated_text(project / "scripts/typos_rollout.py")
    parsed_ci_workflow = parse_yaml_mapping(ci_workflow, "CI workflow")

    release_workflow = (
        read_generated_text(project / ".github/workflows/release.yml")
        if flavour == APP
        else None
    )
    polonius_path = project / "docs/polonius.md"
    polonius_doc = (
        read_generated_text(polonius_path) if polonius_path.exists() else None
    )
    assert_generated_tooling_contracts(
        package=package,
        metadata=metadata,
        flavour=flavour,
        makefile=makefile,
        cargo_config=cargo_config,
        dev_target=dev_target,
        rust_toolchain=rust_toolchain,
        parsed_ci_workflow=parsed_ci_workflow,
        ci_workflow=ci_workflow,
        audit_workflow=audit_workflow,
        act_workflow=act_workflow,
        mutation_workflow=mutation_workflow,
        docs_contents=docs_contents,
        repository_layout=repository_layout,
        readme=readme,
        test_stub=test_stub,
        release_workflow=release_workflow,
    )
    assert_coverage_main_workflow_contract(coverage_main_workflow)
    assert_polonius_toolchain_contracts(
        enabled=enable_polonius,
        dev_target=dev_target,
        cargo_config=cargo_config,
        makefile=makefile,
        rust_toolchain=rust_toolchain,
        ci_workflow=ci_workflow,
        coverage_main_workflow=coverage_main_workflow,
        release_workflow=release_workflow,
        agents=agents,
        readme=readme,
        docs_contents=docs_contents,
        repository_layout=repository_layout,
        developers_guide=developers_guide,
        users_guide=users_guide,
        polonius_doc=polonius_doc,
    )
    assert '[default]\nlocale = "en-gb"' in typos_config
    assert 'accepted = ["Flavored", "mold", "Polonius"]' in typos_overlay
    assert "DEFAULT_BASE_URL" in spelling_generator
    assert "_local_cache_is_current" in spelling_core


@given(case=st.sampled_from(POLONIUS_RENDER_CASES))
@settings(
    deadline=None,
    max_examples=len(POLONIUS_RENDER_CASES),
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_polonius_flag_invariant_across_rendered_configuration_space(
    tmp_path_factory: pytest.TempPathFactory,
    copier: CopierFixture,
    case: tuple[str, bool | None, str],
) -> None:
    """Every rendered RUSTFLAGS override preserves the selected Polonius state."""
    flavour, enable_polonius, dev_target = case
    project = render_project(
        tmp_path_factory.mktemp("polonius-contract"),
        copier,
        project_name="InvariantProperty",
        package_name="invariant_property",
        flavour=flavour,
        enable_polonius=enable_polonius,
        dev_target=dev_target,
    )
    expected_enabled = flavour == APP if enable_polonius is None else enable_polonius
    release_path = project / ".github/workflows/release.yml"
    polonius_path = project / "docs/polonius.md"

    assert_polonius_toolchain_contracts(
        enabled=expected_enabled,
        dev_target=dev_target,
        cargo_config=read_generated_text(project / ".cargo/config.toml"),
        makefile=read_generated_text(project / "Makefile"),
        rust_toolchain=read_generated_text(project / "rust-toolchain.toml"),
        ci_workflow=read_generated_text(project / ".github/workflows/ci.yml"),
        coverage_main_workflow=read_generated_text(
            project / ".github/workflows/coverage-main.yml"
        ),
        release_workflow=(
            read_generated_text(release_path) if release_path.exists() else None
        ),
        agents=read_generated_text(project / "AGENTS.md"),
        readme=read_generated_text(project / "README.md"),
        docs_contents=read_generated_text(project / "docs/contents.md"),
        repository_layout=read_generated_text(project / "docs/repository-layout.md"),
        developers_guide=read_generated_text(project / "docs/developers-guide.md"),
        users_guide=read_generated_text(project / "docs/users-guide.md"),
        polonius_doc=(
            read_generated_text(polonius_path) if polonius_path.exists() else None
        ),
    )


def test_ci_contract_rejects_unguarded_duplicate_audit_step(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Reject a duplicate audit step that would run on Dependabot pull requests."""
    project = render_project(
        tmp_path,
        copier,
        project_name="ToolingExample",
        package_name="tooling_example",
        flavour=APP,
    )
    ci_workflow = read_generated_text(project / ".github/workflows/ci.yml")
    act_workflow = read_generated_text(project / ".github/workflows/act-validation.yml")
    test_stub = read_generated_text(project / "tests/stub.rs")
    parsed_ci_workflow = parse_yaml_mapping(ci_workflow, "CI workflow")

    jobs = require_mapping(parsed_ci_workflow, "jobs", "CI workflow")
    build_test = require_mapping(jobs, "build-test", "CI workflow jobs")
    steps = require_sequence(build_test, "steps", "CI build-test job")
    steps.append({"name": "Audit dependencies", "run": "make audit"})

    with pytest.raises(
        AssertionError, match="each audit-specific CI step exactly once"
    ):
        _assert_ci_workflow_contracts(
            parsed_ci_workflow, ci_workflow, act_workflow, test_stub
        )
