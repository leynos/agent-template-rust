"""Assert rendered Polonius toolchain and documentation contracts."""

from __future__ import annotations

import re
from typing import Any

import tomllib

from tests.helpers.generated_files import (
    parse_yaml_mapping,
    require_mapping,
    require_sequence,
)

POLONIUS_FLAG = "-Zpolonius=next"
RUSTFLAGS_PASSTHROUGH_REVISION = "b804b69fa7f978cf9091b9d9bd5481d8ce58c2ea"
_SETUP_RUST_USES_RE = re.compile(
    r"^leynos/shared-actions/\.github/actions/setup-rust@[0-9a-f]{40}$"
)
_SHARED_ACTION_USES_RE = re.compile(
    r"uses:\s+(?P<reference>leynos/shared-actions/[^\s]+)"
)


def _named_step(workflow: str, job_name: str, step_name: str) -> dict[str, Any]:
    """Return one named step from a rendered workflow."""
    parsed = parse_yaml_mapping(workflow, f"{job_name} workflow")
    jobs = require_mapping(parsed, "jobs", f"{job_name} workflow")
    job = require_mapping(jobs, job_name, f"{job_name} workflow jobs")
    steps = require_sequence(job, "steps", f"{job_name} workflow job")
    matches = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == step_name
    ]
    assert len(matches) == 1, f"expected one {step_name!r} step in {job_name}"
    return matches[0]


def _setup_rust_step(workflow: str, job_name: str) -> dict[str, Any]:
    """Return the setup-rust step from a rendered workflow job."""
    parsed = parse_yaml_mapping(workflow, f"{job_name} workflow")
    jobs = require_mapping(parsed, "jobs", f"{job_name} workflow")
    job = require_mapping(jobs, job_name, f"{job_name} workflow jobs")
    steps = require_sequence(job, "steps", f"{job_name} job")
    matches = [
        step
        for step in steps
        if isinstance(step, dict)
        and _SETUP_RUST_USES_RE.fullmatch(str(step.get("uses", "")))
    ]
    assert len(matches) == 1, f"expected one setup-rust step in {job_name} workflow"
    return matches[0]


def _assert_setup_rust_rustflags(
    workflow: str, job_name: str, *, enabled: bool
) -> None:
    """Assert setup-rust receives the selected Polonius configuration."""
    setup = _setup_rust_step(workflow, job_name)
    setup_inputs = require_mapping(setup, "with", f"{job_name} setup-rust step")
    expected = POLONIUS_FLAG if enabled else "-D warnings"
    actual = setup_inputs.get("rustflags")
    assert actual == expected, (
        f"expected {job_name} setup-rust rustflags to be {expected!r}, got {actual!r}"
    )


def _assert_rust_setup_log(workflow: str, job_name: str) -> None:
    """Assert post-setup diagnostics expose only bounded Rust configuration."""
    log_step = _named_step(workflow, job_name, "Log Rust compiler configuration")
    actual = str(log_step.get("run", "")).splitlines()
    expected = ["rustc --version", "printf 'Base RUSTFLAGS: %s\\n' \"$RUSTFLAGS\""]
    assert actual == expected, (
        f"expected {job_name} Rust setup log commands to be {expected!r}, "
        f"got {actual!r}"
    )


def _assert_cargo_config(cargo_config: str, *, enabled: bool, dev_target: str) -> None:
    """Assert Cargo's build and target rustflags retain Polonius as required."""
    config = tomllib.loads(cargo_config)
    build_flags = config.get("build", {}).get("rustflags", [])
    rustdoc_flags = config.get("build", {}).get("rustdocflags", [])
    assert (POLONIUS_FLAG in build_flags) is enabled, (
        "expected build.rustflags Polonius state to match the Copier answer"
    )
    assert (POLONIUS_FLAG in rustdoc_flags) is enabled, (
        "expected build.rustdocflags Polonius state to match the Copier answer"
    )
    assert "-Zcodegen-backend=cranelift" in build_flags, (
        "expected development builds to select the Cranelift backend"
    )
    assert "-Zthreads=8" in build_flags, (
        "expected development builds to run the rustc frontend on eight threads"
    )
    if "linux" not in dev_target:
        return
    linux_table = config["target"].get('cfg(target_os = "linux")')
    assert linux_table is not None, (
        "expected the Linux cfg table that supplies the mold link flag"
    )
    # The linker and the flag that needs it live in one table: a target that
    # receives `-fuse-ld=mold` must also receive the driver that accepts it,
    # and the `cfg` table matches every Linux target rather than the requested
    # development triple alone.
    assert linux_table.get("linker") == "clang", (
        "expected the Linux cfg table to select the clang driver for mold"
    )
    target_flags = linux_table["rustflags"]
    assert (POLONIUS_FLAG in target_flags) is enabled, (
        "target rustflags override build.rustflags and must preserve the "
        "selected Polonius state"
    )
    assert "-Clink-arg=-fuse-ld=mold" in target_flags, (
        "expected the Linux cfg table to select the mold linker"
    )
    for repeated_flag in ("-Zthreads=8", "-Zcodegen-backend=cranelift"):
        assert repeated_flag in target_flags, (
            f"expected the Linux cfg table to repeat {repeated_flag!r}, because "
            "a matching target table replaces build.rustflags"
        )
    assert set(config["target"]) == {'cfg(target_os = "linux")'}, (
        "expected the Linux cfg table to be the only target override, so every "
        "other target keeps its platform linker"
    )


