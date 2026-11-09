"""Rendered test lane tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import (
    parse_toml_file,
    read_generated_text,
    require_mapping,
    require_sequence,
)
from tests.helpers.rendering import render_project
from tests.helpers.subprocess_env import generated_project_env

PASSING_UI_TEST = """//! Compile-time contract fixture.

#[test]
fn accepts_the_supported_shape() {
    assert_eq!(1 + 1, 2, "arithmetic must hold");
}
"""

FAILING_UI_TEST = """//! Compile-time contract fixture.

#[test]
fn rejects_the_supported_shape() {
    assert_eq!(1 + 1, 3, "the fixture must fail");
}
"""


def _run_make(
    project: Path, target: str, *arguments: str
) -> subprocess.CompletedProcess[str]:
    """Run a generated-project Make target and capture its output."""
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"
    return subprocess.run(
        [make, target, *arguments],
        cwd=project,
        env=generated_project_env({}),
        check=False,
        capture_output=True,
        text=True,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    """Return combined standard output and standard error."""
    return f"{result.stdout}\n{result.stderr}"


def test_rendered_nextest_configuration_bounds_test_execution(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Rendered nextest configuration bounds each test and compiler work."""
    project = render_project(
        tmp_path,
        copier,
        project_name="NextestExample",
        package_name="nextest_example",
    )

    config = parse_toml_file(project / ".config/nextest.toml")
    profile = require_mapping(config, "profile", ".config/nextest.toml")
    default = require_mapping(profile, "default", "nextest profile")

    assert default.get("slow-timeout") == {
        "period": "180s",
        "terminate-after": 1,
        "grace-period": "5s",
    }, "expected nextest to bound every single test run"
    assert default.get("global-timeout") == "90m", (
        "expected nextest to bound the whole run"
    )

    ui = require_mapping(profile, "ui", "nextest ui profile")
    assert ui.get("inherits") == "default", (
        "expected the UI profile to inherit the bounded run defaults"
    )

    ui_overrides = [
        override
        for override in require_sequence(ui, "overrides", "nextest ui profile")
        if isinstance(override, dict)
    ]
    assert any(override.get("filter") == "all()" for override in ui_overrides), (
        "expected the UI profile to select every target it is asked to run"
    )
    assert any(
        override.get("test-group") == "nested-cargo" for override in ui_overrides
    ), "expected compile-time tests to share the serialized nested-Cargo group"
    compile_timeouts = [
        override["slow-timeout"]
        for override in ui_overrides
        if "slow-timeout" in override
    ]
    assert compile_timeouts == [
        {"period": "180s", "terminate-after": 3, "grace-period": "5s"}
    ], "expected compile-time tests to tolerate nested compiler invocations"
    assert "binary(compile_" not in (project / ".config/nextest.toml").read_text(
        encoding="utf-8"
    ), "nextest rejects a binary filter that names no binary in the project"

    groups = require_mapping(config, "test-groups", ".config/nextest.toml")
    nested_cargo = require_mapping(groups, "nested-cargo", "nextest test groups")
    assert nested_cargo.get("max-threads") == 1, (
        "expected nested Cargo invocations to run one at a time"
    )


def test_rendered_test_ui_lane_selects_compile_targets(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Rendered test-ui runs compile-time targets and is a clean no-op without them."""
    project = render_project(
        tmp_path,
        copier,
        project_name="UiLaneExample",
        package_name="ui_lane_example",
    )
    target = project / "tests" / "compile_accept.rs"

    empty = _run_make(project.path, "test-ui")

    assert empty.returncode == 0, (
        "expected the UI lane to succeed without compile-time targets\n"
        f"output:\n{_output(empty)}"
    )
    assert "No compile-time UI test targets" in _output(empty), (
        "expected the UI lane to report an intentional no-op\n"
        f"output:\n{_output(empty)}"
    )

    target.write_text(PASSING_UI_TEST, encoding="utf-8")
    accepted = _run_make(project.path, "test-ui")

    assert accepted.returncode == 0, (
        "expected the UI lane to run a passing compile-time target\n"
        f"output:\n{_output(accepted)}"
    )
    assert "compile_accept" in _output(accepted), (
        "expected the UI lane to name the selected target\n"
        f"output:\n{_output(accepted)}"
    )
    makefile = read_generated_text(project / "Makefile")
    assert "--profile ui" in makefile, (
        "expected the UI lane to run nextest with the serialized profile"
    )

    fallback = _run_make(project.path, "test-ui", "TEST_CMD=test")

    assert fallback.returncode == 0, (
        f"expected the UI lane to fall back to cargo test\noutput:\n{_output(fallback)}"
    )

    target.write_text(FAILING_UI_TEST, encoding="utf-8")
    rejected = _run_make(project.path, "test-ui")

    assert rejected.returncode != 0, (
        "expected the UI lane to fail a failing compile-time target\n"
        f"output:\n{_output(rejected)}"
    )
    assert "compile_accept" in _output(rejected), (
        "expected the UI lane failure to identify the failing target\n"
        f"output:\n{_output(rejected)}"
    )


def test_rendered_workflows_provision_the_formatter_and_run_the_ui_lane(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Rendered workflows install mdtablefix and run the UI lane before coverage."""
    project = render_project(
        tmp_path,
        copier,
        project_name="WorkflowLaneExample",
        package_name="workflow_lane_example",
    )
    ci = read_generated_text(project / ".github/workflows/ci.yml")

    for workflow_name in ("ci.yml", "coverage-main.yml"):
        workflow = read_generated_text(project / ".github/workflows" / workflow_name)
        assert "make test-ui" in workflow, (
            f"expected {workflow_name} to run the explicit UI lane"
        )
        assert workflow.index("make test-ui") < workflow.index(
            "Test and Measure Coverage"
        ), f"expected {workflow_name} to run the UI lane before coverage"

    assert "install-mdtablefix@38905b4b2caec5b049438e6dc3f3f6b36c04d2df" in ci, (
        "expected CI to install the pinned Markdown formatter at a full commit SHA"
    )
    assert ci.index("install-mdtablefix") < ci.index("name: Format"), (
        "expected CI to provision the formatter before the formatting gate"
    )
