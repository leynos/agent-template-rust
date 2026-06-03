"""Validate the generated GitHub Actions workflow through act."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture, CopierProject

from tests.helpers.rendering import render_project
from tests.helpers.tooling_contracts import assert_ci_coverage_action_contract
from tests.utilities import container_daemon_socket, docker_environment

EVENT = Path(__file__).parent / "fixtures" / "pull_request.event.json"
ACT_IMAGE = "ubuntu-latest=catthehacker/ubuntu:act-latest"
GENERATE_COVERAGE_STEP = "Test and Measure Coverage"


def prepare_git_repository(project: CopierProject) -> None:
    """Initialise a rendered project as a Git repository for act."""
    commands = [
        ["git", "init"],
        ["git", "config", "user.email", "act@example.invalid"],
        ["git", "config", "user.name", "Act Validation"],
        ["git", "add", "."],
        ["git", "commit", "-m", "Initial template render"],
    ]
    for command in commands:
        subprocess.run(command, cwd=project.path, check=True, capture_output=True)


def run_act(project: CopierProject, *, artifact_dir: Path) -> tuple[int, str]:
    """Run the generated CI workflow through act."""
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
    completed = subprocess.run(
        command,
        cwd=project.path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=1200,
    )
    return completed.returncode, f"{completed.stdout}\n{completed.stderr}"


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
    """Assert that act logs include the expected Rust test and coverage steps."""
    saw_coverage = False
    saw_rust = False
    for event in iter_json_log_events(logs):
        output = str(event_text(event, "Output", "output", "message", "msg"))
        step = str(event_text(event, "name", "step_name", "Step", "step"))
        in_coverage_step = GENERATE_COVERAGE_STEP in step
        saw_coverage = saw_coverage or (
            in_coverage_step and ("lcov.info" in output or "Current coverage" in output)
        )
        saw_rust = saw_rust or (
            in_coverage_step
            and (
                "run_rust.py" in output
                or "cargo nextest" in output
                or "cargo llvm-cov" in output
            )
        )

    assert saw_coverage, f"coverage action step was not observed:\n{logs}"
    assert saw_rust, f"Rust tests were not observed:\n{logs}"


def assert_act_result(project: CopierProject, code: int, logs: str) -> None:
    """Assert the act workflow result for a rendered Rust project."""
    assert (project / "lcov.info").exists(), (
        "act workflow should write lcov.info in the generated project"
    )
    assert_ci_exercised_expected_steps(logs)
    if code == 0:
        return
    if (
        "Parameter INPUT_ARTEFACT_NAME_SUFFIX specified multiple times" in logs
        and "Provided artifact name input during validation is empty" in logs
    ):
        pytest.xfail(
            "act currently fails in the shared generate-coverage composite "
            "action output/archive phase after tests and coverage succeed"
        )
    assert code == 0, logs


@pytest.mark.act
def test_generated_workflow_runs_with_shared_coverage_action(
    act_ready: None,
    copier: CopierFixture,
    tmp_path: Path,
) -> None:
    """Validate a generated CI workflow through act."""
    project = render_project(
        tmp_path / "act_rust",
        copier,
        project_name="ActRust",
        package_name="act_rust",
    )
    prepare_git_repository(project)

    code, logs = run_act(project, artifact_dir=tmp_path / "rust-artifacts")

    workflow = (project / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert_ci_coverage_action_contract(workflow)
    assert_act_result(project, code, logs)
