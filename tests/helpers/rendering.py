"""Render Copier projects and bridge generated-file helper APIs."""

from __future__ import annotations

from pathlib import Path

from pytest_copier.plugin import CopierFixture, CopierProject

from tests.helpers.generated_files import read_generated_text

APP = "app"
LIB = "lib"


def render_project(
    tmp_path: Path,
    copier: CopierFixture,
    *,
    project_name: str,
    package_name: str,
    flavour: str = LIB,
    license_year: int | None = 2026,
    dev_target: str = "x86_64-unknown-linux-gnu",
) -> CopierProject:
    """Render a generated Rust project with publishable metadata."""
    answers: dict[str, str | int] = {
        "project_name": project_name,
        "package_name": package_name,
        "package_description": f"{project_name} package used by template tests.",
        "repository_url": f"https://github.com/example/{package_name}",
        "homepage_url": f"https://example.com/{package_name}",
        "package_keywords": "rust,template",
        "package_categories": "development-tools",
        "license_holder": f"{project_name} Dev",
        "license_email": f"{package_name}@example.com",
        "flavour": flavour,
        "dev_target": dev_target,
    }
    if license_year is not None:
        answers["license_year"] = license_year

    return copier.copy(tmp_path, **answers)


def run_quality_gates(project: CopierProject) -> None:
    """Run the rendered project's public quality gate."""
    project.run("make all")


def read_generated_file(project: CopierProject, relative_path: str) -> str:
    """Read a rendered project file as UTF-8 text."""
    return read_generated_text(project / relative_path)
