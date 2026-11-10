"""Rendered CV-005 workflow contract tests.

The shared ``cv005-contracts`` checker in ``leynos/shared-actions`` owns the
rules. These tests render four projects and run the generated
``make test-workflow-contracts`` target so the template's wiring is proved end
to end, then mutate one workflow to show the run is not vacuous.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import (
    parse_toml_file,
    read_generated_text,
    require_mapping,
)
from tests.helpers.rendering import APP, LIB, render_project
from tests.helpers.subprocess_env import generated_project_env

CV005_CONTRACTS_REF = "38905b4b2caec5b049438e6dc3f3f6b36c04d2df"
CHECK_TIMEOUT_SECONDS = 900


def _run_make(project: Path, target: str) -> subprocess.CompletedProcess[str]:
    """Run a generated-project Make target and capture its output."""
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"
    return subprocess.run(
        [make, target],
        cwd=project,
        env=generated_project_env({}),
        check=False,
        capture_output=True,
        text=True,
        timeout=CHECK_TIMEOUT_SECONDS,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    """Return combined standard output and standard error."""
    return f"{result.stdout}\n{result.stderr}"


@pytest.mark.parametrize("flavour", [LIB, APP])
@pytest.mark.parametrize("enable_polonius", [True, False])
def test_rendered_workflow_contracts_pass_the_shared_checker(
    tmp_path: Path,
    copier: CopierFixture,
    flavour: str,
    enable_polonius: bool,
) -> None:
    """Every render names its repository and satisfies the shared contract."""
    repository = "example/contract_example"
    project = render_project(
        tmp_path,
        copier,
        project_name="ContractExample",
        package_name="contract_example",
        flavour=flavour,
        enable_polonius=enable_polonius,
        github_repository=repository,
    )

    config = parse_toml_file(project / ".github/cv005.toml")
    assert config.get("repository") == repository, (
        "expected the contract configuration to name the rendered repository"
    )
    selection = require_mapping(config, "selection", ".github/cv005.toml")
    assert selection == {
        "format": "lcov",
        "output-path": "lcov.info",
        "with-ratchet": "true",
    }, "expected both coverage lanes to measure the same ratcheted selection"
    makefile = read_generated_text(project / "Makefile")
    assert f"CV005_CONTRACTS_REF ?= {CV005_CONTRACTS_REF}" in makefile, (
        "expected the generated target to use the reviewed shared revision"
    )

    result = _run_make(project.path, "test-workflow-contracts")

    assert result.returncode == 0, (
        f"expected the rendered workflows to satisfy CV-005\noutput:\n{_output(result)}"
    )


def test_rendered_contract_configuration_defaults_to_the_example_repository(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """The default answer names ``example/<package_name>`` in the contract."""
    project = render_project(
        tmp_path,
        copier,
        project_name="DefaultContract",
        package_name="default_contract",
    )

    config = parse_toml_file(project / ".github/cv005.toml")

    assert config.get("repository") == "example/default_contract", (
        "expected the default repository answer to reach the contract file"
    )


@pytest.mark.parametrize(
    ("repository_url", "expected"),
    [
        ("https://github.com/acme/widget", "acme/widget"),
        ("https://github.com/acme/widget.git", "acme/widget"),
        ("https://gitlab.com/acme/widget", "example/derived_contract"),
    ],
)
def test_repository_answer_defaults_to_the_repository_url(
    tmp_path: Path,
    copier: CopierFixture,
    repository_url: str,
    expected: str,
) -> None:
    """The default answer follows a GitHub URL and otherwise keeps the example."""
    project = render_project(
        tmp_path,
        copier,
        project_name="DerivedContract",
        package_name="derived_contract",
        repository_url=repository_url,
    )

    config = parse_toml_file(project / ".github/cv005.toml")

    assert config.get("repository") == expected, (
        "expected the default repository answer to follow repository_url"
    )


def test_checker_rejects_a_publisher_without_the_codescene_environment(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """A mutation that moves the credential out of its environment fails."""
    project = render_project(
        tmp_path,
        copier,
        project_name="MutationExample",
        package_name="mutation_example",
    )
    publisher = project / ".github/workflows/coverage-main.yml"
    original = publisher.read_text(encoding="utf-8")
    mutated = original.replace("    environment: codescene\n", "", 1)
    assert mutated != original, "expected the publisher to declare the environment"
    publisher.write_text(mutated, encoding="utf-8")

    result = _run_make(project.path, "test-workflow-contracts")

    output = _output(result)
    assert result.returncode != 0, (
        f"expected the mutated publisher to fail the contract check\noutput:\n{output}"
    )
    # A clause line, rather than only an error, shows the checker reported a
    # violation (its status 1) instead of a reading fault (status 2).
    assert "environment.placement" in output, (
        f"expected the environment clause to be named\noutput:\n{output}"
    )
    assert "must declare `environment: codescene`" in output, (
        f"expected the violation to explain the missing environment\noutput:\n{output}"
    )


@pytest.mark.parametrize(
    "answer",
    [
        "example",
        "example/",
        "/example",
        "example/name/extra",
        "example/na me",
    ],
)
def test_template_rejects_invalid_github_repository(
    tmp_path: Path, copier: CopierFixture, answer: str
) -> None:
    """Reject a repository answer that is not a GitHub ``owner/name``."""
    with pytest.raises(ValueError, match="must use owner/name"):
        copier.copy(
            tmp_path,
            project_name="InvalidRepository",
            package_name="invalid_repository",
            github_repository=answer,
        )
