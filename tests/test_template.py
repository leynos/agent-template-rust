from __future__ import annotations

from pathlib import Path
from datetime import datetime, UTC

import pytest
from pytest_copier.plugin import CopierFixture

APP = "app"
LIB = "lib"

TEMPLATE_PATH = Path(__file__).parents[1]


def test_template_renders(tmp_path: Path, copier: CopierFixture) -> None:
    """Template renders with default values."""
    project = copier.copy(
        tmp_path,
        project_name="Example",
        package_name="example",
        license_year=datetime.now(tz=UTC).year,
        license_holder="Example Dev",
        license_email="example@example.com",
    )
    assert (project / "Cargo.toml").exists()
    assert (project / "src" / f"{LIB}.rs").exists()
    project.run("cargo build")


def test_template_renders_app_flavour(tmp_path: Path, copier: CopierFixture) -> None:
    """Template renders app flavour correctly."""
    project = copier.copy(
        tmp_path,
        project_name="AppExample",
        package_name="app_example",
        license_year=datetime.now(tz=UTC).year,
        license_holder="App Dev",
        license_email="app@example.com",
        flavour=APP,
    )
    assert (project / "src" / "main.rs").exists()
    project.run("cargo build")


def test_template_renders_lib_flavour(tmp_path: Path, copier: CopierFixture) -> None:
    """Template renders lib flavour correctly."""
    project = copier.copy(
        tmp_path,
        project_name="LibExample",
        package_name="lib_example",
        license_year=datetime.now(tz=UTC).year,
        license_holder="Lib Dev",
        license_email="lib@example.com",
        flavour=LIB,
    )
    assert (project / "src" / "lib.rs").exists()
    project.run("cargo build")


def test_makefile_validates(tmp_path: Path, copier: CopierFixture) -> None:
    """Generated Makefile validates with mbake."""
    project = copier.copy(
        tmp_path,
        project_name="MakefileExample",
        package_name="makefile_example",
        license_year=datetime.now(tz=UTC).year,
        license_holder="Makefile Dev",
        license_email="makefile@example.com",
    )
    assert (project / "Makefile").exists()
    project.run("mbake validate Makefile")


def test_clippy_runs(tmp_path: Path, copier: CopierFixture) -> None:
    """Generated project passes Clippy."""
    project = copier.copy(
        tmp_path,
        project_name="ClippyExample",
        package_name="clippy_example",
        license_year=datetime.now(tz=UTC).year,
        license_holder="Clippy Dev",
        license_email="clippy@example.com",
    )
    project.run("cargo clippy --all-targets --all-features -- -D warnings")


@pytest.mark.parametrize("flavour", [LIB, APP])
def test_template_compiles(
    tmp_path: Path, copier: CopierFixture, flavour: str
) -> None:
    """Generated project compiles with cargo check."""
    project = copier.copy(
        tmp_path,
        project_name="CompileExample",
        package_name="compile_example",
        license_year=datetime.now(tz=UTC).year,
        license_holder="Compile Dev",
        license_email="compile@example.com",
        flavour=flavour,
    )
    project.run("cargo check --all-targets --all-features")

