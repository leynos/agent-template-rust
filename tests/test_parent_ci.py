"""Validate parent repository CI workflow contracts."""

from __future__ import annotations

from pathlib import Path


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
