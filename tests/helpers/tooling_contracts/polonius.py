"""Assert rendered Polonius toolchain and documentation contracts."""

from __future__ import annotations

import re
import tomllib
from typing import Any

from tests.helpers.generated_files import (
    parse_yaml_mapping,
    require_mapping,
    require_sequence,
)

POLONIUS_FLAG = "-Zpolonius=next"
RUSTFLAGS_PASSTHROUGH_REVISION = "47b337e4f230b591891656534d4ffad868131740"
_SETUP_RUST_USES_RE = re.compile(
    r"^leynos/shared-actions/\.github/actions/setup-rust@[0-9a-f]{40}$"
)
_SHARED_ACTION_USES_RE = re.compile(
    r"uses:\s+(?P<reference>leynos/shared-actions/[^\s]+)"
)


def _named_step(workflow: str, job_name: str, step_name: str) -> dict[str, Any]:
    """Return one named step from a rendered workflow."""
    parsed = parse_yaml_mapping(workflow, f"{job_name} workflow")
    jobs = require_mapping(parsed, "jobs", f"{job_name} workflow")
    job = require_mapping(jobs, job_name, f"{job_name} workflow jobs")
    steps = require_sequence(job, "steps", f"{job_name} workflow job")
    matches = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == step_name
    ]
    assert len(matches) == 1, f"expected one {step_name!r} step in {job_name}"
    return matches[0]


def _setup_rust_step(workflow: str, job_name: str) -> dict[str, Any]:
    """Return the setup-rust step from a rendered workflow job."""
    parsed = parse_yaml_mapping(workflow, f"{job_name} workflow")
    jobs = require_mapping(parsed, "jobs", f"{job_name} workflow")
    job = require_mapping(jobs, job_name, f"{job_name} workflow jobs")
    steps = require_sequence(job, "steps", f"{job_name} job")
    matches = [
        step
        for step in steps
        if isinstance(step, dict)
        and _SETUP_RUST_USES_RE.fullmatch(str(step.get("uses", "")))
    ]
    assert len(matches) == 1, f"expected one setup-rust step in {job_name} workflow"
    return matches[0]

def _assert_setup_rust_rustflags(
    workflow: str, job_name: str, *, enabled: bool
) -> None:
    """Assert setup-rust receives the selected Polonius configuration."""
    setup = _setup_rust_step(workflow, job_name)
    setup_inputs = require_mapping(setup, "with", f"{job_name} setup-rust step")
    expected = POLONIUS_FLAG if enabled else "-D warnings"
    actual = setup_inputs.get("rustflags")
    assert actual == expected, (
        f"expected {job_name} setup-rust rustflags to be {expected!r}, got {actual!r}"
    )
def _assert_cargo_config(cargo_config: str, *, enabled: bool, dev_target: str) -> None:
    """Assert Cargo's build and target rustflags retain Polonius as required."""
    config = tomllib.loads(cargo_config)
    build_flags = config.get("build", {}).get("rustflags", [])
    rustdoc_flags = config.get("build", {}).get("rustdocflags", [])
    assert (POLONIUS_FLAG in build_flags) is enabled, (
        "expected build.rustflags Polonius state to match the Copier answer"
    )
    assert (POLONIUS_FLAG in rustdoc_flags) is enabled, (
        "expected build.rustdocflags Polonius state to match the Copier answer"
    )
    if "linux" not in dev_target:
        return
    target_flags = config["target"][dev_target]["rustflags"]
    assert (POLONIUS_FLAG in target_flags) is enabled, (
        "target rustflags override build.rustflags and must preserve the "
        "selected Polonius state"
    )


