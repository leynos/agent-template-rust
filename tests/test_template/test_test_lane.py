"""Rendered test lane tests."""

from __future__ import annotations

import re
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

TRYBUILD_UI_TEST = """//! Compile-time contract fixture driven by trybuild.

#[test]
fn accepts_the_supported_shape() {
    let cases = trybuild::TestCases::new();
    cases.pass("tests/compile-ui/pass.rs");
}
"""

TRYBUILD_PASS_CASE = """fn main() {
    assert_eq!(1 + 1, 2, "arithmetic must hold");
}
"""


def _add_trybuild_fixture(project: Path) -> None:
    """Add a compile-time target that builds a nested Cargo project."""
    manifest = project / "Cargo.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + '\n[dev-dependencies]\ntrybuild = "1"\n',
        encoding="utf-8",
    )
    (project / "tests" / "compile_accept.rs").write_text(
        TRYBUILD_UI_TEST, encoding="utf-8"
    )
    pass_case = project / "tests" / "compile-ui" / "pass.rs"
    pass_case.parent.mkdir(parents=True)
    pass_case.write_text(TRYBUILD_PASS_CASE, encoding="utf-8")


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


def _run_in_project(project: Path, *command: str) -> subprocess.CompletedProcess[str]:
    """Run a command in a rendered project without its development flags.

    The development flags select Cranelift and the `mold` linker, which this
    parent test does not provision. An empty ``RUSTFLAGS`` replaces them, and
    the target-scoped linker value replaces the rendered clang selection, so
    the assertion under test — which profile nextest loads — is the only
    variable.
    """
    return subprocess.run(
        list(command),
        cwd=project,
        env=generated_project_env(
            {
                "RUSTFLAGS": "",
                "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER": "cc",
            }
        ),
        check=False,
        capture_output=True,
        text=True,
    )


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
    assert ui.get("default-filter") == "all()", (
        "expected the UI profile to keep selecting every target it is asked "
        "for, including when the hosted coverage lane narrows the inherited "
        "default profile"
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
    assert compile_timeouts and compile_timeouts[0]["period"] == "600s", (
        "expected compile-time tests to tolerate nested compiler invocations "
        "that wait on the package-cache lock and compiler admission"
    )
    assert compile_timeouts[0]["terminate-after"] >= 2, (
        "expected the widened period to apply more than once before "
        "terminating a nested build"
    )
    assert "default-filter" not in default, (
        "nextest validates every profile's filter when it loads the "
        "configuration, so the checked-in default profile must not select "
        "compile-time targets by a binary filter that may name nothing"
    )
    active_lines = [
        line
        for line in (project / ".config/nextest.toml")
        .read_text(encoding="utf-8")
        .splitlines()
        if not line.lstrip().startswith("#")
    ]
    assert not any("binary(compile_" in line for line in active_lines), (
        "expected compile-time targets to be selected by name rather than by a "
        "binary filter; only the explanatory comments may mention the filter"
    )

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


def test_default_and_coverage_runs_leave_compile_targets_to_the_ui_lane(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """A real nested-Cargo target runs only in the UI lane, never twice."""
    project = render_project(
        tmp_path,
        copier,
        project_name="TrybuildLaneExample",
        package_name="trybuild_lane_example",
    )
    _add_trybuild_fixture(project.path)

    default_run = _run_make(project.path, "test")
    assert default_run.returncode == 0, (
        "expected the default test run to pass beside a compile-time target\n"
        f"output:\n{_output(default_run)}"
    )
    assert "nextest run" in _output(default_run), (
        f"expected the default run to use nextest\noutput:\n{_output(default_run)}"
    )
    assert "-E 'not binary(compile_*)'" in _output(default_run), (
        "expected the default run to exclude compile-time targets\n"
        f"output:\n{_output(default_run)}"
    )
    assert "compile_accept" not in _output(default_run), (
        "expected the default run not to repeat the UI lane's nested build\n"
        f"output:\n{_output(default_run)}"
    )

    ui_run = _run_make(project.path, "test-ui")
    assert ui_run.returncode == 0, (
        f"expected the UI lane to run a trybuild target\noutput:\n{_output(ui_run)}"
    )
    assert "compile_accept" in _output(ui_run), (
        f"expected the UI lane to run the trybuild target\noutput:\n{_output(ui_run)}"
    )

    makefile = read_generated_text(project / "Makefile")
    assert "$(CARGO) llvm-cov $(COVERAGE_NEXTEST)" in makefile, (
        "expected coverage to run the same nextest-based lane"
    )
    assert "$(TEST_FLAGS) $(TEST_UI_EXCLUDE)" in makefile, (
        "expected coverage to exclude compile-time targets through the same "
        "conditional filter as the default run"
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
        assert workflow.index(
            "Exclude compile-time targets from the coverage build"
        ) < workflow.index("Test and Measure Coverage"), (
            f"expected {workflow_name} to exclude compile-time targets from "
            "the coverage run"
        )
        assert "run: scripts/exclude-ui-targets.sh" in workflow, (
            f"expected {workflow_name} to deselect compile-time targets in the "
            "nextest profile instead of moving their source files"
        )
        assert "mv tests/compile_*.rs" not in workflow, (
            f"expected {workflow_name} to leave the compile-time targets in "
            "the crate, so an explicit [[test]] declaration keeps its file"
        )

    assert re.search(r"install-mdtablefix@[0-9a-f]{40}\b", ci), (
        "expected CI to install the Markdown formatter pinned to a full 40-hex "
        "commit SHA"
    )
    assert ci.index("install-mdtablefix") < ci.index("name: Format"), (
        "expected CI to provision the formatter before the formatting gate"
    )


def test_coverage_exclusion_narrows_the_profile_and_keeps_target_files(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """The coverage exclusion deselects UI targets without removing them.

    The shared coverage action runs workspace nextest with no filter argument,
    so the exclusion has to reach nextest through the project's profile. The
    fixture is a real ``trybuild`` target, whose test spawns a nested Cargo
    build, and the target stays in the crate, which keeps an explicit
    ``[[test]]`` declaration pointing at a source file that exists.
    """
    project = render_project(
        tmp_path,
        copier,
        project_name="ExclusionExample",
        package_name="exclusion_example",
    )
    root = project.path
    script = root / "scripts" / "exclude-ui-targets.sh"
    config_path = root / ".config" / "nextest.toml"
    assert script.stat().st_mode & 0o111, (
        "expected the exclusion script to be executable, because the coverage "
        "workflows run it directly"
    )

    untouched = config_path.read_text(encoding="utf-8")
    without_targets = _run_in_project(root, str(script))
    assert without_targets.returncode == 0, (
        "expected the exclusion to succeed without compile-time targets\n"
        f"output:\n{_output(without_targets)}"
    )
    assert "No compile-time UI targets" in _output(without_targets), (
        "expected the exclusion to report its intentional no-op\n"
        f"output:\n{_output(without_targets)}"
    )
    assert config_path.read_text(encoding="utf-8") == untouched, (
        "expected a project without UI targets to keep its nextest profile, "
        "because nextest rejects a filter that names no binary"
    )

    _add_trybuild_fixture(root)
    target = root / "tests" / "compile_accept.rs"
    manifest = root / "Cargo.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        + '\n[[test]]\nname = "compile_accept"\npath = "tests/compile_accept.rs"\n',
        encoding="utf-8",
    )

    excluded = _run_in_project(root, str(script))
    assert excluded.returncode == 0, (
        "expected the exclusion to narrow a profile that has a filter target\n"
        f"output:\n{_output(excluded)}"
    )
    default = require_mapping(
        require_mapping(parse_toml_file(config_path), "profile", "nextest config"),
        "default",
        "nextest default profile",
    )
    assert default.get("default-filter") == "not binary(compile_*)", (
        "expected the default profile to deselect the compile-time targets, "
        f"got {default.get('default-filter')!r}"
    )
    assert target.exists(), (
        "expected the target file to stay in place; only its tests are "
        "deselected, and an explicit [[test]] declaration still points at it"
    )

    coverage_run = _run_in_project(root, "cargo", "nextest", "run", "--all-features")
    assert coverage_run.returncode == 0, (
        "expected the filterless workspace run the coverage action performs to "
        "load the narrowed profile\n"
        f"output:\n{_output(coverage_run)}"
    )
    assert "replace_this_stub_when_real_tests_exist" in _output(coverage_run), (
        "expected the instrumented run to execute the project's own tests\n"
        f"output:\n{_output(coverage_run)}"
    )
    assert "accepts_the_supported_shape" not in _output(coverage_run), (
        "expected the instrumented run to skip compile-time targets\n"
        f"output:\n{_output(coverage_run)}"
    )

    ui_listed = _run_in_project(
        root,
        "cargo",
        "nextest",
        "list",
        "--all-features",
        "--profile",
        "ui",
        "--test",
        "compile_accept",
    )
    assert ui_listed.returncode == 0, (
        "expected the UI profile to keep its target selected even after the "
        f"default profile was narrowed\noutput:\n{_output(ui_listed)}"
    )
    assert "accepts_the_supported_shape" in _output(ui_listed), (
        "expected the UI profile to select the compile-time target\n"
        f"output:\n{_output(ui_listed)}"
    )

    repeated = _run_in_project(root, str(script))
    assert repeated.returncode == 0, (
        f"expected a repeated exclusion to succeed\noutput:\n{_output(repeated)}"
    )
    assert "already excludes" in _output(repeated), (
        f"expected a repeated exclusion to change nothing\noutput:\n{_output(repeated)}"
    )

    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'default-filter = "not binary(compile_*)"',
            'default-filter = "all()"',
        ),
        encoding="utf-8",
    )
    refused = _run_in_project(root, str(script))
    assert refused.returncode != 0, (
        "expected the exclusion to refuse a profile that already sets another "
        "filter rather than overwrite the project's choice\n"
        f"output:\n{_output(refused)}"
    )
    assert "default-filter" in _output(refused), (
        "expected the refusal to name the setting it cannot replace\n"
        f"output:\n{_output(refused)}"
    )
