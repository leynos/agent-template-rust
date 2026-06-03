"""Validate parent repository CI workflow contracts."""

from __future__ import annotations

from pathlib import Path


def test_parent_ci_runs_template_tests_with_act_enabled() -> None:
    """Validate parent CI runs the act-enabled parent test gate."""
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "ACT_VERSION: v0.2.80" in workflow, (
        "expected parent CI to pin the act release used for workflow tests"
    )
    assert "act_Linux_x86_64.tar.gz" in workflow, (
        "expected parent CI to install the act Linux binary"
    )
    assert "docker info" in workflow, (
        "expected parent CI to verify the Docker runtime before act tests"
    )
    assert "make test WITH_ACT=1" in workflow, (
        "expected parent CI to run the parent tests with act validation enabled"
    )
