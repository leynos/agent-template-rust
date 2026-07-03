"""Rendered project compilation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import APP, LIB, render_project


@pytest.mark.parametrize("flavour", [LIB, APP])
def test_template_compiles(tmp_path: Path, copier: CopierFixture, flavour: str) -> None:
    """Generated project compiles with cargo check."""
    project = render_project(
        tmp_path,
        copier,
        project_name="CompileExample",
        package_name="compile_example",
        flavour=flavour,
    )
    project.run("cargo check --all-targets --all-features")
