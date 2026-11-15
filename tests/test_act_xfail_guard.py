"""Unit tests for the known-limitation xfail guard in the act integration tests.

The shared coverage action's output step runs even after an earlier failure, so
the guard must xfail only when every failed step belongs to that output phase.
These tests feed synthetic act logs and run without act.
"""

from __future__ import annotations

import json

import pytest

from tests.test_github_actions_integration import (
    COVERAGE_STEP,
    RUST_SETUP_LOG_STEP,
    assert_act_result,
)

FLAGS = "-D warnings"
OUTPUT_ERROR = "Parameter INPUT_ARTEFACT_NAME_SUFFIX specified multiple times."


def _event(**fields: object) -> dict[str, object]:
    """Return an act JSON event with the given fields."""
    return {"level": "info", "job": "CI/build-test", **fields}


def _log(events: list[dict[str, object]]) -> str:
    """Render events as the JSON-lines stream act prints."""
    return "\n".join(json.dumps(event) for event in events)


def _evidence() -> list[dict[str, object]]:
    """Return events showing the Rust set-up log and a coverage test run."""
    return [
        _event(step=RUST_SETUP_LOG_STEP, msg=f"Base RUSTFLAGS: {FLAGS}"),
        _event(step=COVERAGE_STEP, msg="$ cargo llvm-cov nextest --workspace"),
    ]


def _failure(*step_ids: str) -> dict[str, object]:
    """Return a failed-step event for the coverage action's step IDs."""
    return _event(step=COVERAGE_STEP, stepID=list(step_ids), stepResult="failure")


def _output_error() -> dict[str, object]:
    """Return the known duplicate-input error event."""
    return _event(step=COVERAGE_STEP, stepID=["4", "out"], msg=OUTPUT_ERROR)


def test_known_output_failure_after_successful_coverage_xfails() -> None:
    """Only the output phase failed: the known limitation is an xfail."""
    events = [*_evidence(), _output_error(), _failure("4", "out"), _failure("4")]

    with pytest.raises(pytest.xfail.Exception):
        assert_act_result(1, _log(events), expected_base_rustflags=FLAGS)


def test_failed_coverage_run_before_the_output_error_is_not_masked() -> None:
    """A failed coverage step followed by the output error is a real failure."""
    events = [
        *_evidence(),
        _failure("4", "12"),
        _output_error(),
        _failure("4", "out"),
        _failure("4"),
    ]

    with pytest.raises(AssertionError):
        assert_act_result(1, _log(events), expected_base_rustflags=FLAGS)


def test_failure_in_another_step_is_not_masked() -> None:
    """A failure outside the coverage action stays a failure."""
    events = [
        *_evidence(),
        _event(step="Setup Rust", stepID=["1"], stepResult="failure"),
        _output_error(),
        _failure("4", "out"),
    ]

    with pytest.raises(AssertionError):
        assert_act_result(1, _log(events), expected_base_rustflags=FLAGS)


def test_a_clean_run_passes() -> None:
    """A zero exit with the expected evidence passes."""
    assert_act_result(0, _log(_evidence()), expected_base_rustflags=FLAGS)
