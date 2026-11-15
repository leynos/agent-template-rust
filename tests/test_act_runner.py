"""Act-free tests for the act runner helper, the make recipe and the trim.

These run in the default suite, so a regression in how the act lane is invoked
fails there rather than only in the act-validation job.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pytest_copier.plugin import CopierFixture, CopierProject

from tests.helpers.rendering import render_project
from tests.test_github_actions_integration import (
    CHECKOUT_USES_PREFIX,
    COVERAGE_STEP,
    RUST_SETUP_LOG_STEP,
    run_act,
    trim_ci_workflow,
)

TOKEN = "nested-token-value"


def _capture_run_act(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env: dict[str, str]
) -> tuple[list[str], dict[str, str]]:
    """Run ``run_act`` against a fake subprocess and return its command and env."""
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        """Capture the act command and the environment it would run with."""
        seen["command"] = list(command)
        seen["env"] = dict(kwargs["env"])
        return subprocess.CompletedProcess(command, 0, "stdout", "")

    monkeypatch.setattr(
        "tests.test_github_actions_integration.docker_environment", lambda: dict(env)
    )
    monkeypatch.setattr(
        "tests.test_github_actions_integration.container_daemon_socket", lambda _: None
    )
    monkeypatch.setattr(subprocess, "run", fake_run)
    project = cast("CopierProject", SimpleNamespace(path=tmp_path))
    run_act(project, artifact_dir=tmp_path / "artefacts")
    return seen["command"], seen["env"]


def test_run_act_forwards_the_token_by_name_not_by_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The secret value reaches act through the environment, never its arguments."""
    command, env = _capture_run_act(monkeypatch, tmp_path, {"ACT_GITHUB_TOKEN": TOKEN})

    assert command[command.index("-s") + 1] == "GITHUB_TOKEN", (
        "expected act to be told the secret's name only"
    )
    assert not any(TOKEN in argument for argument in command), (
        "expected the token value to stay out of the act arguments"
    )
    assert env["GITHUB_TOKEN"] == TOKEN, (
        "expected the token value to travel in the act environment"
    )


def test_run_act_passes_no_secret_without_a_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without ``ACT_GITHUB_TOKEN`` act receives no secret and no token variable."""
    command, env = _capture_run_act(monkeypatch, tmp_path, {})

    assert "-s" not in command, "expected no act secret without ACT_GITHUB_TOKEN"
    assert "GITHUB_TOKEN" not in env, "expected no synthesized GITHUB_TOKEN"


def test_test_act_recipe_runs_only_the_act_marked_tests() -> None:
    """``make test-act`` enables act validation and selects ``-m act`` only."""
    makefile = Path("Makefile").read_text(encoding="utf-8")
    recipe = makefile.split("\ntest-act:", 1)[1].split("\n\n", 1)[0]

    assert "RUN_ACT_VALIDATION=1" in recipe, "expected the recipe to enable act"
    assert "-m act" in recipe, "expected the recipe to select the act marker"
    assert "$(MAKE)" not in recipe and "make " not in recipe, (
        "expected the recipe not to call another make target, which could run "
        "the unmarked suite"
    )
    assert recipe.count("pytest") == 1, (
        "expected the recipe to run pytest once, so it cannot also run an "
        "unmarked full suite"
    )


@pytest.mark.parametrize("enable_polonius", [False, True], ids=["warnings", "polonius"])
def test_trim_keeps_the_rendered_coverage_steps_in_order(
    copier: CopierFixture, tmp_path: Path, enable_polonius: bool
) -> None:
    """Trimming a real rendered CI workflow keeps exactly the coverage steps."""
    project = render_project(
        tmp_path / f"trim_{enable_polonius}",
        copier,
        project_name="TrimRust",
        package_name="trim_rust",
        enable_polonius=enable_polonius,
    )
    text = (project / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    trimmed = trim_ci_workflow(text)

    positions = [
        trimmed.index(CHECKOUT_USES_PREFIX),
        trimmed.index("name: Setup Rust"),
        trimmed.index(f"name: {RUST_SETUP_LOG_STEP}"),
        trimmed.index("name: Log coverage linker configuration"),
        trimmed.index(f"name: {COVERAGE_STEP}"),
    ]
    assert positions == sorted(positions), "expected the kept steps in template order"
    for removed in ("Format", "Lint", "Audit dependencies", "Check spelling"):
        assert f"name: {removed}\n" not in trimmed, f"expected {removed} to be trimmed"
