"""Rendered lint target tests."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import render_project


def test_clippy_runs(tmp_path: Path, copier: CopierFixture) -> None:
    """Generated project passes its full lint target."""
    project = render_project(
        tmp_path,
        copier,
        project_name="ClippyExample",
        package_name="clippy_example",
    )
    project.run("make lint")


@pytest.mark.parametrize("whitaker_location", ["path", "home", "missing"])
def test_makefile_resolves_whitaker_fallback(
    tmp_path: Path,
    copier: CopierFixture,
    whitaker_location: str,
) -> None:
    """Generated lint target resolves Whitaker from PATH or user install."""
    project = render_project(
        tmp_path,
        copier,
        project_name="WhitakerExample",
        package_name="whitaker_example",
    )
    home = tmp_path / "home"
    path_bin = tmp_path / "path-bin"
    user_bin = home / ".local" / "bin"
    cargo = tmp_path / "cargo"
    marker = tmp_path / "whitaker-ran"
    path_bin.mkdir(parents=True)
    user_bin.mkdir(parents=True)
    cargo.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    cargo.chmod(0o755)

    expected_whitaker = None
    if whitaker_location != "missing":
        expected_whitaker = (
            path_bin / "whitaker"
            if whitaker_location == "path"
            else user_bin / "whitaker"
        )
        expected_whitaker.write_text(
            f"#!/bin/sh\ntouch {marker}\nexit 0\n", encoding="utf-8"
        )
        expected_whitaker.chmod(0o755)
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"

    result = subprocess.run(
        [make, "lint"],
        cwd=project.path,
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": os.pathsep.join(
                [str(path_bin), "/usr/bin", "/bin"]
                if whitaker_location == "path"
                else ["/usr/bin", "/bin"]
            ),
            "CARGO": str(cargo),
        },
        check=False,
        capture_output=True,
        text=True,
    )

    if expected_whitaker is None:
        assert result.returncode != 0, "expected lint to fail without Whitaker"
        assert "whitaker" in result.stderr.lower(), (
            "expected missing Whitaker failure to identify the missing tool"
        )
    else:
        assert result.returncode == 0, result.stderr
        assert marker.exists(), (
            f"expected generated lint target to execute {whitaker_location} Whitaker"
        )
