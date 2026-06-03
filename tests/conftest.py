"""Pytest fixtures for configuring pytest-copier template selection.

This module narrows pytest-copier's temporary template repository to the real
Copier inputs used by this project. Tests can use the normal `copier` fixture;
pytest-copier reads `copier_template_paths` during setup and copies only
`copier.yaml` and `template/` before rendering generated projects.

Example:
    A test that accepts `copier` and calls `copier.copy(...)` automatically uses
    these template paths.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from tests.utilities import docker_environment


@pytest.fixture(scope="session")
def copier_template_paths() -> list[str]:
    """Copy only template inputs into pytest-copier's temporary Git repo."""
    return ["copier.yaml", "template"]


def container_info_command() -> list[str] | None:
    """Return the preferred available container runtime probe."""
    if shutil.which("docker") is not None:
        return ["docker", "info"]
    if shutil.which("podman") is not None:
        return ["podman", "info"]
    return None


def _runtime_info_commands() -> list[list[str]]:
    """Return available container runtime info commands in preference order."""
    commands: list[list[str]] = []
    if container_info_command() is not None and shutil.which("docker") is not None:
        commands.append(["docker", "info"])
    if shutil.which("podman") is not None:
        commands.append(["podman", "info"])
    return commands


@pytest.fixture
def act_ready() -> None:
    """Skip act-backed tests unless local workflow validation can run."""
    if os.environ.get("RUN_ACT_VALIDATION") != "1":
        pytest.skip("set RUN_ACT_VALIDATION=1 to run act workflow validation")
    if shutil.which("act") is None:
        pytest.skip("act is not installed")
    info_commands = _runtime_info_commands()
    if not info_commands:
        pytest.skip("docker-compatible container runtime is not installed")
    errors: list[str] = []
    for info_command in info_commands:
        try:
            runtime = subprocess.run(
                info_command,
                env=docker_environment(),
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"{info_command[0]} info failed: {exc}")
            continue
        if runtime.returncode == 0:
            return
        errors.append(f"{info_command[0]} info failed:\n{runtime.stderr}")
    pytest.skip("docker-compatible runtime is unavailable:\n" + "\n".join(errors))
