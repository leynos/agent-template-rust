"""Rendered Makefile validation tests."""

from __future__ import annotations

from pathlib import Path

from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import render_project


def test_makefile_validates(tmp_path: Path, copier: CopierFixture) -> None:
    """Generated Makefile validates with mbake."""
    project = render_project(
        tmp_path,
        copier,
        project_name="MakefileExample",
        package_name="makefile_example",
    )
    assert (project / "Makefile").exists(), (
        "expected generated project Makefile to exist"
    )
    project.run("mbake validate Makefile")
