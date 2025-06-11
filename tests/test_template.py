from __future__ import annotations

from pathlib import Path
from datetime import datetime
import subprocess

import pytest
from pytest_copier.plugin import CopierFixture

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
    assert (project / "src" / "main.rs").exists()
    project.run("cargo build")
