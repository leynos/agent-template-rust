"""Rendered delayed pull-request comment workflow tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture, CopierProject

from tests.helpers.delivery_workflows import named_step, render_delivery_project
from tests.helpers.generated_files import (
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
)
from tests.helpers.rendering import LIB


def _run_validation_step(
    project: CopierProject, pr_number: str, delay_minutes: str
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the rendered validation script with untrusted dispatch values."""
    parsed = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/delayed-pr-comment.yml"),
        "delayed comment workflow",
    )
    job = require_mapping(
        require_mapping(parsed, "jobs", "delayed comment workflow"),
        "delay-and-comment",
        "delayed workflow jobs",
    )
    validation_step = named_step(job, "Validate inputs", "delayed workflow job")
    script = str(validation_step.get("run", ""))
    assert script, "expected the validation step to run a script"
    output_path = project.path / "validation-output"
    output_path.write_text("", encoding="utf-8")
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "GITHUB_OUTPUT": str(output_path),
        "PR_NUMBER": pr_number,
        "DELAY_MINUTES": delay_minutes,
    }
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=project.path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result, output_path


@pytest.mark.parametrize(
    ("pr_number", "delay_minutes", "expected_seconds"),
    [
        ("12", "5", "300"),
        ("0", "0", "0"),
        ("123456", "90", "5400"),
        ("12", "010", "600"),
        ("12", "300", "18000"),
    ],
)
def test_delayed_pr_comment_accepts_whole_numbers(
    tmp_path: Path,
    copier: CopierFixture,
    pr_number: str,
    delay_minutes: str,
    expected_seconds: str,
) -> None:
    """The validation step converts a whole-minute delay to seconds."""
    project = render_delivery_project(
        tmp_path,
        copier,
        flavour=LIB,
        project_name="DelayedComment",
        package_name="delayed_comment",
    )
    result, output_path = _run_validation_step(project, pr_number, delay_minutes)

    assert result.returncode == 0, result.stderr
    assert f"delay-seconds={expected_seconds}" in output_path.read_text(
        encoding="utf-8"
    ), f"expected {delay_minutes} minutes to become {expected_seconds} seconds"


@pytest.mark.parametrize(
    ("pr_number", "delay_minutes"),
    [
        ("abc", "5"),
        ("12", "1.5"),
        ("-1", "5"),
        ("12", ""),
        ("12; rm -rf /", "5"),
        ("12", "$(id)"),
        ("12", "301"),
        ("12", "99999"),
        ("12", "00000000000000000001"),
    ],
)
def test_delayed_pr_comment_rejects_other_input(
    tmp_path: Path,
    copier: CopierFixture,
    pr_number: str,
    delay_minutes: str,
) -> None:
    """Non-numeric and shell-shaped input is rejected before use."""
    project = render_delivery_project(
        tmp_path,
        copier,
        flavour=LIB,
        project_name="InvalidDelayedComment",
        package_name="invalid_delayed_comment",
    )
    result, _output_path = _run_validation_step(project, pr_number, delay_minutes)

    assert result.returncode != 0, (
        f"expected {pr_number!r} and {delay_minutes!r} to be rejected"
    )
