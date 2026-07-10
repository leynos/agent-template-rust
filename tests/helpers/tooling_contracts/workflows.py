"""Assert rendered GitHub Actions contracts for generated Rust projects."""

from __future__ import annotations

from typing import Any

from tests.helpers.generated_files import (
    parse_yaml_mapping,
    require_mapping,
    require_sequence,
)


def assert_ci_coverage_action_contract(ci_workflow: str) -> None:
    """Assert generated CI coverage inputs used by act validation.

    Parameters
    ----------
    ci_workflow
        Rendered generated-project CI workflow text.

    Returns
    -------
    None
        The helper returns ``None`` when the coverage action contract passes.

    Raises
    ------
    AssertionError
        Raised when checkout credentials are persisted, the shared coverage
        action is missing or unpinned, or coverage inputs diverge from the
        expected ``lcov.info`` and ``lcov`` configuration.
    pytest.fail.Exception
        Raised by YAML parsing helpers when the workflow cannot be parsed as
        the expected mapping structure.
    """
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
        "@455d9ed03477c0026da96c2541ca26569a74acac"
    ), "expected CI to use the pinned shared coverage action"
    coverage_inputs = require_mapping(coverage_step, "with", "coverage step")
    assert coverage_inputs.get("output-path") == "lcov.info", (
        "expected CI coverage output path to match the act assertion"
    )
    assert coverage_inputs.get("format") == "lcov", (
        "expected CI coverage format to match the CodeScene upload"
    )


def _assert_ci_workflow_contracts(
    parsed_ci_workflow: dict[str, Any],
    ci_workflow: str,
    act_workflow: str,
    test_stub: str,
) -> None:
    """Assert generated CI workflow and adjacent documentation contracts."""
    jobs = require_mapping(parsed_ci_workflow, "jobs", "CI workflow")
    assert "act-validation" not in jobs, (
        "expected generated main CI workflow to keep act validation separate"
    )
    assert "ACT_VERSION: v0.2.80" not in ci_workflow, (
        "expected generated main CI workflow not to install act"
    )
    assert "act_Linux_x86_64.tar.gz" not in ci_workflow, (
        "expected generated main CI workflow not to download act"
    )
    assert "make test WITH_ACT=1" not in ci_workflow, (
        "expected generated main CI workflow not to run act validation"
    )

    parsed_act_workflow = parse_yaml_mapping(act_workflow, "act-validation workflow")
    act_jobs = require_mapping(
        parsed_act_workflow, "jobs", "act-validation workflow"
    )
    act_validation = require_mapping(
        act_jobs, "act-validation", "act-validation workflow jobs"
    )
    act_steps = require_sequence(act_validation, "steps", "CI act-validation job")
    assert any(
        isinstance(step, dict)
        and isinstance(step.get("with"), dict)
        and step["with"].get("persist-credentials") is False
        for step in act_steps
    ), "expected generated act-validation job checkout to disable credentials"
    assert "ACT_VERSION: v0.2.80" in act_workflow, (
        "expected generated act-validation workflow to pin the act release"
    )
    assert "act_Linux_x86_64.tar.gz" in act_workflow, (
        "expected generated act-validation workflow to install the act Linux binary"
    )
    assert "docker info" in act_workflow, (
        "expected generated act-validation workflow to verify Docker"
    )
    assert "make test WITH_ACT=1" in act_workflow, (
        "expected generated act-validation workflow to run an act-enabled test gate"
    )
    checkout_steps = extract_checkout_steps(jobs)
    assert checkout_steps, "expected generated CI workflow to check out sources"
    assert all(
        step.get("with", {}).get("persist-credentials") is False
        for step in checkout_steps
    ), "expected generated CI checkout steps to disable credential persistence"
    build_test = require_mapping(jobs, "build-test", "CI workflow jobs")
    steps = require_sequence(build_test, "steps", "CI build-test job")
    rust_tool_install_step_names = [
        "Install test runner",
        "Install cargo-audit",
        "Install Whitaker",
    ]
    for step_name in rust_tool_install_step_names:
        matching_steps = [
            step
            for step in steps
            if isinstance(step, dict) and step.get("name") == step_name
        ]
        assert len(matching_steps) == 1, (
            f"expected generated CI to include one {step_name} step"
        )
        rust_tool_env = require_mapping(
            matching_steps[0], "env", f"{step_name} step"
        )
        assert rust_tool_env.get("RUSTFLAGS") == "", (
            f"expected generated CI {step_name} step to clear inherited RUSTFLAGS"
        )

    assert "Cache Whitaker installation" in ci_workflow, (
        "expected generated CI workflow to cache Whitaker installation"
    )
    assert (
        "leynos/shared-actions/.github/actions/setup-rust"
        "@455d9ed03477c0026da96c2541ca26569a74acac" in ci_workflow
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
    assert "name: Check spelling" in ci_workflow, (
        "expected generated CI workflow to identify the spelling gate"
    )
    assert "run: make spelling" in ci_workflow, (
        "expected generated CI workflow to run the pinned spelling gate"
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
    assert "Installing whitaker-installer" in ci_workflow, (
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
    """Return checkout steps from a parsed GitHub Actions jobs mapping.

    Parameters
    ----------
    jobs
        Parsed GitHub Actions ``jobs`` mapping.

    Returns
    -------
    list[dict[str, Any]]
        Checkout step mappings whose ``uses`` value starts with
        ``actions/checkout@``. Jobs or steps with other shapes are ignored.
    """
    return [
        step
        for job in jobs.values()
        if isinstance(job, dict)
        for step in job.get("steps", [])
        if isinstance(step, dict)
        and str(step.get("uses", "")).startswith("actions/checkout@")
    ]