def _assert_makefile(makefile: str, *, enabled: bool, dev_target: str) -> None:
    """Assert every generated compile path preserves the selected flag."""
    expected_default = (
        f"POLONIUS_FLAGS ?= {POLONIUS_FLAG}" if enabled else "POLONIUS_FLAGS ?="
    )
    assert expected_default in makefile
    assert (
        "COVERAGE_RUST_FLAGS ?= $(RUST_FLAGS) $(POLONIUS_FLAGS) "
        "-C link-arg=$(COVERAGE_LINKER_FLAGS)"
    ) in makefile, "expected coverage to compose its own Polonius flag route"
    assert (
        "DEV_RUST_FLAGS ?= $(RUST_FLAGS) $(POLONIUS_FLAGS) $(DEV_CODEGEN_FLAGS) "
        "$(DEV_LINKER_FLAGS)" in makefile
    ), "expected development builds to compose Polonius, codegen, and linker flags"
    assert "WHITAKER_RUST_FLAGS ?= $(RUST_FLAGS) $(POLONIUS_FLAGS)" in makefile, (
        "expected Whitaker to compose its own Polonius flag route"
    )
    assert "RELEASE_RUST_FLAGS ?= $(POLONIUS_FLAGS)" in makefile, (
        "expected release to compose its own Polonius flag route"
    )
    assert "RUSTDOC_FLAGS ?=" in makefile
    assert (
        "RUSTDOC_FLAGS := --cfg docsrs -D warnings $(POLONIUS_FLAGS) $(RUSTDOC_FLAGS)"
    ) in makefile, (
        "RUSTDOC_FLAGS must require POLONIUS_FLAGS while preserving inherited flags"
    )
    linker_default = next(
        line for line in makefile.splitlines() if line.startswith("DEV_LINKER_FLAGS ?=")
    )
    if "linux" in dev_target:
        assert "$(filter Linux,$(shell uname -s))" in linker_default
        assert "-fuse-ld=mold" in linker_default
    else:
        assert linker_default == "DEV_LINKER_FLAGS ?="
    compile_lines = [
        line
        for line in makefile.splitlines()
        if "RUSTFLAGS=" in line and ("$(CARGO)" in line or "$(WHITAKER)" in line)
    ]
    assert compile_lines, "expected generated compile recipes to set RUSTFLAGS"
    composed_routes = (
        "$(DEV_RUST_FLAGS)",
        "$(COVERAGE_RUST_FLAGS)",
        "$(WHITAKER_RUST_FLAGS)",
        "$(RELEASE_RUST_FLAGS)",
    )
    assert all(
        any(route in line for route in composed_routes) for line in compile_lines
    ), f"compile recipes must use composed Rust flags: {compile_lines!r}"
    coverage_recipe = makefile.partition("coverage:")[2].partition("\n\n")[0]
    assert 'RUSTFLAGS="$(COVERAGE_RUST_FLAGS)"' in coverage_recipe, (
        "coverage recipe must use composed coverage Rust flags"
    )
    whitaker_recipe = next(
        line
        for line in makefile.splitlines()
        if "$(WHITAKER)" in line and "RUSTFLAGS=" in line
    )
    assert 'RUSTFLAGS="$(WHITAKER_RUST_FLAGS)"' in whitaker_recipe, (
        "Whitaker must use its own flag route"
    )
    release_recipe = next(
        line for line in makefile.splitlines() if "$(RELEASE_CARGO)" in line
    )
    assert 'RUSTFLAGS="$(RELEASE_RUST_FLAGS)"' in release_recipe, (
        "release must use its own flag route"
    )
    for route_name, recipe in (
        ("Whitaker", whitaker_recipe),
        ("coverage", coverage_recipe),
        ("release", release_recipe),
    ):
        assert "codegen" not in recipe, (
            f"{route_name} must stay free of the development codegen backend"
        )
    rustdoc_lines = [
        line
        for line in makefile.splitlines()
        if "$(CARGO) test --doc" in line or "$(CARGO) doc" in line
    ]
    assert len(rustdoc_lines) == 2, (
        f"expected exactly two rustdoc recipes, got: {rustdoc_lines!r}"
    )
    assert all('RUSTDOCFLAGS="$(RUSTDOC_FLAGS)"' in line for line in rustdoc_lines), (
        f"rustdoc recipes must use composed rustdoc flags: {rustdoc_lines!r}"
    )


