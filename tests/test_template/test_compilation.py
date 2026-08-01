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


def test_polonius_project_accepts_single_lookup_get_or_insert(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Polonius-enabled public typecheck accepts a borrow-returning accessor."""
    project = render_project(
        tmp_path,
        copier,
        project_name="PoloniusExample",
        package_name="polonius_example",
        flavour=LIB,
        enable_polonius=True,
    )
    (project / "src/lib.rs").write_text(
        """//! Borrow-centric Polonius compilation fixture.

use std::collections::HashMap;

/// Return the existing value or insert its default with one hit-path lookup.
pub fn get_or_insert<'values>(
    values: &'values mut HashMap<String, u8>,
    key: &str,
) -> &'values mut u8 {
    if let Some(value) = values.get_mut(key) {
        return value;
    }
    values.entry(key.to_owned()).or_default()
}
""",
        encoding="utf-8",
    )

    project.run("make typecheck")
