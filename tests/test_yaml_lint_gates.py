"""Behavioural tests for the parent and rendered YAML lint gates.

The gates are exercised through the public Make targets rather than by
reimplementing their file selection. Tests that need the real tools skip when
yamllint, actionlint or shellcheck is unavailable; the selection and
defect-rejection cases prove that a passing run is not vacuous.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import APP, LIB, render_project

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_TOOLS = ("make", "yamllint", "actionlint", "shellcheck")


def _require_tools() -> None:
    """Skip the current test unless every real lint tool is installed."""
    missing = [tool for tool in REQUIRED_TOOLS if shutil.which(tool) is None]
    if missing:
        pytest.skip(f"real lint tools are unavailable: {', '.join(missing)}")


def _run_parent_target(
    workdir: Path, target: str, overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run one parent Make target in *workdir*.

    Parameters
    ----------
    workdir : Path
        Directory the target runs from; it owns the files Git enumerates.
    target : str
        Parent Make target to run.
    overrides : dict[str, str] | None
        Environment variables to apply after clearing Make controls.

    Returns
    -------
    subprocess.CompletedProcess[str]
        The finished process with captured output.
    """
    environment = {**os.environ, "MAKEFLAGS": ""}
    if overrides:
        environment.update(overrides)
    return subprocess.run(
        ["make", "-f", str(REPOSITORY_ROOT / "Makefile"), target],
        cwd=workdir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def _write(root: Path, name: str, source: str) -> None:
    """Write *source* to *name* under *root*, creating parent directories."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _install_yamllint_config(root: Path) -> None:
    """Copy the repository's yamllint base and overlay into *root*."""
    for name in (".yamllint-estate.yml", ".yamllint.yml"):
        shutil.copyfile(REPOSITORY_ROOT / name, root / name)


def _stage(root: Path, names: Iterable[str]) -> None:
    """Initialize *root* as a Git repository and stage the named files."""
    for command in (["init", "--quiet"], ["add", *names]):
        subprocess.run(
            ["git", *command],
            cwd=root,
            check=True,
            capture_output=True,
            timeout=60,
        )


def test_parent_yaml_gates_pass_on_the_repository() -> None:
    """The parent's own tracked YAML and workflows satisfy both gates."""
    _require_tools()

    for target in ("lint-yaml", "lint-actions"):
        completed = _run_parent_target(REPOSITORY_ROOT, target)
        assert completed.returncode == 0, (
            f"expected {target} to pass on the parent repository:\n"
            f"{completed.stdout}{completed.stderr}"
        )


def test_parent_yaml_gate_rejects_invalid_staged_yaml(tmp_path: Path) -> None:
    """Strict yamllint rejects a malformed tracked YAML document."""
    _require_tools()
    _install_yamllint_config(tmp_path)
    _write(tmp_path, "valid.yml", "name: valid\n")
    _write(tmp_path, "broken.yml", "name: [unterminated\n")
    _stage(tmp_path, ["valid.yml", "broken.yml"])

    completed = _run_parent_target(tmp_path, "lint-yaml")

    assert completed.returncode != 0, "expected malformed YAML to fail lint-yaml"
    assert "broken.yml" in completed.stdout + completed.stderr, (
        "expected the failure to name the malformed file"
    )


def test_parent_yaml_gate_excludes_untracked_yaml(tmp_path: Path) -> None:
    """An untracked malformed file does not enter the tracked-file gate."""
    _require_tools()
    _install_yamllint_config(tmp_path)
    _write(tmp_path, "valid.yml", "name: valid\n")
    _stage(tmp_path, ["valid.yml"])
    _write(tmp_path, "untracked.yml", "name: [unterminated\n")

    completed = _run_parent_target(tmp_path, "lint-yaml")

    assert completed.returncode == 0, (
        "expected the gate to enumerate tracked files only:\n"
        f"{completed.stdout}{completed.stderr}"
    )


def test_parent_yaml_gate_excludes_jinja_sources(tmp_path: Path) -> None:
    """A Copier source ending in `.jinja` is never parsed as YAML."""
    _require_tools()
    _install_yamllint_config(tmp_path)
    _write(tmp_path, "valid.yml", "name: valid\n")
    _write(
        tmp_path,
        ".github/workflows/ci.yml.jinja",
        "name: {{ project_name }}\non: {% if flavour %}push{% endif %}\n",
    )
    _stage(tmp_path, ["valid.yml", ".github/workflows/ci.yml.jinja"])

    completed = _run_parent_target(tmp_path, "lint-yaml")

    assert completed.returncode == 0, (
        "expected Jinja sources to be excluded from yamllint:\n"
        f"{completed.stdout}{completed.stderr}"
    )


def test_parent_action_gate_rejects_invalid_workflow(tmp_path: Path) -> None:
    """actionlint rejects a workflow whose job has no runner."""
    _require_tools()
    _write(
        tmp_path,
        ".github/workflows/invalid.yml",
        "name: invalid\non: push\njobs:\n  build:\n    steps:\n"
        "      - run: echo hello\n",
    )
    _stage(tmp_path, [".github/workflows/invalid.yml"])

    completed = _run_parent_target(tmp_path, "lint-actions")

    assert completed.returncode != 0, "expected an invalid workflow to fail actionlint"
    assert "runs-on" in completed.stdout + completed.stderr, (
        "expected actionlint to report the missing runner"
    )


def test_parent_action_gate_runs_shellcheck(tmp_path: Path) -> None:
    """actionlint reports ShellCheck findings in embedded run scripts."""
    _require_tools()
    _write(
        tmp_path,
        ".github/workflows/shellcheck.yml",
        "name: shellcheck\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: echo $UNDEFINED_VARIABLE\n",
    )
    _stage(tmp_path, [".github/workflows/shellcheck.yml"])

    completed = _run_parent_target(tmp_path, "lint-actions")

    assert completed.returncode != 0, (
        "expected ShellCheck to reject an unquoted variable"
    )
    assert "shellcheck" in (completed.stdout + completed.stderr).lower(), (
        "expected actionlint to attribute the finding to ShellCheck"
    )


def test_parent_and_template_yamllint_configuration_agree() -> None:
    """The template ships the same estate base and a minimal extending overlay."""
    estate = (REPOSITORY_ROOT / ".yamllint-estate.yml").read_text(encoding="utf-8")
    template_estate = (REPOSITORY_ROOT / "template/.yamllint-estate.yml").read_text(
        encoding="utf-8"
    )

    assert template_estate == estate, "expected the estate base copied verbatim"
    for overlay_path in (".yamllint.yml", "template/.yamllint.yml"):
        overlay = (REPOSITORY_ROOT / overlay_path).read_text(encoding="utf-8")
        assert overlay.strip() == "---\nextends: .yamllint-estate.yml", (
            f"expected {overlay_path} to only extend the estate base"
        )


@pytest.mark.parametrize(
    ("flavour", "enable_polonius"),
    [(LIB, False), (LIB, True), (APP, False), (APP, True)],
    ids=["lib-nll", "lib-polonius", "app-nll", "app-polonius"],
)
def test_rendered_projects_lint_yaml_and_workflows(
    tmp_path: Path, copier: CopierFixture, flavour: str, enable_polonius: bool
) -> None:
    """Each rendered flavour and Polonius mode passes the rendered lint gates."""
    _require_tools()
    project = render_project(
        tmp_path,
        copier,
        project_name="YamlLintExample",
        package_name="yaml_lint_example",
        flavour=flavour,
        enable_polonius=enable_polonius,
    )

    for target in ("lint-yaml", "lint-actions", "lint-shell"):
        project.run(f"make {target}")
