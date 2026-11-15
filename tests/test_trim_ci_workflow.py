"""Unit tests for the act coverage-job workflow trimmer.

``trim_ci_workflow`` keeps the real act run to the steps the shared coverage
action needs. These tests run without act, so a wrong trim fails in the default
suite rather than only in the act-validation job.
"""

from __future__ import annotations

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from tests.test_github_actions_integration import (
    CHECKOUT_USES_PREFIX,
    COVERAGE_JOB_STEP_NAMES,
    trim_ci_workflow,
)

CHECKOUT = f"{CHECKOUT_USES_PREFIX}0123456789abcdef0123456789abcdef01234567"
KEPT_NAMES = sorted(COVERAGE_JOB_STEP_NAMES)
REMOVED_NAMES = ("Format", "Check spelling", "Audit dependencies", "Lint")


def _named(name: str) -> str:
    """Return a rendered-looking named step block."""
    return f"      - name: {name}\n        run: echo {name.replace(' ', '-')}\n"


def _checkout() -> str:
    """Return the unnamed checkout step the Rust template renders."""
    return f"      - uses: {CHECKOUT}\n        with:\n          persist-credentials: false\n"


def _workflow(blocks: list[str]) -> str:
    """Return a minimal CI workflow whose job runs the given step blocks."""
    header = (
        "name: CI\n\n'on':\n  pull_request:\n\n"
        "jobs:\n  build-test:\n    runs-on: ubuntu-latest\n    steps:\n"
    )
    return header + "".join(blocks)


def _steps(workflow: str) -> list[dict[str, object]]:
    """Return the steps of the workflow's only job, parsed as YAML."""
    return yaml.safe_load(workflow)["jobs"]["build-test"]["steps"]


def _labels(workflow: str) -> list[str]:
    """Return each step's name, or its ``uses`` value for unnamed steps."""
    return [str(step.get("name", step.get("uses"))) for step in _steps(workflow)]


FULL = [
    _checkout(),
    *(_named(name) for name in REMOVED_NAMES),
    *(_named(name) for name in KEPT_NAMES),
]


def test_trim_keeps_checkout_and_coverage_job_steps_and_drops_the_rest() -> None:
    """Only the checkout and the coverage job's steps survive, in order."""
    labels = _labels(trim_ci_workflow(_workflow(FULL)))

    assert labels == [CHECKOUT, *KEPT_NAMES], (
        "expected the trim to keep the checkout and the coverage job's steps"
    )


def test_trim_output_is_valid_workflow_yaml() -> None:
    """The trimmed text parses and keeps the checkout step's `with` block."""
    steps = _steps(trim_ci_workflow(_workflow(FULL)))

    assert steps[0]["with"] == {"persist-credentials": False}, (
        "expected the trim to keep a retained step's whole block"
    )


@pytest.mark.parametrize("missing", ["Setup Rust", "Test and Measure Coverage"])
def test_trim_rejects_a_workflow_missing_a_required_step(missing: str) -> None:
    """A renamed or removed required step fails loudly instead of trimming away."""
    blocks = [block for block in FULL if f"name: {missing}\n" not in block]

    with pytest.raises(AssertionError, match="lacks coverage-job steps"):
        trim_ci_workflow(_workflow(blocks))


def test_trim_rejects_a_workflow_without_a_checkout() -> None:
    """The unnamed checkout step is required as well."""
    blocks = [block for block in FULL if CHECKOUT_USES_PREFIX not in block]

    with pytest.raises(AssertionError, match="lacks coverage-job steps"):
        trim_ci_workflow(_workflow(blocks))


@given(extra_count=st.integers(min_value=0, max_value=8), split=st.integers(0, 8))
def test_trim_keeps_exactly_the_required_steps_whatever_surrounds_them(
    extra_count: int, split: int
) -> None:
    """Arbitrary extra steps never survive and the required steps always do."""
    extras = [_named(f"Extra step {number}") for number in range(extra_count)]
    cut = min(split, extra_count)
    required = [_checkout(), *(_named(name) for name in KEPT_NAMES)]
    blocks = [*extras[:cut], *required, *extras[cut:]]

    labels = _labels(trim_ci_workflow(_workflow(blocks)))

    assert labels == [CHECKOUT, *KEPT_NAMES], (
        "expected only the checkout and coverage job steps to survive the trim"
    )
