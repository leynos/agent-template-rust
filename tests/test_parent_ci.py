"""Validate parent repository CI workflow contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SETUP_RUST_ACTION = "leynos/shared-actions/.github/actions/setup-rust@"


def test_parent_ci_runs_template_tests_without_act_enabled() -> None:
    """Validate parent main CI keeps act validation separate."""
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "ACT_VERSION: v0.2.80" not in workflow, (
        "expected parent main CI not to pin the act release"
    )
    assert "act_Linux_x86_64.tar.gz" not in workflow, (
        "expected parent main CI not to install the act Linux binary"
    )
    assert "docker info" not in workflow, (
        "expected parent main CI not to verify Docker for act tests"
    )
    assert "make test WITH_ACT=1" not in workflow, (
        "expected parent main CI not to run act validation"
    )
    assert "run: make test" in workflow, (
        "expected parent main CI to run ordinary template tests"
    )
    assert "run: make spelling" in workflow, (
        "expected parent main CI to enforce spelling before template tests"
    )


def test_parent_act_validation_runs_template_tests_with_act_enabled() -> None:
    """Validate parent act workflow runs the act-enabled parent test gate."""
    workflow = Path(".github/workflows/act-validation.yml").read_text(encoding="utf-8")

    assert "ACT_VERSION: v0.2.80" in workflow, (
        "expected parent act workflow to pin the act release used for workflow tests"
    )
    assert "act_Linux_x86_64.tar.gz" in workflow, (
        "expected parent act workflow to install the act Linux binary"
    )
    assert "docker info" in workflow, (
        "expected parent act workflow to verify the Docker runtime before act tests"
    )
    assert "make test WITH_ACT=1" in workflow, (
        "expected parent act workflow to run parent tests with act validation enabled"
    )


@pytest.mark.parametrize(
    "workflow_path",
    [".github/workflows/ci.yml", ".github/workflows/act-validation.yml"],
)
def test_parent_workflows_accept_any_sccache_backend(workflow_path: str) -> None:
    """Every parent Rust setup step names its cache expectation explicitly.

    The parent jobs run on GitHub-hosted runners, where the shared action picks
    a local-disk sccache directory; ``expect-cache: any`` records that the job
    takes whichever backend the runner offers. The pinned revision is judged
    by its action name only, because the workflow contract asserts shape, not
    a SHA that Dependabot moves.
    """
    workflow = yaml.safe_load(Path(workflow_path).read_text(encoding="utf-8"))
    setup_steps = [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if str(step.get("uses", "")).startswith(SETUP_RUST_ACTION)
    ]

    assert setup_steps, f"expected {workflow_path} to run the shared setup-rust action"
    for step in setup_steps:
        assert (step.get("with") or {}).get("expect-cache") == "any", (
            f"expected {workflow_path} to set expect-cache: any on {step.get('name')}"
        )
