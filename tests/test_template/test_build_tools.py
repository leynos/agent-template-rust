"""Tests for the pinned build-tool installer and capability checker.

The generated project ships three shell scripts and two mold pins. These tests
run the scripts against fake toolchains and fake mold releases so that checks,
installations and checksum failures are observable without touching the
machine. The rendered project is also checked for the assets and pins the
scripts depend on.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import pytest
import tomllib
from pytest_copier.plugin import CopierFixture

from tests.helpers.build_tool_sandbox import (
    CHANNEL,
    CRANELIFT,
    TEMPLATE_SCRIPTS,
    installed_component_lines,
    installer_env,
    make_sandbox,
    run_script,
    rustup_calls,
    script_env,
    write_mold_release,
    write_rustup_stub,
    write_version_stub,
    write_workspace_pins,
)
from tests.helpers.rendering import render_project
from tests.helpers.subprocess_env import generated_project_env

# The scripts gate mold installation and checking on Linux, so a non-Linux host
# never reaches the checksum, install, or version-report paths these tests
# exercise.
requires_linux = pytest.mark.skipif(
    platform.system() != "Linux",
    reason="the pinned mold installer and checker only act on Linux",
)


def test_checker_reports_a_missing_toolchain_without_installing(
    tmp_path: Path,
) -> None:
    """A missing pinned toolchain fails the check and never installs it."""
    sandbox = make_sandbox(tmp_path)
    write_workspace_pins(sandbox)
    write_rustup_stub(sandbox)
    write_version_stub(sandbox, "mold", "mold 9.9.9")
    write_version_stub(sandbox, "clang", "clang version 19.1.0")

    result = run_script(
        TEMPLATE_SCRIPTS / "check-build-tools.sh",
        script_env(sandbox, {"FAKE_TOOLCHAINS": ""}),
    )

    assert result.returncode != 0, result.stderr
    assert "is not installed" in result.stderr, result.stderr
    assert rustup_calls(sandbox) == [("0", "toolchain list")], (
        "expected the check to consult rustup once with auto-install disabled; "
        f"calls={rustup_calls(sandbox)}"
    )


def test_checker_reports_a_missing_component(tmp_path: Path) -> None:
    """A toolchain missing a pinned component fails and names the component."""
    sandbox = make_sandbox(tmp_path)
    write_workspace_pins(sandbox)
    write_rustup_stub(sandbox)
    write_version_stub(sandbox, "mold", "mold 9.9.9")
    write_version_stub(sandbox, "clang", "clang version 19.1.0")

    result = run_script(
        TEMPLATE_SCRIPTS / "check-build-tools.sh",
        script_env(
            sandbox,
            {
                "FAKE_TOOLCHAINS": f"{CHANNEL}-x86_64-unknown-linux-gnu (default)",
                "FAKE_COMPONENTS": installed_component_lines(
                    ("rustfmt", "rustc-codegen-cranelift")
                ),
            },
        ),
    )

    assert result.returncode != 0, result.stderr
    assert "component clippy is not installed" in result.stderr, result.stderr
    assert all(
        "component add" not in arguments for _, arguments in rustup_calls(sandbox)
    ), "expected the check to report the gap rather than install the component"


@requires_linux
def test_coverage_check_ignores_cranelift_but_requires_lld(tmp_path: Path) -> None:
    """Coverage preflight skips Cranelift and still requires the lld linker."""
    sandbox = make_sandbox(tmp_path)
    write_workspace_pins(sandbox, components=("rustfmt", "clippy", CRANELIFT))
    write_rustup_stub(sandbox)
    write_version_stub(sandbox, "clang", "clang version 19.1.0")
    lld = write_version_stub(sandbox, "ld.lld", "LLD 19.1.0")
    env = script_env(
        sandbox,
        {
            "FAKE_TOOLCHAINS": f"{CHANNEL}-x86_64-unknown-linux-gnu (default)",
            "FAKE_COMPONENTS": installed_component_lines(("rustfmt", "clippy")),
        },
    )

    passing = run_script(
        TEMPLATE_SCRIPTS / "check-build-tools.sh", env, "--coverage-only"
    )
    assert passing.returncode == 0, passing.stderr
    assert CRANELIFT not in passing.stderr, (
        "expected coverage preflight to skip the Cranelift component"
    )

    lld.unlink()
    failing = run_script(
        TEMPLATE_SCRIPTS / "check-build-tools.sh", env, "--coverage-only"
    )
    assert failing.returncode != 0, failing.stderr
    assert "lld" in failing.stderr, failing.stderr


def test_toolchain_only_check_skips_linkers(tmp_path: Path) -> None:
    """Toolchain-only preflight succeeds with no mold, clang or lld on PATH."""
    sandbox = make_sandbox(tmp_path)
    write_workspace_pins(sandbox)
    write_rustup_stub(sandbox)

    result = run_script(
        TEMPLATE_SCRIPTS / "check-build-tools.sh",
        script_env(
            sandbox,
            {
                "FAKE_TOOLCHAINS": f"{CHANNEL}-x86_64-unknown-linux-gnu (default)",
                "FAKE_COMPONENTS": installed_component_lines(
                    ("rustfmt", "clippy", CRANELIFT)
                ),
            },
        ),
        "--toolchain-only",
    )

    assert result.returncode == 0, result.stderr
    assert "mold" not in result.stderr, result.stderr


@requires_linux
def test_installer_refuses_a_corrupted_mold_archive(tmp_path: Path) -> None:
    """A checksum mismatch fails before extraction or toolchain installation."""
    sandbox = make_sandbox(tmp_path)
    version = "9.9.9"
    name, _ = write_mold_release(sandbox, version)
    write_workspace_pins(sandbox, version=version, sums=f"{'0' * 64}  {name}\n")
    write_rustup_stub(sandbox)

    result = run_script(
        TEMPLATE_SCRIPTS / "install-build-tools.sh", installer_env(sandbox, version)
    )

    assert result.returncode != 0, result.stderr
    assert "checksum mismatch" in result.stderr, result.stderr
    assert not (sandbox.base / "prefix" / "bin" / "mold").exists(), (
        "expected a rejected archive to install nothing"
    )
    assert rustup_calls(sandbox) == [], (
        "expected a checksum failure before any toolchain installation"
    )


@requires_linux
def test_installer_verifies_a_matching_archive_before_installing(
    tmp_path: Path,
) -> None:
    """A matching checksum installs mold and then the pinned toolchain."""
    sandbox = make_sandbox(tmp_path)
    version = "9.9.9"
    write_workspace_pins(sandbox, version=version)
    _, correct_line = write_mold_release(sandbox, version)
    (sandbox.workspace / "tools/mold/SHA256SUMS").write_text(
        f"{correct_line}\n", encoding="utf-8"
    )
    write_rustup_stub(sandbox)

    result = run_script(
        TEMPLATE_SCRIPTS / "install-build-tools.sh", installer_env(sandbox, version)
    )

    assert result.returncode == 0, result.stderr
    assert "verified" in result.stderr, result.stderr
    installed_mold = sandbox.base / "prefix" / "bin" / "mold"
    assert installed_mold.is_file() and os.access(installed_mold, os.X_OK), (
        "expected the verified archive to install an executable mold"
    )
    calls = rustup_calls(sandbox)
    assert calls == [
        (
            "<unset>",
            (
                f"toolchain install {CHANNEL} --profile minimal --component "
                f"rustfmt,clippy,{CRANELIFT}"
            ),
        )
    ], f"expected one minimally provisioned toolchain install; calls={calls}"


def test_installer_can_add_only_the_cranelift_component(tmp_path: Path) -> None:
    """The Cranelift-only route adds one component to the pinned toolchain."""
    sandbox = make_sandbox(tmp_path)
    write_workspace_pins(sandbox)
    write_rustup_stub(sandbox)

    result = run_script(
        TEMPLATE_SCRIPTS / "install-build-tools.sh",
        installer_env(sandbox),
        "--cranelift-only",
    )

    assert result.returncode == 0, result.stderr
    assert rustup_calls(sandbox) == [
        ("<unset>", f"component add {CRANELIFT} --toolchain {CHANNEL}")
    ], rustup_calls(sandbox)


@requires_linux
def test_rendered_checker_resolves_its_own_pins(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """The rendered checker reads the rendered pins without overrides."""
    project = render_project(
        tmp_path,
        copier,
        project_name="RenderedCheckerExample",
        package_name="rendered_checker_example",
    )
    toolchain = tomllib.loads((project / "rust-toolchain.toml").read_text("utf-8"))
    channel = toolchain["toolchain"]["channel"]
    components = tuple(toolchain["toolchain"]["components"])
    mold_version = (project / "tools/mold/VERSION").read_text("utf-8").strip()

    sandbox = make_sandbox(tmp_path)
    write_rustup_stub(sandbox)
    write_version_stub(sandbox, "mold", f"mold {mold_version}")
    write_version_stub(sandbox, "clang", "clang version 19.1.0")
    env = generated_project_env(
        {
            "PATH": f"{sandbox.bin}:{sandbox.core}",
            "HOME": str(sandbox.home),
            "RUSTUP_LOG": str(sandbox.base / "rustup.log"),
            "FAKE_TOOLCHAINS": f"{channel}-x86_64-unknown-linux-gnu (default)",
            "FAKE_COMPONENTS": installed_component_lines(components),
        }
    )

    result = run_script(project / "scripts" / "check-build-tools.sh", env)

    assert result.returncode == 0, result.stderr
    assert f"mold {mold_version}" in result.stderr, result.stderr
    assert f"toolchain {channel} available" in result.stderr, result.stderr
