from __future__ import annotations

from pathlib import Path
from datetime import datetime
import subprocess

import pytest
from pytest_copier import CopierRunner

TEMPLATE_PATH = Path(__file__).parents[1]


def test_template_renders(tmp_path: Path) -> None:
    """Template renders with default values."""
    runner = CopierRunner(str(TEMPLATE_PATH))
    project = runner.copy(
        str(tmp_path),
        data={
            "project_name": "Example",
            "package_name": "example",
            "license_year": datetime.now().year,
            "license_holder": "Example Dev",
            "license_email": "example@example.com",
        },
    )
    assert (project / "Cargo.toml").exists()
    assert (project / "src" / "main.rs").exists()
    subprocess.run(["cargo", "build"], cwd=project, check=True)
