"""Validate the generated GitHub Actions workflow through act."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture, CopierProject

from tests.helpers.rendering import render_project
from tests.utilities import container_daemon_socket, docker_environment

EVENT = Path(__file__).parent / "fixtures" / "pull_request.event.json"
ACT_IMAGE = "ubuntu-latest=catthehacker/ubuntu:act-latest"
ACT_VALIDATION_STEP = "Run tests with act validation"


def prepare_git_repository(project: CopierProject) -> None:
    """Initialise a rendered project as a Git repository for act."""
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


def run_act(project: CopierProject, *, artifact_dir: Path) -> tuple[int, str]:
    """Run the generated act-validation workflow through act."""
    started = time.perf_counter()
    phase_logs = [
        f"act phase: setup started for {project.path}",
        f"act phase: artifact directory {artifact_dir}",
    ]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    env = docker_environment()
    command = [
        "act",
        "pull_request",
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
    docker_host = container_daemon_socket(env)
    if docker_host is not None:
        command.extend(["--container-daemon-socket", docker_host])
        phase_logs.append("act phase: using explicit container daemon socket")
    else:
        phase_logs.append("act phase: using act default container daemon socket")
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


def assert_ci_exercised_expected_steps(logs: str) -> None:
    """Assert that act logs include the expected Rust test gate."""
    saw_test_step = False
    saw_rust = False
    for event in iter_json_log_events(logs):
        output = str(event_text(event, "Output", "output", "message", "msg"))
        step = str(event_text(event, "name", "step_name", "Step", "step"))
        in_act_test_step = ACT_VALIDATION_STEP in step
        saw_test_step = saw_test_step or (
            in_act_test_step and "make test WITH_ACT=1" in output
        )
        saw_rust = saw_rust or (
            in_act_test_step
            and (
                "cargo nextest" in output
                or "cargo test --doc" in output
                or "cargo test" in output
            )
        )

    assert saw_test_step, f"act-validation test step was not observed:\n{logs}"
    assert saw_rust, f"Rust tests were not observed:\n{logs}"


def xfail_known_act_runtime_limitations(logs: str) -> None:
    """Xfail act limitations that prevent workflow execution from reaching tests."""
    if (
        "The runs.using key in action.yml must be one of:" in logs
        and "got node24" in logs
    ):
        pytest.xfail(
            "act currently cannot execute an upstream action that declares "
            "runs.using: node24"
        )
    if (
        "Parameter INPUT_ARTEFACT_NAME_SUFFIX specified multiple times" in logs
        and "Provided artifact name input during validation is empty" in logs
    ):
        pytest.xfail(
            "act currently fails in the shared generate-coverage composite "
            "action output/archive phase after tests and coverage succeed"
        )


def assert_act_result(project: CopierProject, code: int, logs: str) -> None:
    """Assert the act workflow result for a rendered Rust project."""
    xfail_known_act_runtime_limitations(logs)
    assert_ci_exercised_expected_steps(logs)
    assert code == 0, logs


@pytest.mark.act
def test_generated_act_validation_workflow_runs_tests(
    act_ready: None,
    copier: CopierFixture,
    tmp_path: Path,
) -> None:
    """Validate a generated act-validation workflow through act."""
    project = render_project(
        tmp_path / "act_rust",
        copier,
        project_name="ActRust",
        package_name="act_rust",
    )
    prepare_git_repository(project)

    code, logs = run_act(project, artifact_dir=tmp_path / "rust-artifacts")

    assert_act_result(project, code, logs)
