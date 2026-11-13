"""Tests for the rustflags composition of the generated Make routes.

Each Make route compiles under a different strategy: development builds use
Cranelift and mold, coverage uses lld, Whitaker and release stay free of the
development codegen backend. These tests render a project, replace Cargo and
Whitaker with logging stubs, and assert the RUSTFLAGS each route supplies.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.build_tool_sandbox import TEMPLATE_MOLD, write_executable
from tests.helpers.rendering import render_project
from tests.helpers.subprocess_env import generated_project_env


def _write_logging_stub(sandbox_bin: Path, name: str) -> Path:
    """Write a stub that appends its arguments and RUSTFLAGS to FLAG_LOG."""
    body = (
        "#!/bin/sh\n"
        'if [ "${RUSTFLAGS+x}" = x ]; then\n'
        '  flags="RUSTFLAGS=$RUSTFLAGS"\n'
        "else\n"
        '  flags="RUSTFLAGS=<unset>"\n'
        "fi\n"
        'printf \'%s\\t%s\\t%s\\n\' __NAME__ "$*" "$flags" >> "$FLAG_LOG"\n'
        "exit 0\n"
    ).replace("__NAME__", name)
    return write_executable(sandbox_bin / name, body)


@dataclass(frozen=True)
class FlagRecord:
    """One recorded tool invocation and the RUSTFLAGS it received."""

    tool: str
    arguments: str
    flags: str


def _flag_records(log: Path) -> list[FlagRecord]:
    """Read the flag log, dropping the parse-time `cargo nextest` probe."""
    records = []
    for line in log.read_text("utf-8").splitlines():
        tool, arguments, flags = line.split("\t", 2)
        if arguments.startswith("nextest"):
            continue
        records.append(FlagRecord(tool, arguments, flags))
    return records


def _make_flag_sandbox(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create the stub directory, uname stub and flag log for route tests."""
    bin_dir = tmp_path / "flag-bin"
    bin_dir.mkdir()
    for tool in (
        "cargo",
        "whitaker",
        "yamllint",
        "actionlint",
        "shellcheck",
        "git",
        "xargs",
    ):
        _write_logging_stub(bin_dir, tool)
    uname = write_executable(bin_dir / "uname", "#!/bin/sh\necho Linux\n")
    assert uname.exists()
    return bin_dir, bin_dir / "uname", tmp_path / "flags.log"


