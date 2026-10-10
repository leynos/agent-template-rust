"""Contract tests for how the workflows provision clang, lld and mold.

The parent repository's CI and act-validation workflows, and the generated CI
and coverage-main workflows (asserted by the template tooling contracts through
the same helper), install the linkers through ``setup-rust``'s
``install-mold`` and ``install-clang-lld`` inputs. These tests read the parent
workflows' parsed steps, and run the shared helper against deliberately broken
steps so that it fails for each way the provisioning can be lost.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.helpers.tooling_contracts.workflows import (
    assert_setup_rust_installs_linkers,
)

SETUP_RUST = "leynos/shared-actions/.github/actions/setup-rust@" + "0" * 40
GOOD_INPUTS = {"install-mold": "true", "install-clang-lld": "true"}


def _setup_step(inputs: dict[str, Any] | None) -> dict[str, Any]:
    """Return a ``setup-rust`` step carrying *inputs*."""
    step: dict[str, Any] = {"name": "Setup Rust", "uses": SETUP_RUST}
    if inputs is not None:
        step["with"] = inputs
    return step


def _steps(workflow: str) -> list[Any]:
    """Return every step of every job in the parent workflow *workflow*."""
    document = yaml.safe_load(Path(".github/workflows", workflow).read_text("utf-8"))
    return [step for job in document["jobs"].values() for step in job["steps"]]


@pytest.mark.parametrize("workflow", ["ci.yml", "act-validation.yml"])
def test_parent_workflows_install_the_linkers_through_setup_rust(
    workflow: str,
) -> None:
    """The parent CI and act-validation workflows provision the linkers."""
    assert_setup_rust_installs_linkers(_steps(workflow), f"parent {workflow}")


def test_the_helper_accepts_both_inputs() -> None:
    """A setup-rust step with both inputs and no hand install passes."""
    assert_setup_rust_installs_linkers([_setup_step(GOOD_INPUTS)], "fixture")


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        pytest.param(None, "install-mold", id="no-with-block"),
        pytest.param({"install-mold": "true"}, "install-clang-lld", id="no-clang-lld"),
        pytest.param({"install-clang-lld": "true"}, "install-mold", id="no-mold"),
        pytest.param(
            {"install-mold": "true", "install-clang-lld": True},
            "install-clang-lld",
            id="boolean-not-string",
        ),
        pytest.param(
            {"install-mold": "false", "install-clang-lld": "true"},
            "install-mold",
            id="mold-false",
        ),
    ],
)
def test_the_helper_rejects_a_step_missing_an_input(
    inputs: dict[str, Any] | None, message: str
) -> None:
    """A missing, boolean or false input fails and names the input."""
    with pytest.raises(AssertionError, match=message):
        assert_setup_rust_installs_linkers([_setup_step(inputs)], "fixture")


def test_the_helper_rejects_a_workflow_without_a_pinned_setup_rust_step() -> None:
    """An unpinned setup-rust reference does not count as provisioning."""
    unpinned = {"uses": "leynos/shared-actions/.github/actions/setup-rust@main"}

    with pytest.raises(AssertionError, match="pinned to a full SHA"):
        assert_setup_rust_installs_linkers([unpinned], "fixture")


def test_the_helper_rejects_a_comment_that_only_mentions_the_inputs() -> None:
    """Text in a comment or another step's script is not a setup-rust input."""
    decoy = {
        "name": "Note",
        "run": "echo install-mold: 'true' install-clang-lld: 'true'",
    }

    with pytest.raises(AssertionError, match="install-mold"):
        assert_setup_rust_installs_linkers([_setup_step({}), decoy], "fixture")


def test_the_helper_rejects_a_hand_rolled_apt_install() -> None:
    """An apt step that installs a linker fails even beside the inputs."""
    by_hand = {
        "name": "Install mold linker",
        "run": "sudo apt-get install --yes --no-install-recommends clang lld mold",
    }

    with pytest.raises(AssertionError, match="Install mold linker"):
        assert_setup_rust_installs_linkers(
            [_setup_step(GOOD_INPUTS), by_hand], "fixture"
        )
