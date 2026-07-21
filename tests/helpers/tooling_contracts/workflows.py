"""Assert rendered GitHub Actions contracts for generated Rust projects.

Shared-actions ``uses:`` refs are asserted by shape (correct reusable-workflow
or action path, pinned to a full 40-hex commit SHA), not by exact SHA value.
Dependabot owns bumping the pinned SHA; these contracts must not fail in
lockstep with routine bump PRs.
"""

from __future__ import annotations

import re
from typing import Any

from tests.helpers.generated_files import (
    parse_yaml_mapping,
    require_mapping,
    require_sequence,
)

_GENERATE_COVERAGE_USES_RE = re.compile(
    r"^leynos/shared-actions/\.github/actions/generate-coverage@[0-9a-f]{40}$"
)
_UPLOAD_CODESCENE_COVERAGE_USES_RE = re.compile(
    r"^leynos/shared-actions/\.github/actions/upload-codescene-coverage@[0-9a-f]{40}$"
)
_SETUP_RUST_USES_TEXT_RE = re.compile(
    r"leynos/shared-actions/\.github/actions/setup-rust@[0-9a-f]{40}"
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
    coverage_uses = str(coverage_step.get("uses", ""))
    assert _GENERATE_COVERAGE_USES_RE.match(coverage_uses), (
        "expected CI to use the shared coverage action pinned to a full "
        f"40-hex commit SHA, got {coverage_uses!r}"
    )
    coverage_inputs = require_mapping(coverage_step, "with", "coverage step")
    assert coverage_inputs.get("output-path") == "lcov.info", (
        "expected CI coverage output path to match the act assertion"
    )
    assert coverage_inputs.get("format") == "lcov", (
        "expected CI coverage format to match the CodeScene upload"
    )
    assert coverage_inputs.get("with-ratchet") == "true", (
        "expected CI coverage step to enable the coverage ratchet"
    )


def _assert_audit_workflow_contracts(audit_workflow: str) -> None:
    """Assert generated scheduled dependency audit workflow contracts."""
    parsed_audit_workflow = parse_yaml_mapping(audit_workflow, "audit workflow")
    triggers = require_mapping(parsed_audit_workflow, "on", "audit workflow")
    schedule = require_sequence(triggers, "schedule", "audit workflow triggers")
    assert schedule == [{"cron": "41 6 * * 1"}], (
        "expected generated audit workflow to run weekly"
    )
    assert "workflow_dispatch" in triggers, (
        "expected generated audit workflow to support manual runs"
    )

    permissions = require_mapping(
        parsed_audit_workflow, "permissions", "audit workflow"
    )
    assert permissions.get("contents") == "read", (
        "expected generated audit workflow to grant least-privilege "
        "contents: read permissions"
    )

    jobs = require_mapping(parsed_audit_workflow, "jobs", "audit workflow")
    audit = require_mapping(jobs, "audit", "audit workflow jobs")
    assert audit.get("runs-on") == "ubuntu-latest", (
        "expected generated audit job to use Ubuntu"
    )
    assert audit.get("timeout-minutes") == 30, (
        "expected generated audit job to have a bounded runtime"
    )
    steps = require_sequence(audit, "steps", "audit workflow job")
    checkout_action = "actions/checkout@900f2210b1d28bbbd0bd22d17926b9e224e8f231"
    expected_steps = {
        None: checkout_action,
        "Setup Python for audit manifest extraction": (
            "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405"
        ),
    }
    for step_name, action in expected_steps.items():
        matching_steps = [
            step
            for step in steps
            if isinstance(step, dict)
            and step.get("name") == step_name
            and step.get("uses") == action
        ]
        assert len(matching_steps) == 1, (
            f"expected generated audit workflow to include pinned {action}"
        )
    checkout_steps = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("uses") == checkout_action
    ]
    assert checkout_steps, "expected generated audit workflow checkout step"
    assert all(
        isinstance(step.get("with"), dict)
        and step["with"].get("persist-credentials") is False
        for step in checkout_steps
    ), "expected generated audit workflow checkout to disable credential persistence"
    setup_rust_steps = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == "Setup Rust"
    ]
    assert len(setup_rust_steps) == 1, (
        "expected generated audit workflow to include one Setup Rust step"
    )
    setup_rust_uses = str(setup_rust_steps[0].get("uses", ""))
    assert _SETUP_RUST_USES_TEXT_RE.fullmatch(setup_rust_uses), (
        "expected generated audit workflow to use setup-rust pinned to a full "
        f"40-hex commit SHA, got {setup_rust_uses!r}"
    )
    assert any(
        isinstance(step, dict)
        and step.get("name") == "Install cargo-audit"
        and step.get("run") == "cargo binstall --no-confirm cargo-audit"
        for step in steps
    ), "expected generated audit workflow to install cargo-audit"
    assert any(
        isinstance(step, dict)
        and step.get("name") == "Audit dependencies"
        and step.get("run") == "make audit"
        for step in steps
    ), "expected generated audit workflow to run make audit"


