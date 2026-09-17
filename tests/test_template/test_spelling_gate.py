"""Real-binary smoke test for the generated project's spelling gate.

The shared ``typos-config-builder`` gate is not exercised by any unit test in
this repository: it is an external, pinned tool. These tests prove the rendered
wiring works end to end by running ``make spelling`` in a generated project and
asserting the default Markdown scope, the local overlay, and the repository
state the gate requires. Every test that reaches the real gate needs network
access to resolve the pinned tool and the live shared dictionary, so it is
marked ``slow``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture, CopierProject

from tests.helpers.rendering import render_project

# Assembled at run time so the parent gate, which checks every tracked file
# with --scope all, does not report this deliberate fixture as a finding.
PLANTED_TYPO = "rec" + "ieve"


def test_generated_project_ships_no_pregenerated_spelling_config(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """The template payload carries the overlay but no generated config."""
    project = render_project(
        tmp_path,
        copier,
        project_name="OverlayExample",
        package_name="overlay_example",
    )

    assert (project / "typos.local.toml").exists(), (
        "expected the rendered project to ship the narrow spelling overlay"
    )
    assert not (project / "typos.toml").exists(), (
        "expected the gate to generate typos.toml rather than the template"
    )
    assert not (project / "scripts/generate_typos_config.py").exists(), (
        "expected the retired vendored spelling generator to be absent"
    )
    assert not (project / "scripts/typos_rollout.py").exists(), (
        "expected the retired vendored spelling rollout module to be absent"
    )


@pytest.mark.slow
def test_generated_project_spelling_gate_passes(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """A freshly generated project passes its own ``make spelling`` gate."""
    if shutil.which("uv") is None:
        pytest.skip("uv is unavailable to resolve the pinned spelling gate")
    project = render_project(
        tmp_path,
        copier,
        project_name="SpellingExample",
        package_name="spelling_example",
    )

    project.run("make spelling")

    assert (project / "typos.toml").exists(), (
        "expected the gate to generate typos.toml on its first run"
    )


def _commit_all(project: CopierProject) -> None:
    """Stage every rendered and added file so the gate can enumerate it."""
    subprocess.run(
        ["git", "add", "--all"],
        cwd=project.path,
        check=True,
        capture_output=True,
        timeout=120,
    )


def _run_spelling(project: CopierProject) -> subprocess.CompletedProcess[str]:
    """Run the generated spelling gate without raising on findings.

    Git discovery is confined to the rendered project so a repository above the
    temporary directory cannot satisfy the gate's repository requirement.
    """
    return subprocess.run(
        ["make", "spelling"],
        cwd=project.path,
        env={**os.environ, "GIT_CEILING_DIRECTORIES": str(project.path.parent)},
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )


def test_generated_spelling_gate_requires_a_git_repository(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Running the gate outside a repository explains how to fix it."""
    if shutil.which("make") is None:
        pytest.skip("make is unavailable")
    project = render_project(
        tmp_path,
        copier,
        project_name="UnversionedExample",
        package_name="unversioned_example",
    )
    shutil.rmtree(project.path / ".git")

    completed = _run_spelling(project)

    assert completed.returncode != 0, (
        "expected the gate to refuse to run outside a Git repository"
    )
    assert "git init" in completed.stderr, (
        "expected the failure to name the command that fixes the repository state"
    )


@pytest.mark.slow
def test_generated_spelling_gate_reports_markdown_findings(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """The default scope checks Markdown prose and honours the overlay."""
    if shutil.which("uv") is None:
        pytest.skip("uv is unavailable to resolve the pinned spelling gate")
    project = render_project(
        tmp_path,
        copier,
        project_name="ScopeExample",
        package_name="scope_example",
    )
    (project.path / "docs" / "planted.md").write_text(
        f"# Planted\n\nThis sentence will {PLANTED_TYPO} a correction.\n",
        encoding="utf-8",
    )
    _commit_all(project)

    findings = _run_spelling(project)

    assert findings.returncode != 0, (
        "expected the default Markdown scope to check rendered prose"
    )
    assert PLANTED_TYPO in findings.stdout + findings.stderr, (
        "expected the gate to name the planted misspelling"
    )

    overlay = project.path / "typos.local.toml"
    overlay.write_text(
        overlay.read_text(encoding="utf-8").replace(
            'accepted = ["mold", "Polonius"]',
            f'accepted = ["mold", "Polonius", "{PLANTED_TYPO}"]',
        ),
        encoding="utf-8",
    )
    _commit_all(project)

    accepted = _run_spelling(project)

    assert accepted.returncode == 0, (
        "expected the local overlay to suppress the planted misspelling:\n"
        f"{accepted.stdout}\n{accepted.stderr}"
    )


@pytest.mark.slow
def test_generated_spelling_gate_leaves_rust_sources_to_the_parent_scope(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """The generated gate uses the Markdown scope, not the whole repository."""
    if shutil.which("uv") is None:
        pytest.skip("uv is unavailable to resolve the pinned spelling gate")
    project = render_project(
        tmp_path,
        copier,
        project_name="RustScopeExample",
        package_name="rust_scope_example",
    )
    planted = project.path / "src" / "planted.rs"
    planted.write_text(
        f"// This comment will {PLANTED_TYPO} no correction.\n", encoding="utf-8"
    )
    _commit_all(project)

    completed = _run_spelling(project)

    assert completed.returncode == 0, (
        "expected the generated gate to run at the default Markdown scope:\n"
        f"{completed.stdout}\n{completed.stderr}"
    )
