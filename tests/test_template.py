from __future__ import annotations

from pathlib import Path
from datetime import datetime
import subprocess

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
        license_year=datetime.now().year,
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
        license_year=datetime.now().year,
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
        license_year=datetime.now().year,
        license_holder="Lib Dev",
        license_email="lib@example.com",
        flavour=LIB,
    )
    assert (project / "src" / "lib.rs").exists()
    project.run("cargo build")