def assert_coverage_main_workflow_contract(coverage_main_workflow: str) -> None:
    """Assert the generated ``coverage-main.yml`` push-and-upload contract.

    Parameters
    ----------
    coverage_main_workflow
        Rendered generated-project ``coverage-main.yml`` workflow text.

    Returns
    -------
    None
        The helper returns ``None`` when the coverage-main contract passes.

    Raises
    ------
    AssertionError
        Raised when the workflow does not trigger on push to main and
        ``workflow_dispatch``, omits the pinned shared coverage action, fails
        to guard the CodeScene upload on ``CS_ACCESS_TOKEN``, or drops the
        ratchet baseline that pull-request runs compare against.
    pytest.fail.Exception
        Raised by YAML parsing helpers when the workflow cannot be parsed as
        the expected mapping structure.
    """
    parsed = parse_yaml_mapping(coverage_main_workflow, "coverage-main workflow")
    triggers = require_mapping(parsed, "on", "coverage-main workflow")
    push = require_mapping(triggers, "push", "coverage-main workflow on")
    assert push.get("branches") == ["main"], (
        "expected coverage-main.yml to upload on push to main"
    )
    assert "workflow_dispatch" in triggers, (
        "expected coverage-main.yml to allow workflow_dispatch; automerge "
        "GITHUB_TOKEN pushes do not fire push-event workflows"
    )
    jobs = require_mapping(parsed, "jobs", "coverage-main workflow")
    coverage_upload = require_mapping(jobs, "coverage-upload", "coverage-main jobs")
    steps = require_sequence(coverage_upload, "steps", "coverage-main job")
    coverage_steps = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == "Test and Measure Coverage"
    ]
    assert len(coverage_steps) == 1, (
        "expected coverage-main.yml to generate coverage once"
    )
    coverage_inputs = require_mapping(coverage_steps[0], "with", "coverage-main step")
    assert coverage_inputs.get("with-ratchet") == "true", (
        "expected coverage-main.yml to advance the ratchet baseline"
    )
    upload_steps = [
        step
        for step in steps
        if isinstance(step, dict)
        and "upload-codescene-coverage" in str(step.get("uses", ""))
    ]
    assert len(upload_steps) == 1, (
        "expected coverage-main.yml to upload coverage to CodeScene"
    )
    upload_uses = str(upload_steps[0].get("uses", ""))
    assert _UPLOAD_CODESCENE_COVERAGE_USES_RE.match(upload_uses), (
        "expected coverage-main.yml to use the shared upload action pinned "
        f"to a full 40-hex commit SHA, got {upload_uses!r}"
    )
    assert upload_steps[0].get("if") == "env.CS_ACCESS_TOKEN != ''", (
        "expected coverage-main.yml upload to skip cleanly without a token"
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
    act_jobs = require_mapping(parsed_act_workflow, "jobs", "act-validation workflow")
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
    dependabot_guard = "github.actor != 'dependabot[bot]'"
    dependabot_guarded_steps = [
        step.get("name")
        for step in steps
        if isinstance(step, dict) and step.get("if") == dependabot_guard
    ]
    assert dependabot_guarded_steps == [
        "Install cargo-audit",
        "Setup Python for audit manifest extraction",
        "Audit dependencies",
    ], "expected only audit-specific CI steps to skip Dependabot pull requests"
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
        rust_tool_env = require_mapping(matching_steps[0], "env", f"{step_name} step")
        assert rust_tool_env.get("RUSTFLAGS") == "", (
            f"expected generated CI {step_name} step to clear inherited RUSTFLAGS"
        )

    assert "Cache Whitaker installation" in ci_workflow, (
        "expected generated CI workflow to cache Whitaker installation"
    )
    assert _SETUP_RUST_USES_TEXT_RE.search(ci_workflow), (
        "expected generated CI workflow to use the shared setup-rust action "
        "pinned to a full 40-hex commit SHA"
    )
    build_test_checkout = [
        step
        for step in steps
        if isinstance(step, dict)
        and str(step.get("uses", "")).startswith("actions/checkout@")
    ]
    assert build_test_checkout, "expected generated CI build-test checkout step"
    assert all(
        step.get("with", {}).get("fetch-depth") == 0 for step in build_test_checkout
    ), (
        "expected generated CI coverage checkout to fetch full history "
        "(fetch-depth: 0) so CodeScene's changed-line gate can reach the "
        "merge base once the deferred gate is wired"
    )
    upload_steps = [
        step
        for step in steps
        if isinstance(step, dict)
        and "upload-codescene-coverage" in str(step.get("uses", ""))
    ]
    assert not upload_steps, (
        "expected the generated pull-request CI job to omit the CodeScene "
        "upload step; uploads belong in coverage-main.yml, and mode: check "
        "awaits per-project gate enablement"
    )
    assert "Deferred CodeScene coverage gate" in ci_workflow, (
        "expected generated CI workflow to document the deferred CodeScene "
        "coverage gate"
    )
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
    assert "key: cross-${{ env.CROSS_REVISION }}" in release_workflow, (
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