def _assert_coverage_workflow(workflow: str, job_name: str, *, enabled: bool) -> None:
    """Assert coverage's explicit RUSTFLAGS do not shadow Polonius."""
    coverage_step = _named_step(workflow, job_name, "Test and Measure Coverage")
    env = require_mapping(coverage_step, "env", "coverage step")
    actual = str(env.get("RUSTFLAGS", ""))
    base_flags = POLONIUS_FLAG if enabled else "-D warnings"
    expected = f"{base_flags} -C link-arg=-fuse-ld=lld"
    assert actual == expected, (
        f"expected {job_name} coverage RUSTFLAGS to be {expected!r}, got {actual!r}"
    )
    log_step = _named_step(workflow, job_name, "Log coverage linker configuration")
    actual_log = str(log_step.get("run", ""))
    expected_log = f'echo "Coverage RUSTFLAGS: {expected}"'
    assert expected_log in actual_log, (
        f"expected {job_name} coverage log to contain {expected_log!r}, "
        f"got {actual_log!r}"
    )


def _assert_shared_action_passthrough_revision(
    workflow: str, workflow_name: str
) -> None:
    """Assert affected shared-action refs include the rustflags capability."""
    references = [
        match.group("reference")
        for match in _SHARED_ACTION_USES_RE.finditer(workflow)
        if "/.github/actions/setup-rust@" in match.group("reference")
    ]
    assert references, f"expected shared setup-rust references in {workflow_name}"
    unexpected = [
        reference
        for reference in references
        if not reference.endswith(f"@{RUSTFLAGS_PASSTHROUGH_REVISION}")
    ]
    assert not unexpected, (
        f"expected {workflow_name} shared-action references to use rustflags "
        f"passthrough revision {RUSTFLAGS_PASSTHROUGH_REVISION!r}, "
        f"got {unexpected!r}"
    )


def _assert_release_workflow(release_workflow: str, *, enabled: bool) -> None:
    """Assert release builds follow the project's borrow-checker mode."""
    setup = _setup_rust_step(release_workflow, "build")
    setup_inputs = require_mapping(setup, "with", "release setup-rust step")
    actual_toolchain = str(setup_inputs.get("toolchain", ""))
    expected_flags = POLONIUS_FLAG if enabled else ""
    # A Polonius release must use the same dated nightly as development,
    # because the source does not compile without the analysis.
    # `rust-toolchain.toml` is that toolchain's single source of truth, so the
    # input is empty and setup-rust installs whatever the file pins. A release
    # without Polonius overrides the file with stable, whose Cargo must parse
    # the generated configuration.
    expected_toolchain = "" if enabled else "stable"
    assert actual_toolchain == expected_toolchain, (
        "expected the release setup-rust toolchain input to be "
        f"{expected_toolchain!r}, got {actual_toolchain!r}"
    )
    assert setup_inputs.get("rustflags") == expected_flags, (
        "expected the release setup-rust input to carry only the flags its "
        f"borrow-checker mode needs, got {setup_inputs.get('rustflags')!r}"
    )
    cargo_toolchain = "" if enabled else "+stable "
    rustup_toolchain = "" if enabled else "--toolchain stable "
    expected_commands = {
        "Build release binary (cross)": f"cross {cargo_toolchain}build --release",
        "Build release binary (native)": f"cargo {cargo_toolchain}build --release",
    }
    for step_name, expected_command in expected_commands.items():
        build = _named_step(release_workflow, "build", step_name)
        actual_command = str(build.get("run", ""))
        assert expected_command in actual_command, (
            f"expected {step_name} command to contain {expected_command!r}, "
            f"got {actual_command!r}"
        )
        build_env = require_mapping(build, "env", f"{step_name} step")
        assert build_env.get("RUSTFLAGS") == expected_flags, (
            f"expected {step_name} to carry only its mode's flags, "
            f"got {build_env.get('RUSTFLAGS')!r}"
        )
    native_target = _named_step(release_workflow, "build", "Add native target")
    expected_rustup = f'rustup target add {rustup_toolchain}"${{{{ matrix.target }}}}"'
    assert expected_rustup in str(native_target.get("run", "")), (
        "expected the native leg to add its target to the release toolchain, "
        f"got {native_target.get('run')!r}"
    )
    cross = _named_step(release_workflow, "build", "Build release binary (cross)")
    cross_env = require_mapping(cross, "env", "cross release step")
    assert cross_env.get("CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER") == "cc", (
        "expected the cross image's host triple to link with gcc, because the "
        "container has no clang"
    )
    # The generated Cargo configuration selects clang for every Linux target,
    # and the cross image has gcc only. The override is written per matrix
    # target because its variable name carries the target, and it is limited to
    # Linux legs so the Windows and FreeBSD legs keep their default linker.
    linker_step = _named_step(release_workflow, "build", "Select the cross linker")
    assert linker_step.get("if") == (
        "matrix.builder == 'cross' && contains(matrix.target, 'linux')"
    ), (
        "expected the cross linker override to be limited to cross-built Linux "
        f"targets, got {linker_step.get('if')!r}"
    )
    linker_run = str(linker_step.get("run", ""))
    assert "CARGO_TARGET_%s_LINKER=cc" in linker_run, (
        "expected the cross linker step to override the matrix target's linker"
    )
    assert "$GITHUB_ENV" in linker_run, (
        "expected the cross linker override to reach later steps"
    )
    for development_flag in ("-Zthreads=8", "-Zcodegen-backend=cranelift"):
        assert development_flag not in release_workflow, (
            f"expected the release workflow to omit {development_flag!r}"
        )
    _assert_rust_setup_log(release_workflow, "build")


