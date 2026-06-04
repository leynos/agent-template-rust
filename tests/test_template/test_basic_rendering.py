"""Basic rendered project smoke tests."""

from __future__ import annotations

from pathlib import Path

from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import APP, LIB, render_project


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
    assert (project / ".github" / "workflows" / "release.yml").exists(), (
        "expected release workflow to exist for app flavour"
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
    project.run("make all")