def _assert_makefile(makefile: str, *, enabled: bool, dev_target: str) -> None:
    """Assert every generated compile path preserves the selected flag."""
    expected_default = (
        f"POLONIUS_FLAGS ?= {POLONIUS_FLAG}" if enabled else "POLONIUS_FLAGS ?="
    )
    assert expected_default in makefile
    assert (
        "COVERAGE_RUST_FLAGS ?= $(RUST_FLAGS) $(POLONIUS_FLAGS) "
        "-C link-arg=$(COVERAGE_LINKER_FLAGS)"
    ) in makefile
    assert (
        "DEV_RUST_FLAGS ?= $(RUST_FLAGS) $(POLONIUS_FLAGS) $(DEV_LINKER_FLAGS)"
        in makefile
    )
    assert "RUSTDOC_FLAGS ?=" in makefile
    assert (
        "RUSTDOC_FLAGS := --cfg docsrs -D warnings $(POLONIUS_FLAGS) $(RUSTDOC_FLAGS)"
    ) in makefile, (
        "RUSTDOC_FLAGS must require POLONIUS_FLAGS while preserving inherited flags"
    )
    linker_default = next(
        line for line in makefile.splitlines() if line.startswith("DEV_LINKER_FLAGS ?=")
    )
    if "linux" in dev_target:
        assert "$(filter Linux,$(shell uname -s))" in linker_default
        assert "-fuse-ld=mold" in linker_default
    else:
        assert linker_default == "DEV_LINKER_FLAGS ?="
    compile_lines = [
        line
        for line in makefile.splitlines()
        if "RUSTFLAGS=" in line and ("$(CARGO)" in line or "$(WHITAKER)" in line)
    ]
    assert compile_lines, "expected generated compile recipes to set RUSTFLAGS"
    assert all(
        "$(DEV_RUST_FLAGS)" in line or "$(COVERAGE_RUST_FLAGS)" in line
        for line in compile_lines
    ), f"compile recipes must use composed Rust flags: {compile_lines!r}"
    coverage_recipe = makefile.partition("coverage:")[2].partition("\n\n")[0]
    assert 'RUSTFLAGS="$(COVERAGE_RUST_FLAGS)"' in coverage_recipe, (
        "coverage recipe must use composed coverage Rust flags"
    )
    rustdoc_lines = [
        line
        for line in makefile.splitlines()
        if "$(CARGO) test --doc" in line or "$(CARGO) doc" in line
    ]
    assert len(rustdoc_lines) == 2, (
        f"expected exactly two rustdoc recipes, got: {rustdoc_lines!r}"
    )
    assert all('RUSTDOCFLAGS="$(RUSTDOC_FLAGS)"' in line for line in rustdoc_lines), (
        f"rustdoc recipes must use composed rustdoc flags: {rustdoc_lines!r}"
    )


def _assert_coverage_workflow(workflow: str, job_name: str, *, enabled: bool) -> None:
    """Assert coverage's explicit RUSTFLAGS do not shadow Polonius."""
    coverage_step = _named_step(workflow, job_name, "Test and Measure Coverage")
    env = require_mapping(coverage_step, "env", "coverage step")
    actual = str(env.get("RUSTFLAGS", ""))
    base_flags = POLONIUS_FLAG if enabled else "-D warnings"
    expected = f"{base_flags} -C link-arg=-fuse-ld=lld"
    assert actual == expected, (
        f"expected {job_name} coverage RUSTFLAGS to be {expected!r}, got {actual!r}"
    )
    log_step = _named_step(workflow, job_name, "Log coverage linker configuration")
    actual_log = str(log_step.get("run", ""))
    expected_log = f'echo "Coverage RUSTFLAGS: {expected}"'
    assert expected_log in actual_log, (
        f"expected {job_name} coverage log to contain {expected_log!r}, "
        f"got {actual_log!r}"
    )

def _assert_shared_action_passthrough_revision(
    workflow: str, workflow_name: str
) -> None:
    """Assert affected shared-action refs include the rustflags capability."""
    references = [
        match.group("reference") for match in _SHARED_ACTION_USES_RE.finditer(workflow)
    ]
    assert references, f"expected shared-action references in {workflow_name}"
    unexpected = [
        reference
        for reference in references
        if not reference.endswith(f"@{RUSTFLAGS_PASSTHROUGH_REVISION}")
    ]
    assert not unexpected, (
        f"expected {workflow_name} shared-action references to use rustflags "
        f"passthrough revision {RUSTFLAGS_PASSTHROUGH_REVISION!r}, "
        f"got {unexpected!r}"
    )
