"""Rendered doctest gate tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import LIB, render_project


def test_library_make_test_runs_doctests(tmp_path: Path, copier: CopierFixture) -> None:
    """Generated library test gate catches broken doctest examples."""
    project = render_project(
        tmp_path,
        copier,
        project_name="DoctestExample",
        package_name="doctest_example",
        flavour=LIB,
    )
    lib_rs = project / "src" / "lib.rs"
    lib_rs.write_text(
        lib_rs.read_text(encoding="utf-8")
        + """

/// Deliberately broken doctest used by the parent template regression test.
///
/// ```
/// let status = std::process::ExitCode::SUCCESS;
/// assert!(status.success());
/// ```
pub fn doctest_regression_marker() {}
""",
        encoding="utf-8",
    )
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"

    result = subprocess.run(
        [make, "test"],
        cwd=project.path,
        check=False,
        capture_output=True,
        text=True,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0, "expected make test to fail on broken doctests"
    assert "no method named `success`" in output, (
        "expected make test to compile doctests, exposing the broken example"
    )
