"""Rendered application release workflow tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_copier.plugin import CopierFixture

from tests.helpers.delivery_workflows import (
    DOWNLOAD_ARTIFACT_USES_RE,
    SETUP_RUST_USES_RE,
    SOFT_PROPS_RELEASE_USES_RE,
    UPLOAD_ARTIFACT_USES_RE,
    named_step,
    render_delivery_project,
    steps,
)
from tests.helpers.generated_files import (
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
    require_sequence,
)
from tests.helpers.rendering import APP, LIB


def _assert_matrix_legs(build: dict[str, Any]) -> None:
    """Assert each matrix leg's runner agrees with its builder and target."""
    strategy = require_mapping(build, "strategy", "release build job")
    assert strategy.get("fail-fast") is False, (
        "expected one failing leg not to cancel the others"
    )
    matrix = require_mapping(strategy, "matrix", "release build strategy")
    include = require_sequence(matrix, "include", "release build matrix")
    assert include, "expected release matrix legs"
    targets = [str(entry["target"]) for entry in include]
    assert len(targets) == len(set(targets)), "expected one leg per target"
    for entry in include:
        builder = entry["builder"]
        runner = str(entry["runner"])
        target = str(entry["target"])
        if builder == "cargo":
            assert runner.startswith("macos-"), (
                f"expected native builder for {target} to use a macOS runner"
            )
        else:
            assert builder == "cross", f"expected {target} to use the cross builder"
            assert runner == "ubuntu-latest", (
                f"expected cross builder for {target} to use a Linux runner"
            )
    runners_by_target = {entry["target"]: entry["runner"] for entry in include}
    assert runners_by_target["x86_64-apple-darwin"] == "macos-15-intel", (
        "expected the Intel macOS target to use the Intel runner"
    )
    assert runners_by_target["aarch64-apple-darwin"] == "macos-latest", (
        "expected the Apple Silicon target to use the arm64 runner"
    )


def _assert_build_steps(build: dict[str, Any]) -> None:
    """Assert the build job uses stable Cargo and uploads checksummed artefacts."""
    build_steps = steps(build, "release build job")
    setup = next(
        step
        for step in build_steps
        if SETUP_RUST_USES_RE.fullmatch(str(step.get("uses", "")))
    )
    setup_inputs = require_mapping(setup, "with", "release setup-rust step")
    assert setup_inputs.get("use-sccache") == "false", (
        "expected a release build not to install or save sccache"
    )
    assert setup_inputs.get("expect-cache") == "any", (
        "expected a release build to tolerate an empty or populated cache"
    )
    assert setup_inputs.get("toolchain") == "stable", (
        "expected the release build to use stable Cargo"
    )
    assert "rustflags" not in setup_inputs, (
        "expected no nightly development flags on the release toolchain"
    )

    native = named_step(build, "Build release binary (native)", "release build job")
    native_command = str(native.get("run", ""))
    assert native_command.startswith("cargo +stable build --release --target "), (
        "expected the native leg to build with stable Cargo"
    )
    native_env = require_mapping(native, "env", "native release step")
    assert native_env.get("RUSTFLAGS") == "", (
        "expected the native release build to clear inherited Rust flags"
    )
    cross = named_step(build, "Build release binary (cross)", "release build job")
    cross_command = str(cross.get("run", ""))
    assert cross_command.startswith("cross +stable build --release --target "), (
        "expected the cross leg to build with stable Cargo"
    )
    cross_env = require_mapping(cross, "env", "cross release step")
    assert cross_env.get("RUSTFLAGS") == "", (
        "expected the cross release build to clear inherited Rust flags"
    )
    assert cross_env.get("CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER") == "cc", (
        "expected the cross image to use gcc rather than the clang config"
    )
    add_target = named_step(build, "Add native target", "release build job")
    assert 'rustup target add --toolchain stable "${{ matrix.target }}"' in str(
        add_target.get("run")
    ), "expected the native target to be added to the stable toolchain"
    prepare = named_step(build, "Prepare artifact", "release build job")
    assert "shasum -a 256" in str(prepare.get("run")), (
        "expected a checksum beside every release artefact"
    )
    assert any(
        UPLOAD_ARTIFACT_USES_RE.fullmatch(str(step.get("uses", "")))
        for step in build_steps
    ), "expected release artefacts to be uploaded by a pinned action"


def _assert_release_job(jobs: dict[str, Any]) -> None:
    """Assert the release job waits for every leg and publishes safely."""
    release = require_mapping(jobs, "release", "release workflow jobs")
    assert release.get("needs") == "build", (
        "expected the release job to wait for every build leg"
    )
    assert require_mapping(release, "permissions", "release job") == {
        "contents": "write"
    }, "expected the release job to need only content write access"
    release_steps = steps(release, "release job")
    assert any(
        DOWNLOAD_ARTIFACT_USES_RE.fullmatch(str(step.get("uses", "")))
        for step in release_steps
    ), "expected the release job to fetch the build artefacts"
    assert any(
        SOFT_PROPS_RELEASE_USES_RE.fullmatch(str(step.get("uses", "")))
        for step in release_steps
    ), "expected the release job to publish through the pinned release action"


def test_application_release_matrix_uses_native_macos_and_cross_builders(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Each matrix leg's runner agrees with its builder and target."""
    project = render_delivery_project(
        tmp_path,
        copier,
        flavour=APP,
        project_name="ReleaseMatrix",
        package_name="release_matrix",
    )
    workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/release.yml"),
        "release workflow",
    )
    jobs = require_mapping(workflow, "jobs", "release workflow")
    build = require_mapping(jobs, "build", "release workflow jobs")

    _assert_matrix_legs(build)
    _assert_build_steps(build)
    _assert_release_job(jobs)


def test_library_render_has_no_release_workflow(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """A library has no application binary to release."""
    project = render_delivery_project(
        tmp_path,
        copier,
        flavour=LIB,
        project_name="LibraryRelease",
        package_name="library_release",
    )

    assert not (project / ".github/workflows/release.yml").exists(), (
        "expected a library render to omit the application release workflow"
    )