def _assert_release_workflow(
    release_workflow: str, rust_toolchain: str, *, enabled: bool
) -> None:
    """Assert release artefacts use a compiler compatible with the source."""
    toolchain_config = tomllib.loads(rust_toolchain)
    configured_toolchain = str(toolchain_config["toolchain"]["channel"])
    setup = _setup_rust_step(release_workflow, "build")
    setup_inputs = require_mapping(setup, "with", "release setup-rust step")
    actual_toolchain = str(setup_inputs.get("toolchain", ""))
    actual_rustflags = setup_inputs.get("rustflags")
    build = _named_step(release_workflow, "build", "Build release binary")
    actual_command = str(build.get("run", ""))
    actual_env = build.get("env")
    expected_toolchain = configured_toolchain if enabled else "stable"
    expected_rustflags = POLONIUS_FLAG if enabled else "-D warnings"
    expected_command = f"cross +{expected_toolchain} build"
    assert actual_toolchain == expected_toolchain, (
        f"expected release build toolchain to be {expected_toolchain!r}, "
        f"got {actual_toolchain!r}"
    )
    assert actual_rustflags == expected_rustflags, (
        f"expected release setup-rust rustflags to be {expected_rustflags!r}, "
        f"got {actual_rustflags!r}"
    )
    assert expected_command in actual_command, (
        f"expected release build command to contain {expected_command!r}, "
        f"got {actual_command!r}"
    )
    assert "env" not in build, (
        f"expected release build env to be absent, got {actual_env!r}"
    )


def assert_polonius_toolchain_contracts(
    *,
    enabled: bool,
    dev_target: str,
    cargo_config: str,
    makefile: str,
    rust_toolchain: str,
    ci_workflow: str,
    coverage_main_workflow: str,
    release_workflow: str | None,
    agents: str,
    readme: str,
    docs_contents: str,
    repository_layout: str,
    developers_guide: str,
    users_guide: str,
    polonius_doc: str | None,
) -> None:
    """Assert the selected Polonius state across generated project surfaces.

    Parameters
    ----------
    enabled : bool
        Expected Polonius selection for the rendered project.
    dev_target : str
        Development target represented in the rendered Cargo and Make files.
    cargo_config : str
        Rendered Cargo configuration.
    makefile : str
        Rendered Makefile.
    rust_toolchain : str
        Rendered Rust toolchain configuration.
    ci_workflow : str
        Rendered Continuous Integration workflow.
    coverage_main_workflow : str
        Rendered main-branch coverage workflow.
    release_workflow : str | None
        Rendered release workflow, or ``None`` when the project has none.
    agents : str
        Rendered agent guidance.
    readme : str
        Rendered project README.
    docs_contents : str
        Rendered documentation contents page.
    repository_layout : str
        Rendered repository layout documentation.
    developers_guide : str
        Rendered developers guide.
    users_guide : str
        Rendered users guide.
    polonius_doc : str | None
        Rendered Polonius policy, or ``None`` when Polonius is disabled.

    Raises
    ------
    AssertionError
        If any rendered surface does not match the selected Polonius state.
    """
    _assert_cargo_config(cargo_config, enabled=enabled, dev_target=dev_target)
    _assert_makefile(makefile, enabled=enabled, dev_target=dev_target)
    _assert_setup_rust_rustflags(ci_workflow, "build-test", enabled=enabled)
    _assert_setup_rust_rustflags(
        coverage_main_workflow, "coverage-upload", enabled=enabled
    )
    _assert_shared_action_passthrough_revision(ci_workflow, "CI workflow")
    _assert_shared_action_passthrough_revision(
        coverage_main_workflow, "coverage-main workflow"
    )
    _assert_coverage_workflow(ci_workflow, "build-test", enabled=enabled)
    _assert_coverage_workflow(
        coverage_main_workflow, "coverage-upload", enabled=enabled
    )
    if release_workflow is not None:
        _assert_shared_action_passthrough_revision(release_workflow, "release workflow")
        _assert_release_workflow(release_workflow, rust_toolchain, enabled=enabled)

    if enabled:
        assert "Polonius alpha" in rust_toolchain
        assert polonius_doc is not None
        assert POLONIUS_FLAG in polonius_doc
        for surface in (
            agents,
            readme,
            docs_contents,
            repository_layout,
            developers_guide,
            users_guide,
        ):
            assert "Polonius" in surface
    else:
        assert "Polonius" not in rust_toolchain
        assert polonius_doc is None
        for surface in (
            agents,
            readme,
            docs_contents,
            repository_layout,
            developers_guide,
            users_guide,
        ):
            assert "Polonius" not in surface