def _run_make(
    project_root: Path,
    bin_dir: Path,
    log: Path,
    target: str,
    *,
    rustflags: str = "-C target-cpu=native",
) -> subprocess.CompletedProcess[str]:
    """Run one generated Make *target* against the logging stubs."""
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"
    if log.exists():
        log.unlink()
    return subprocess.run(
        [make, target],
        cwd=project_root,
        env=generated_project_env(
            {
                "PATH": f"{bin_dir}:{os.environ.get('PATH', os.defpath)}",
                "CARGO": str(bin_dir / "cargo"),
                "WHITAKER": str(bin_dir / "whitaker"),
                "YAMLLINT": str(bin_dir / "yamllint"),
                "ACTIONLINT": str(bin_dir / "actionlint"),
                "SHELLCHECK": str(bin_dir / "shellcheck"),
                "CHECK_BUILD_TOOLS": "true",
                "CHECK_RUST_TOOLCHAIN": "true",
                "CHECK_COVERAGE_TOOLS": "true",
                "FLAG_LOG": str(log),
                "RUSTFLAGS": rustflags,
            }
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _assert_common_flags(flags: str) -> None:
    """Assert the flags every route carries: warnings and inherited values."""
    assert "-C target-cpu=native" in flags, flags
    assert "-D warnings" in flags, flags


def _assert_no_development_codegen(flags: str, route: str) -> None:
    """Assert a route keeps the platform codegen and linker."""
    assert "-Zcodegen-backend=cranelift" not in flags, f"{route} must not use Cranelift"
    assert "-Zthreads=8" not in flags, f"{route} must not use the nightly thread flag"


@pytest.mark.parametrize("enable_polonius", [False, True], ids=["nll", "polonius"])
def test_make_routes_compose_the_intended_rustflags(
    tmp_path: Path, copier: CopierFixture, enable_polonius: bool
) -> None:
    """Each Make route sets the flags its compilation strategy requires."""
    project = render_project(
        tmp_path,
        copier,
        project_name="FlagRouteExample",
        package_name="flag_route_example",
        enable_polonius=enable_polonius,
    )
    bin_dir, _, log = _make_flag_sandbox(tmp_path)
    polonius = "-Zpolonius=next"

    build = _run_make(project.path, bin_dir, log, "build")
    assert build.returncode == 0, build.stderr
    build_flags = [record.flags for record in _flag_records(log)]
    assert build_flags, "expected the build recipe to invoke Cargo"
    for flags in build_flags:
        _assert_common_flags(flags)
        assert "-Zthreads=8" in flags, flags
        assert "-Zcodegen-backend=cranelift" in flags, flags
        assert "-C link-arg=-fuse-ld=mold" in flags, flags
        assert (polonius in flags) is enable_polonius, flags

    test = _run_make(project.path, bin_dir, log, "test")
    assert test.returncode == 0, test.stderr
    test_records = _flag_records(log)
    assert [record.arguments.split(" ", 1)[0] for record in test_records] == [
        "test",
        "test",
    ], test_records
    assert any("--doc" in record.arguments for record in test_records), test_records
    for record in test_records:
        _assert_common_flags(record.flags)
        assert "-Zcodegen-backend=cranelift" in record.flags, record.flags
        assert (polonius in record.flags) is enable_polonius, record.flags

    lint = _run_make(project.path, bin_dir, log, "lint")
    assert lint.returncode == 0, lint.stderr
    lint_records = _flag_records(log)
    whitaker = [record for record in lint_records if record.tool == "whitaker"]
    assert whitaker, f"expected a Whitaker invocation; records={lint_records}"
    for record in whitaker:
        _assert_common_flags(record.flags)
        _assert_no_development_codegen(record.flags, "Whitaker")
        assert (polonius in record.flags) is enable_polonius, record.flags

    coverage = _run_make(project.path, bin_dir, log, "coverage")
    assert coverage.returncode == 0, coverage.stderr
    coverage_records = _flag_records(log)
    assert len(coverage_records) == 1, coverage_records
    coverage_flags = coverage_records[0].flags
    _assert_common_flags(coverage_flags)
    _assert_no_development_codegen(coverage_flags, "coverage")
    assert "-C link-arg=-fuse-ld=lld" in coverage_flags, coverage_flags
    assert (polonius in coverage_flags) is enable_polonius, coverage_flags

    release = _run_make(project.path, bin_dir, log, "release")
    assert release.returncode == 0, release.stderr
    release_records = _flag_records(log)
    assert len(release_records) == 1, release_records
    release_flags = release_records[0].flags
    _assert_no_development_codegen(release_flags, "release")
    assert (polonius in release_flags) is enable_polonius, release_flags
    if enable_polonius:
        assert release_records[0].arguments.startswith("build"), release_records[0]
    else:
        assert release_records[0].arguments.startswith("+stable build"), (
            release_records[0]
        )
        assert release_flags == "RUSTFLAGS=", (
            "expected the stable release recipe to clear inherited flags; "
            f"actual={release_flags!r}"
        )


@pytest.mark.parametrize("enable_polonius", [False, True], ids=["nll", "polonius"])
def test_stable_cargo_parses_the_rendered_configuration(
    tmp_path: Path, copier: CopierFixture, enable_polonius: bool
) -> None:
    """Stable Cargo accepts the generated `.cargo/config.toml` with dev flags."""
    project = render_project(
        tmp_path,
        copier,
        project_name="StableMetadataExample",
        package_name="stable_metadata_example",
        enable_polonius=enable_polonius,
    )
    cargo = shutil.which("cargo")
    assert cargo is not None, "expected cargo to be available for generated tests"

    result = subprocess.run(
        [cargo, "+stable", "metadata", "--no-deps", "--format-version", "1"],
        cwd=project.path,
        env=generated_project_env({}),
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert result.returncode == 0, (
        "expected stable Cargo to parse the rendered configuration\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    metadata = json.loads(result.stdout)
    assert metadata["packages"], "expected metadata to describe the generated package"


def test_rendered_project_ships_the_build_tool_assets(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """The rendered project carries executable scripts and the mould pins."""
    project = render_project(
        tmp_path,
        copier,
        project_name="BuildToolAssetsExample",
        package_name="build_tool_assets_example",
    )

    for name in (
        "build-tools-common.sh",
        "check-build-tools.sh",
        "exclude-ui-targets.sh",
        "install-build-tools.sh",
    ):
        script = project / "scripts" / name
        assert script.is_file(), f"expected rendered script {name}"
        assert os.access(script, os.X_OK), (
            f"expected rendered script {name} to be executable"
        )

    for pin in ("VERSION", "SHA256SUMS"):
        assert (project / "tools/mold" / pin).read_text("utf-8") == (
            TEMPLATE_MOLD / pin
        ).read_text("utf-8"), f"expected the rendered {pin} pin to match the template"
