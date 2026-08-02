"""Rendered project compilation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import read_generated_text
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

def test_documented_environment_injection_example_compiles(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Documented mockable environment example compiles against its pinned API."""
    project = render_project(
        tmp_path,
        copier,
        project_name="EnvironmentInjectionExample",
        package_name="environment_injection_example",
    )
    documentation = read_generated_text(
        project / "docs" / "reliable-testing-in-rust-via-dependency-injection.md"
    )
    dependency_tables = _fenced_block_after(
        documentation, "### 1. Add `mockable`", "toml"
    )
    rust_blocks = [
        _fenced_block_after(documentation, heading, "rust,no_run")
        for heading in [
            "### 3. Refactoring for testability (after)",
            "### 4. Writing isolated unit tests",
            "### 5. Usage in production code",
        ]
    ]

    example = project / "documented-environment-injection"
    source_directory = example / "src"
    source_directory.mkdir(parents=True)
    (example / "Cargo.toml").write_text(
        """[package]
name = "documented-environment-injection"
version = "0.1.0"
edition = "2024"

"""
        + dependency_tables
        + "\n",
        encoding="utf-8",
    )
    (source_directory / "main.rs").write_text(
        "\n\n".join(rust_blocks) + "\n",
        encoding="utf-8",
    )

    project.run(
        "cargo test --manifest-path "
        "documented-environment-injection/Cargo.toml --all-targets --all-features"
    )


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

def _fenced_block_after(documentation: str, heading: str, language: str) -> str:
    """Extract the first fenced code block following a documentation heading."""
    _, heading_found, section = documentation.partition(heading)
    assert heading_found, f"expected documentation heading {heading}"
    fence = f"```{language}\n"
    _, fence_found, fenced_content = section.partition(fence)
    assert fence_found, f"expected {language} block after {heading}"
    block, closing_fence_found, _ = fenced_content.partition("\n```")
    assert closing_fence_found, f"expected closing fence after {heading}"
    return block
