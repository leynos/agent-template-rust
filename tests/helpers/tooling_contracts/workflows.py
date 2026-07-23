"""Assert rendered GitHub Actions contracts for generated Rust projects.

Shared-actions ``uses:`` refs are asserted by shape (correct reusable-workflow
or action path, pinned to a full 40-hex commit SHA), not by exact SHA value.
Dependabot owns bumping the pinned SHA; these contracts must not fail in
lockstep with routine bump PRs.
"""

from __future__ import annotations

import re
import shlex
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
_SETUP_RUST_USES_RE = re.compile(
    r"leynos/shared-actions/\.github/actions/setup-rust@[0-9a-f]{40}"
)
_SETUP_PYTHON_USES_RE = re.compile(r"actions/setup-python@[0-9a-f]{40}")
_UPLOAD_ARTIFACT_USES_RE = re.compile(r"actions/upload-artifact@[0-9a-f]{40}")


def _iter_job_steps(jobs: dict[str, Any]) -> list[Any]:
    """Return every step across all jobs in a parsed jobs mapping."""
    return [
        step
        for job in jobs.values()
        if isinstance(job, dict)
        for step in job.get("steps", [])
    ]


def _assert_pinned_step_uses(
    steps: list[Any], uses_re: "re.Pattern[str]", label: str
) -> None:
    """Assert one workflow step's ``uses:`` fully matches ``uses_re``.

    Parsing the actual ``uses:`` field, rather than scanning the raw workflow
    text, ensures that a commented-out reference or a mutable tag or branch
    cannot satisfy the pinned-action contract.
    """
    assert any(
        isinstance(step, dict) and uses_re.fullmatch(str(step.get("uses", "")))
        for step in steps
    ), f"expected {label} pinned to a full 40-hex commit SHA in a workflow step"


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
    _assert_pinned_step_uses(
        steps, _SETUP_RUST_USES_RE, "generated CI shared setup-rust action"
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
    _assert_pinned_step_uses(
        steps, _SETUP_PYTHON_USES_RE, "generated CI setup-python action"
    )
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


_MUTATION_JOB_PERMISSIONS = {"contents": "read", "id-token": "write"}
_MUTATION_SETUP_PACKAGES = ("clang", "lld", "mold")
_MUTATION_REUSABLE_WORKFLOW = (
    "leynos/shared-actions/.github/workflows/mutation-cargo.yml"
)
_MUTATION_CRON = "15 9 * * *"
_MUTATION_CONCURRENCY_GROUP = "mutation-testing-${{ github.ref }}"


def _extract_apt_install_packages(setup_commands: str) -> list[str]:
    """Return packages passed to the setup-commands ``apt-get install`` call.

    Parameters
    ----------
    setup_commands
        Setup-commands shell script from the mutation job ``with`` inputs.

    Returns
    -------
    list[str]
        Non-flag arguments supplied to ``apt-get install``, following any
        backslash line continuations, or an empty list when no install command
        is present.
    """
    lines = setup_commands.splitlines()
    marker = "apt-get install"
    for index, line in enumerate(lines):
        # Ignore commented-out commands so a `# ... apt-get install ...` line
        # can never be mistaken for a real install.
        if line.strip().startswith("#"):
            continue
        marker_at = line.find(marker)
        if marker_at == -1:
            continue
        segment = line[marker_at + len(marker) :]
        cursor = index
        while cursor < len(lines) and lines[cursor].rstrip().endswith("\\"):
            segment = segment.rstrip().removesuffix("\\")
            cursor += 1
            if cursor < len(lines):
                segment += " " + lines[cursor]
        # Surface malformed shell instead of masking it as a valid install; a
        # setup-commands script that cannot be parsed is not runnable.
        try:
            tokens = shlex.split(segment)
        except ValueError as error:
            raise AssertionError(
                "expected mutation job setup-commands apt-get install to be "
                f"parseable shell, got {segment!r}"
            ) from error
        return [token for token in tokens if not token.startswith("-")]
    return []


def _assert_mutation_workflow_contracts(mutation_workflow: str) -> None:
    """Assert generated mutation-testing workflow contracts."""
    parsed = parse_yaml_mapping(mutation_workflow, "mutation-testing workflow")
    assert parsed.get("permissions") == {}, (
        "expected mutation-testing workflow root permissions to grant no scopes"
    )
    triggers = require_mapping(parsed, "on", "mutation-testing workflow")
    schedule = require_sequence(triggers, "schedule", "mutation-testing workflow on")
    assert any(
        isinstance(entry, dict) and entry.get("cron") == _MUTATION_CRON
        for entry in schedule
    ), f"expected mutation-testing workflow to schedule cron {_MUTATION_CRON!r}"
    assert "workflow_dispatch" in triggers, (
        "expected mutation-testing workflow to support manual workflow_dispatch"
    )
    concurrency = require_mapping(parsed, "concurrency", "mutation-testing workflow")
    assert concurrency.get("group") == _MUTATION_CONCURRENCY_GROUP, (
        "expected mutation-testing workflow concurrency group "
        f"{_MUTATION_CONCURRENCY_GROUP!r}"
    )
    assert concurrency.get("cancel-in-progress") is False, (
        "expected mutation-testing workflow to queue runs "
        "(concurrency.cancel-in-progress: false)"
    )
    jobs = require_mapping(parsed, "jobs", "mutation-testing workflow")
    mutation = require_mapping(jobs, "mutation", "mutation-testing workflow jobs")
    mutation_uses = str(mutation.get("uses", ""))
    pinned_prefix = f"{_MUTATION_REUSABLE_WORKFLOW}@"
    assert mutation_uses.startswith(pinned_prefix), (
        "expected mutation job to call the shared mutation-cargo reusable workflow"
    )
    # The specific SHA is owned by Dependabot and deliberately not hard-coded, so
    # the contract survives dependency bumps while requiring an immutable pin.
    assert re.fullmatch(r"[0-9a-f]{40}", mutation_uses[len(pinned_prefix) :]), (
        "expected mutation job to pin the reusable workflow to a full commit SHA"
    )
    permissions = require_mapping(mutation, "permissions", "mutation job")
    assert permissions == _MUTATION_JOB_PERMISSIONS, (
        "expected mutation job permissions to stay scoped to "
        "contents: read and id-token: write"
    )
    inputs = require_mapping(mutation, "with", "mutation job")
    assert inputs.get("extra-args") == "--all-features", (
        "expected mutation job to mirror the CI --all-features test baseline"
    )
    setup_commands = inputs.get("setup-commands")
    assert isinstance(setup_commands, str), (
        "expected mutation job setup-commands to be a string"
    )
    installed_packages = _extract_apt_install_packages(setup_commands)
    assert installed_packages, (
        "expected mutation job setup-commands to install packages via apt-get"
    )
    for package in _MUTATION_SETUP_PACKAGES:
        assert package in installed_packages, (
            "expected mutation job setup-commands apt-get install to include "
            f"{package}"
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
    _assert_pinned_step_uses(
        _iter_job_steps(jobs),
        _UPLOAD_ARTIFACT_USES_RE,
        "app release upload-artifact action",
    )
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
