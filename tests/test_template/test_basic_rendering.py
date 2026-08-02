"""Basic rendered project smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import APP, LIB, render_project


def test_template_rejects_unsafe_nightly_date(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Reject a nightly date that could inject shell into release builds."""
    with pytest.raises(ValueError, match="must use YYYY-MM-DD"):
        copier.copy(
            tmp_path,
            project_name="UnsafeNightly",
            package_name="unsafe_nightly",
            rust_nightly_date="2025-06-10; echo INJECTED",
        )


def test_template_rejects_nightly_date_with_trailing_newline(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Reject a nightly date with content after the expected date."""
    with pytest.raises(ValueError, match="must use YYYY-MM-DD"):
        copier.copy(
            tmp_path,
            project_name="InvalidNightly",
            package_name="invalid_nightly",
            rust_nightly_date="2025-06-10\n",
        )


def test_template_renders(tmp_path: Path, copier: CopierFixture) -> None:
    """Template renders with default values and passes public gates."""
    project = render_project(
        tmp_path, copier, project_name="Example", package_name="example"
    )
    assert (project / "Cargo.toml").exists(), (
        "expected Cargo.toml to exist in generated project"
    )
    assert (project / "src" / f"{LIB}.rs").exists(), (
        f"expected src/{LIB}.rs to exist in generated project"
    )
    project.run("make all")


def test_template_renders_app_flavour(tmp_path: Path, copier: CopierFixture) -> None:
    """Template renders app flavour correctly and passes public gates."""
    project = render_project(
        tmp_path,
        copier,
        project_name="AppExample",
        package_name="app_example",
        flavour=APP,
    )
    assert (project / "src" / "main.rs").exists(), (
        "expected src/main.rs to exist for app flavour"
    )
    assert (project / "src" / "lib.rs").exists(), (
        "expected src/lib.rs to exist for app flavour doctests"
    )
    assert (project / ".github" / "workflows" / "release.yml").exists(), (
        "expected release workflow to exist for app flavour"
    )
    assert "-Zpolonius=next" in (project / ".cargo/config.toml").read_text(), (
        "expected app flavour to enable recommended Polonius support by default"
    )
    assert (project / "docs/polonius.md").exists(), (
        "expected app flavour to document default Polonius support"
    )
    project.run("make all")


def test_template_renders_lib_flavour(tmp_path: Path, copier: CopierFixture) -> None:
    """Template renders lib flavour correctly and passes public gates."""
    project = render_project(
        tmp_path,
        copier,
        project_name="LibExample",
        package_name="lib_example",
        flavour=LIB,
    )
    assert (project / "src" / "lib.rs").exists(), (
        "expected src/lib.rs to exist for lib flavour"
    )
    assert not (project / ".github" / "workflows" / "release.yml").exists(), (
        "expected release workflow to be omitted for lib flavour"
    )
    assert "-Zpolonius=next" not in (project / ".cargo/config.toml").read_text(), (
        "expected lib flavour to retain wider compiler compatibility by default"
    )
    assert not (project / "docs/polonius.md").exists(), (
        "expected lib flavour to omit Polonius policy by default"
    )
    project.run("make all")
