"""Render Copier projects and bridge generated-file helper APIs."""

from __future__ import annotations

import subprocess
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
    enable_polonius: bool | None = None,
    license_year: int | None = 2026,
    dev_target: str = "x86_64-unknown-linux-gnu",
) -> CopierProject:
    """Render a generated Rust project with publishable metadata.

    Parameters
    ----------
    tmp_path : Path
        Destination directory for the rendered project.
    copier : CopierFixture
        Copier test fixture used to render the template.
    project_name : str
        Human-readable project name supplied to Copier.
    package_name : str
        Rust package name supplied to Copier.
    flavour : str
        Generated project flavour, either an application or a library.
    enable_polonius : bool | None
        Explicit Polonius selection. ``None`` omits the answer so Copier uses
        the flavour-based default; a Boolean overrides that default.
    license_year : int | None
        Copyright year. ``None`` omits the answer so Copier uses its default.
    dev_target : str
        Rust target triple used for generated development tooling.

    Returns
    -------
    CopierProject
        The rendered project fixture.
    """
    answers: dict[str, str | int | bool] = {
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
    if enable_polonius is not None:
        answers["enable_polonius"] = enable_polonius
    if license_year is not None:
        answers["license_year"] = license_year

    project = copier.copy(tmp_path, **answers)
    stage_generated_repository(project)
    return project


def stage_generated_repository(project: CopierProject) -> None:
    """Initialize and stage the rendered project as a Git repository.

    The generated spelling gate enumerates tracked files through
    ``git ls-files``, so a rendered project must be a Git repository with its
    files staged before ``make spelling``, ``make markdownlint`` or
    ``make all`` can run. Staging here mirrors how a generated project is used
    once it is committed.
    """
    for argv in (["git", "init", "--quiet"], ["git", "add", "--all"]):
        subprocess.run(
            argv,
            cwd=project.path,
            check=True,
            capture_output=True,
            timeout=120,
        )


def run_quality_gates(project: CopierProject) -> None:
    """Run the rendered project's public quality gate."""
    project.run("make all")


def read_generated_file(project: CopierProject, relative_path: str) -> str:
    """Read a rendered project file as UTF-8 text."""
    return read_generated_text(project / relative_path)