def assert_polonius_toolchain_contracts(
    *,
    enabled: bool,
    dev_target: str,
    cargo_config: str,
    makefile: str,
    rust_toolchain: str,
    ci_workflow: str,
    coverage_main_workflow: str,
    audit_workflow: str,
    act_validation_workflow: str,
    release_workflow: str | None,
    agents: str,
    readme: str,
    docs_contents: str,
    repository_layout: str,
    developers_guide: str,
    users_guide: str,
    polonius_doc: str | None,
) -> None:
    """Assert the selected Polonius state across generated project surfaces.

    Parameters
    ----------
    enabled : bool
        Expected Polonius selection for the rendered project.
    dev_target : str
        Development target represented in the rendered Cargo and Make files.
    cargo_config : str
        Rendered Cargo configuration.
    makefile : str
        Rendered Makefile.
    rust_toolchain : str
        Rendered Rust toolchain configuration.
    ci_workflow : str
        Rendered Continuous Integration workflow.
    coverage_main_workflow : str
        Rendered main-branch coverage workflow.
    audit_workflow : str
        Rendered scheduled dependency audit workflow.
    act_validation_workflow : str
        Rendered act-validation workflow.
    release_workflow : str | None
        Rendered release workflow, or ``None`` when the project has none.
    agents : str
        Rendered agent guidance.
    readme : str
        Rendered project README.
    docs_contents : str
        Rendered documentation contents page.
    repository_layout : str
        Rendered repository layout documentation.
    developers_guide : str
        Rendered developers guide.
    users_guide : str
        Rendered users guide.
    polonius_doc : str | None
        Rendered Polonius policy, or ``None`` when Polonius is disabled.

    Raises
    ------
    AssertionError
        If any rendered surface does not match the selected Polonius state.
    """
    _assert_cargo_config(cargo_config, enabled=enabled, dev_target=dev_target)
    _assert_makefile(makefile, enabled=enabled, dev_target=dev_target)
    _assert_setup_rust_rustflags(ci_workflow, "build-test", enabled=enabled)
    _assert_setup_rust_rustflags(
        coverage_main_workflow, "coverage-upload", enabled=enabled
    )
    _assert_rust_setup_log(ci_workflow, "build-test")
    _assert_rust_setup_log(coverage_main_workflow, "coverage-upload")
    _assert_shared_action_passthrough_revision(ci_workflow, "CI workflow")
    _assert_shared_action_passthrough_revision(
        coverage_main_workflow, "coverage-main workflow"
    )
    _assert_shared_action_passthrough_revision(audit_workflow, "audit workflow")
    _assert_shared_action_passthrough_revision(
        act_validation_workflow, "act-validation workflow"
    )
    _assert_coverage_workflow(ci_workflow, "build-test", enabled=enabled)
    _assert_coverage_workflow(
        coverage_main_workflow, "coverage-upload", enabled=enabled
    )
    if release_workflow is not None:
        _assert_shared_action_passthrough_revision(release_workflow, "release workflow")
        _assert_release_workflow(release_workflow, enabled=enabled)

    if enabled:
        assert "Polonius alpha" in rust_toolchain
        assert polonius_doc is not None
        assert POLONIUS_FLAG in polonius_doc
        for surface in (
            agents,
            readme,
            docs_contents,
            repository_layout,
            developers_guide,
            users_guide,
        ):
            assert "Polonius" in surface
    else:
        assert "Polonius" not in rust_toolchain
        assert polonius_doc is None
        for surface in (
            agents,
            readme,
            docs_contents,
            repository_layout,
            developers_guide,
            users_guide,
        ):
            assert "Polonius" not in surface
