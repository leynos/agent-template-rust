"""Validate the generated GitHub Actions workflow through act."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture, CopierProject

from tests.helpers.rendering import render_project
from tests.utilities import container_daemon_socket, docker_environment

EVENT = Path(__file__).parent / "fixtures" / "pull_request.event.json"
ACT_IMAGE = "ubuntu-latest=catthehacker/ubuntu:act-latest"
RUST_SETUP_LOG_STEP = "Log Rust compiler configuration"
COVERAGE_STEP = "Test and Measure Coverage"
COVERAGE_JOB_STEP_NAMES = frozenset(
    {
        "Setup Rust",
        RUST_SETUP_LOG_STEP,
        "Log coverage linker configuration",
        COVERAGE_STEP,
    }
)
CHECKOUT_USES_PREFIX = "actions/checkout@"
STEP_HEADER = re.compile(r"^ {6}- (?P<key>name|uses): (?P<value>.+?)\s*$")


def trim_ci_workflow(workflow: str) -> str:
    """Reduce a rendered CI workflow to the steps the coverage job needs.

    The parent ``make test`` already renders each variant and runs its format,
    lint and test targets once (``make all``); the audit and spelling targets
    run in the rendered project's own CI on GitHub. A real act run only has to
    prove that the Rust set-up and the shared coverage action work end to end
    (it does not verify every output), so the other steps (spelling, audit,
    Whitaker, lint) are dropped from the act copy.

    Parameters
    ----------
    workflow
        Rendered ``ci.yml`` text.

    Returns
    -------
    str
        The workflow with every step outside the coverage job's steps removed.

    Raises
    ------
    AssertionError
        Raised when a step the coverage job needs is missing, which means the
        template renamed it and ``COVERAGE_JOB_STEP_NAMES`` must follow.
    """
    kept: list[str] = []
    seen: set[str] = set()
    keep_block = True
    for line in workflow.splitlines(keepends=True):
        header = STEP_HEADER.match(line)
        if header:
            value = header.group("value").strip("'\"")
            is_checkout = header.group("key") == "uses" and value.startswith(
                CHECKOUT_USES_PREFIX
            )
            seen.add(CHECKOUT_USES_PREFIX if is_checkout else value)
            keep_block = is_checkout or (
                header.group("key") == "name" and value in COVERAGE_JOB_STEP_NAMES
            )
        if keep_block:
            kept.append(line)
    missing = sorted((COVERAGE_JOB_STEP_NAMES | {CHECKOUT_USES_PREFIX}) - seen)
    assert not missing, f"rendered ci.yml lacks coverage-job steps: {missing}"
    return "".join(kept)


def prepare_git_repository(project: CopierProject) -> None:
    """Initialize a rendered project as a Git repository for act."""
    started = time.perf_counter()
    print(f"act phase: git repository preparation started for {project.path}")
    commands = [
        ["git", "init"],
        ["git", "config", "user.email", "act@example.invalid"],
        ["git", "config", "user.name", "Act Validation"],
        ["git", "add", "."],
        ["git", "commit", "-m", "Initial template render"],
    ]
    for command in commands:
        completed = subprocess.run(
            command, cwd=project.path, check=False, capture_output=True, text=True
        )
        if completed.returncode != 0:
            pytest.fail(
                "act phase: git repository preparation failed during "
                f"{' '.join(command)}\nstdout:\n{completed.stdout}\nstderr:\n"
                f"{completed.stderr}"
            )
    elapsed = time.perf_counter() - started
    print(f"act phase: git repository preparation completed in {elapsed:.3f}s")


def run_act(
    project: CopierProject, *, artifact_dir: Path, dry_run: bool = False
) -> tuple[int, str]:
    """Run the generated CI workflow through act, optionally as a dry run."""
    started = time.perf_counter()
    phase_logs = [
        f"act phase: setup started for {project.path}",
        f"act phase: artefact directory {artifact_dir}",
    ]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    env = docker_environment()
    command = [
        "act",
        "pull_request",
        "-W",
        ".github/workflows/ci.yml",
        "-j",
        "build-test",
        "-e",
        str(EVENT),
        "-P",
        ACT_IMAGE,
        "--artifact-server-path",
        str(artifact_dir),
        "--json",
        "-b",
    ]
    if dry_run:
        command.append("--dryrun")
    docker_host = container_daemon_socket(env)
    if docker_host is not None:
        command.extend(["--container-daemon-socket", docker_host])
        phase_logs.append("act phase: using explicit container daemon socket")
    else:
        phase_logs.append("act phase: using act default container daemon socket")
    act_github_token = env.get("ACT_GITHUB_TOKEN")
    if act_github_token:
        # The shared setup-rust action reads github-token while choosing its
        # sccache backend; without a secret it fails under act.
        command.extend(["-s", f"GITHUB_TOKEN={act_github_token}"])
        phase_logs.append("act phase: forwarding ACT_GITHUB_TOKEN as GITHUB_TOKEN")
    phase_logs.append("act phase: workflow execution started")
    completed = subprocess.run(
        command,
        cwd=project.path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=1200,
    )
    elapsed = time.perf_counter() - started
    phase_logs.append(f"act phase: workflow execution completed in {elapsed:.3f}s")
    return completed.returncode, "\n".join(
        [*phase_logs, completed.stdout, completed.stderr]
    )


def iter_json_log_events(logs: str) -> list[dict[str, object]]:
    """Return JSON event objects from an act log stream."""
    events: list[dict[str, object]] = []
    for line in logs.splitlines():
        if not line.lstrip().startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def event_text(event: dict[str, object], *keys: str) -> str:
    """Return the first non-empty event field as text."""
    for key in keys:
        value = event.get(key)
        if value:
            return str(value)
    return ""


def assert_ci_exercised_expected_steps(
    logs: str, *, expected_base_rustflags: str
) -> None:
    """Assert that act logs include the expected Rust test gate."""
    saw_test_step = False
    saw_rust = False
    saw_rust_setup_log = False
    for event in iter_json_log_events(logs):
        output = str(event_text(event, "Output", "output", "message", "msg"))
        step = str(event_text(event, "name", "step_name", "Step", "step"))
        saw_test_step = saw_test_step or "$ cargo llvm-cov" in output
        saw_rust = saw_rust or (
            "$ cargo llvm-cov nextest" in output or "$ cargo llvm-cov test" in output
        )
        saw_rust_setup_log = saw_rust_setup_log or (
            RUST_SETUP_LOG_STEP in step
            and f"Base RUSTFLAGS: {expected_base_rustflags}" in output
        )

    assert saw_rust_setup_log, f"Rust setup diagnostics were not observed:\n{logs}"
    assert saw_test_step, f"CI coverage command was not observed:\n{logs}"
    assert saw_rust, f"Rust coverage tests were not observed:\n{logs}"


def only_coverage_output_failures(events: list[dict[str, object]]) -> bool:
    """Return whether every failed step is the coverage action's output phase.

    The failures act reports for the known output limitation are the composite
    step itself (a one-element step ID) and its ``out`` sub-step. Any other
    failed step, such as the test or coverage run, is a real failure.

    Parameters
    ----------
    events
        Parsed act JSON events.

    Returns
    -------
    bool
        ``True`` when there is at least one failure and all of them belong to the
        coverage action's output phase.
    """
    failures = [event for event in events if event.get("stepResult") == "failure"]
    if not failures:
        return False
    for event in failures:
        step_ids = event.get("stepID", event.get("stepid", []))
        if event_text(event, "step", "Step") != COVERAGE_STEP:
            return False
        if not isinstance(step_ids, list) or not (
            len(step_ids) == 1 or step_ids[-1:] == ["out"]
        ):
            return False
    return True


def xfail_known_act_runtime_limitations(
    logs: str, *, expected_base_rustflags: str
) -> None:
    """Xfail known act runtime or coverage-output limitations."""
    if (
        "The runs.using key in action.yml must be one of:" in logs
        and "got node24" in logs
    ):
        pytest.xfail(
            "act currently cannot execute an upstream action that declares "
            "runs.using: node24"
        )
    # act v0.2.84 reports only the first message; earlier versions reported the
    # artefact-name validation error as well. The composite action's output step
    # runs even after an earlier failure, so the xfail applies only when every
    # failed step belongs to that output phase; a failed test or coverage run
    # falls through to the assertions below.
    if (
        "Parameter INPUT_ARTEFACT_NAME_SUFFIX specified multiple times" in logs
        and only_coverage_output_failures(iter_json_log_events(logs))
    ):
        assert_ci_exercised_expected_steps(
            logs, expected_base_rustflags=expected_base_rustflags
        )
        pytest.xfail(
            "act currently fails in the shared generate-coverage composite "
            "action output/archive phase after tests and coverage succeed"
        )


def assert_act_result(
    code: int,
    logs: str,
    *,
    expected_base_rustflags: str,
) -> None:
    """Assert the act workflow result for a rendered Rust project."""
    xfail_known_act_runtime_limitations(
        logs, expected_base_rustflags=expected_base_rustflags
    )
    assert_ci_exercised_expected_steps(
        logs, expected_base_rustflags=expected_base_rustflags
    )
    assert code == 0, logs


@pytest.mark.act
@pytest.mark.parametrize(
    ("enable_polonius", "expected_base_rustflags"),
    [(False, "-D warnings"), (True, "-Zpolonius=next")],
    ids=["warnings", "polonius"],
)
def test_generated_act_validation_workflow_runs_tests(
    act_ready: None,
    copier: CopierFixture,
    tmp_path: Path,
    enable_polonius: bool,
    expected_base_rustflags: str,
) -> None:
    """Run both Rust flag branches of the trimmed CI coverage job through act.

    Only the coverage job's steps run (see ``trim_ci_workflow``); the rendered
    project's lint, audit and test targets run once in the ordinary template
    tests.
    """
    project = render_project(
        tmp_path / f"act_rust_{enable_polonius}",
        copier,
        project_name="ActRust",
        package_name="act_rust",
        enable_polonius=enable_polonius,
    )
    ci_workflow = project / ".github" / "workflows" / "ci.yml"
    ci_workflow.write_text(
        trim_ci_workflow(ci_workflow.read_text(encoding="utf-8")), encoding="utf-8"
    )
    prepare_git_repository(project)

    code, logs = run_act(
        project, artifact_dir=tmp_path / f"rust-artifacts-{enable_polonius}"
    )

    assert_act_result(
        code,
        logs,
        expected_base_rustflags=expected_base_rustflags,
    )


@pytest.mark.act
@pytest.mark.parametrize("enable_polonius", [False, True], ids=["warnings", "polonius"])
def test_generated_workflows_parse_and_resolve_under_act(
    act_ready: None,
    copier: CopierFixture,
    tmp_path: Path,
    enable_polonius: bool,
) -> None:
    """Check the rendered workflows' wiring through act without running steps.

    ``act --list`` parses every rendered workflow, and a dry run of the CI job
    resolves its steps and the actions they use. Neither executes a step, so the
    full CI job is not run a second time.
    """
    project = render_project(
        tmp_path / f"act_wiring_{enable_polonius}",
        copier,
        project_name="ActWiring",
        package_name="act_wiring",
        enable_polonius=enable_polonius,
    )
    prepare_git_repository(project)
    listed = subprocess.run(
        ["act", "--list"],
        cwd=project.path,
        env=docker_environment(),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert listed.returncode == 0, f"act --list failed:\n{listed.stdout}{listed.stderr}"
    workflows = sorted(
        path.name for path in (project / ".github" / "workflows").glob("*.yml")
    )
    unlisted = [file for file in workflows if file not in listed.stdout]
    assert not unlisted, f"act did not list rendered workflows: {unlisted}"

    code, logs = run_act(
        project, artifact_dir=tmp_path / f"dryrun-{enable_polonius}", dry_run=True
    )
    assert code == 0, logs
    assert COVERAGE_STEP in logs, "the dry run should resolve the shared coverage step"
