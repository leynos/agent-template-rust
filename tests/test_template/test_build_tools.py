"""Tests for the pinned build-tool installer and capability checker.

The generated project ships three shell scripts and two mold pins. These tests
run the scripts against fake toolchains and fake mold releases so that checks,
installations and checksum failures are observable without touching the
machine, then render a project to prove stable Cargo accepts the generated
configuration and that every Make route composes the intended rustflags.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path

import pytest
import tomllib
from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import render_project
from tests.helpers.subprocess_env import generated_project_env

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_SCRIPTS = REPO_ROOT / "template" / "scripts"
TEMPLATE_MOLD = REPO_ROOT / "template" / "tools" / "mold"
CHANNEL = "nightly-2026-11-06"
CRANELIFT = "rustc-codegen-cranelift-preview"

# The scripts call these programs to read pins and unpack archives. A sandbox
# PATH keeps them while hiding every other tool, so an absent mold, clang or
# rustup really is absent.
_CORE_TOOLS = (
    "bash",
    "cat",
    "curl",
    "dirname",
    "grep",
    "gzip",
    "mkdir",
    "mktemp",
    "rm",
    "sha256sum",
    "tar",
    "uname",
    "awk",
)


@dataclass(frozen=True)
class Sandbox:
    """Directories and environment shared by a script invocation."""

    base: Path
    bin: Path
    core: Path
    home: Path
    workspace: Path


def _write_executable(path: Path, body: str) -> Path:
    """Write *body* to *path*, make it executable, and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _make_sandbox(tmp_path: Path) -> Sandbox:
    """Create a PATH-limited sandbox with an empty tool bin directory."""
    base = tmp_path / "sandbox"
    bin_dir = base / "bin"
    core = base / "core"
    home = base / "home"
    workspace = base / "workspace"
    for directory in (bin_dir, core, home, workspace):
        directory.mkdir(parents=True)
    for name in _CORE_TOOLS:
        resolved = shutil.which(name)
        if resolved is not None:
            (core / name).symlink_to(resolved)
    return Sandbox(base=base, bin=bin_dir, core=core, home=home, workspace=workspace)


def _write_workspace_pins(
    sandbox: Sandbox,
    *,
    version: str = "9.9.9",
    sums: str | None = None,
    components: tuple[str, ...] = ("rustfmt", "clippy", CRANELIFT),
) -> None:
    """Write the pin files the scripts read when no override is set."""
    tools = sandbox.workspace / "tools" / "mold"
    tools.mkdir(parents=True)
    (tools / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    if sums is None:
        name = f"mold-{version}-{_mold_arch()}-linux.tar.gz"
        sums = f"{'0' * 64}  {name}\n"
    (tools / "SHA256SUMS").write_text(sums, encoding="utf-8")
    rendered_components = ", ".join(f'"{component}"' for component in components)
    (sandbox.workspace / "rust-toolchain.toml").write_text(
        f'[toolchain]\nchannel = "{CHANNEL}"\ncomponents = [{rendered_components}]\n',
        encoding="utf-8",
    )


def _write_rustup_stub(sandbox: Sandbox) -> Path:
    """Write a rustup stub that records calls and answers list queries."""
    body = (
        "#!/bin/sh\n"
        'printf \'%s|%s\\n\' "${RUSTUP_AUTO_INSTALL-<unset>}" "$*" >> "$RUSTUP_LOG"\n'
        'case "${1-} ${2-}" in\n'
        '  "toolchain list") printf \'%s\\n\' "${FAKE_TOOLCHAINS-}" ;;\n'
        '  "component list") printf \'%s\\n\' "${FAKE_COMPONENTS-}" ;;\n'
        "esac\n"
        "exit 0\n"
    )
    return _write_executable(sandbox.bin / "rustup", body)


def _write_version_stub(sandbox: Sandbox, name: str, output: str) -> Path:
    """Write a stub that prints *output*, ignoring its arguments."""
    body = f"#!/bin/sh\nprintf '%s\\n' {json.dumps(output)}\n"
    return _write_executable(sandbox.bin / name, body)


def _script_env(
    sandbox: Sandbox, overrides: dict[str, str] | None = None
) -> dict[str, str]:
    """Return a PATH-limited environment for a build-tool script."""
    env = generated_project_env(
        {
            "PATH": f"{sandbox.bin}:{sandbox.core}",
            "HOME": str(sandbox.home),
            "RUSTUP_LOG": str(sandbox.base / "rustup.log"),
            "MOLD_VERSION_FILE": str(sandbox.workspace / "tools/mold/VERSION"),
            "MOLD_SHA256SUMS_FILE": str(sandbox.workspace / "tools/mold/SHA256SUMS"),
            "RUST_TOOLCHAIN_FILE": str(sandbox.workspace / "rust-toolchain.toml"),
        }
    )
    if overrides:
        env.update(overrides)
    return env


def _run_script(
    script: Path, env: dict[str, str], *arguments: str
) -> subprocess.CompletedProcess[str]:
    """Run *script* under Bash with *env* and *arguments*."""
    bash = shutil.which("bash")
    assert bash is not None, "expected bash to run the build-tool scripts"
    return subprocess.run(
        [bash, str(script), *arguments],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _rustup_calls(sandbox: Sandbox) -> list[tuple[str, str]]:
    """Return the recorded rustup calls as (auto-install, arguments) pairs."""
    log = sandbox.base / "rustup.log"
    if not log.exists():
        return []
    calls = []
    for line in log.read_text("utf-8").splitlines():
        auto_install, arguments = line.split("|", 1)
        calls.append((auto_install, arguments))
    return calls


def _installed_component_lines(sandbox: Sandbox, components: tuple[str, ...]) -> str:
    """Return rustup-style component listing lines for *components*."""
    return "\n".join(
        f"{component}-x86_64-unknown-linux-gnu" for component in components
    )


def test_checker_reports_a_missing_toolchain_without_installing(
    tmp_path: Path,
) -> None:
    """A missing pinned toolchain fails the check and never installs it."""
    sandbox = _make_sandbox(tmp_path)
    _write_workspace_pins(sandbox)
    _write_rustup_stub(sandbox)
    _write_version_stub(sandbox, "mold", "mold 9.9.9")
    _write_version_stub(sandbox, "clang", "clang version 19.1.0")

    result = _run_script(
        TEMPLATE_SCRIPTS / "check-build-tools.sh",
        _script_env(sandbox, {"FAKE_TOOLCHAINS": ""}),
    )

    assert result.returncode != 0, result.stderr
    assert "is not installed" in result.stderr, result.stderr
    assert _rustup_calls(sandbox) == [("0", "toolchain list")], (
        "expected the check to consult rustup once with auto-install disabled; "
        f"calls={_rustup_calls(sandbox)}"
    )


def test_checker_reports_a_missing_component(tmp_path: Path) -> None:
    """A toolchain missing a pinned component fails and names the component."""
    sandbox = _make_sandbox(tmp_path)
    _write_workspace_pins(sandbox)
    _write_rustup_stub(sandbox)
    _write_version_stub(sandbox, "mold", "mold 9.9.9")
    _write_version_stub(sandbox, "clang", "clang version 19.1.0")

    result = _run_script(
        TEMPLATE_SCRIPTS / "check-build-tools.sh",
        _script_env(
            sandbox,
            {
                "FAKE_TOOLCHAINS": f"{CHANNEL}-x86_64-unknown-linux-gnu (default)",
                "FAKE_COMPONENTS": _installed_component_lines(
                    sandbox, ("rustfmt", "rustc-codegen-cranelift")
                ),
            },
        ),
    )

    assert result.returncode != 0, result.stderr
    assert "component clippy is not installed" in result.stderr, result.stderr
    assert all(
        "component add" not in arguments for _, arguments in _rustup_calls(sandbox)
    ), "expected the check to report the gap rather than install the component"


def test_coverage_check_ignores_cranelift_but_requires_lld(tmp_path: Path) -> None:
    """Coverage preflight skips Cranelift and still requires the lld linker."""
    sandbox = _make_sandbox(tmp_path)
    _write_workspace_pins(sandbox, components=("rustfmt", "clippy", CRANELIFT))
    _write_rustup_stub(sandbox)
    _write_version_stub(sandbox, "clang", "clang version 19.1.0")
    lld = _write_version_stub(sandbox, "ld.lld", "LLD 19.1.0")
    env = _script_env(
        sandbox,
        {
            "FAKE_TOOLCHAINS": f"{CHANNEL}-x86_64-unknown-linux-gnu (default)",
            "FAKE_COMPONENTS": _installed_component_lines(
                sandbox, ("rustfmt", "clippy")
            ),
        },
    )

    passing = _run_script(
        TEMPLATE_SCRIPTS / "check-build-tools.sh", env, "--coverage-only"
    )
    assert passing.returncode == 0, passing.stderr
    assert CRANELIFT not in passing.stderr, (
        "expected coverage preflight to skip the Cranelift component"
    )

    lld.unlink()
    failing = _run_script(
        TEMPLATE_SCRIPTS / "check-build-tools.sh", env, "--coverage-only"
    )
    assert failing.returncode != 0, failing.stderr
    assert "lld" in failing.stderr, failing.stderr


def test_toolchain_only_check_skips_linkers(tmp_path: Path) -> None:
    """Toolchain-only preflight succeeds with no mold, clang or lld on PATH."""
    sandbox = _make_sandbox(tmp_path)
    _write_workspace_pins(sandbox)
    _write_rustup_stub(sandbox)

    result = _run_script(
        TEMPLATE_SCRIPTS / "check-build-tools.sh",
        _script_env(
            sandbox,
            {
                "FAKE_TOOLCHAINS": f"{CHANNEL}-x86_64-unknown-linux-gnu (default)",
                "FAKE_COMPONENTS": _installed_component_lines(
                    sandbox, ("rustfmt", "clippy", CRANELIFT)
                ),
            },
        ),
        "--toolchain-only",
    )

    assert result.returncode == 0, result.stderr
    assert "mold" not in result.stderr, result.stderr


def _mold_arch() -> str:
    """Return the release architecture name for the running machine."""
    return "aarch64" if platform.machine() in {"aarch64", "arm64"} else "x86_64"


def _write_mold_release(sandbox: Sandbox, version: str) -> tuple[str, str]:
    """Write a fake mold archive and return its name and correct checksum line."""
    arch = _mold_arch()
    name = f"mold-{version}-{arch}-linux.tar.gz"
    directory = sandbox.workspace / "releases" / f"v{version}"
    directory.mkdir(parents=True)
    archive = directory / name
    payload = b"#!/bin/sh\nprintf 'mold 9.9.9\\n'\n"
    info = tarfile.TarInfo(f"mold-{version}-{arch}-linux/bin/mold")
    info.size = len(payload)
    info.mode = 0o755
    with tarfile.open(archive, "w:gz") as tar:
        tar.addfile(info, io.BytesIO(payload))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return name, f"{digest}  {name}"


def _installer_env(sandbox: Sandbox, version: str = "9.9.9") -> dict[str, str]:
    """Return an environment that points the installer at the fake release."""
    return _script_env(
        sandbox,
        {
            "BUILD_TOOLS_PREFIX": str(sandbox.base / "prefix"),
            "MOLD_RELEASE_BASE_URL": (sandbox.workspace / "releases").as_uri(),
            "MOLD_VERSION_FILE": str(sandbox.workspace / "tools/mold/VERSION"),
            "MOLD_SHA256SUMS_FILE": str(sandbox.workspace / "tools/mold/SHA256SUMS"),
            "RUST_TOOLCHAIN_FILE": str(sandbox.workspace / "rust-toolchain.toml"),
        },
    )


def test_installer_refuses_a_corrupted_mold_archive(tmp_path: Path) -> None:
    """A checksum mismatch fails before extraction or toolchain installation."""
    sandbox = _make_sandbox(tmp_path)
    version = "9.9.9"
    name, _ = _write_mold_release(sandbox, version)
    _write_workspace_pins(sandbox, version=version, sums=f"{'0' * 64}  {name}\n")
    _write_rustup_stub(sandbox)

    result = _run_script(
        TEMPLATE_SCRIPTS / "install-build-tools.sh", _installer_env(sandbox, version)
    )

    assert result.returncode != 0, result.stderr
    assert "checksum mismatch" in result.stderr, result.stderr
    assert not (sandbox.base / "prefix" / "bin" / "mold").exists(), (
        "expected a rejected archive to install nothing"
    )
    assert _rustup_calls(sandbox) == [], (
        "expected a checksum failure before any toolchain installation"
    )


def test_installer_verifies_a_matching_archive_before_installing(
    tmp_path: Path,
) -> None:
    """A matching checksum installs mold and then the pinned toolchain."""
    sandbox = _make_sandbox(tmp_path)
    version = "9.9.9"
    _write_workspace_pins(sandbox, version=version)
    _, correct_line = _write_mold_release(sandbox, version)
    (sandbox.workspace / "tools/mold/SHA256SUMS").write_text(
        f"{correct_line}\n", encoding="utf-8"
    )
    _write_rustup_stub(sandbox)

    result = _run_script(
        TEMPLATE_SCRIPTS / "install-build-tools.sh", _installer_env(sandbox, version)
    )

    assert result.returncode == 0, result.stderr
    assert "verified" in result.stderr, result.stderr
    installed_mold = sandbox.base / "prefix" / "bin" / "mold"
    assert installed_mold.is_file() and os.access(installed_mold, os.X_OK), (
        "expected the verified archive to install an executable mold"
    )
    calls = _rustup_calls(sandbox)
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
    sandbox = _make_sandbox(tmp_path)
    _write_workspace_pins(sandbox)
    _write_rustup_stub(sandbox)

    result = _run_script(
        TEMPLATE_SCRIPTS / "install-build-tools.sh",
        _installer_env(sandbox),
        "--cranelift-only",
    )

    assert result.returncode == 0, result.stderr
    assert _rustup_calls(sandbox) == [
        ("<unset>", f"component add {CRANELIFT} --toolchain {CHANNEL}")
    ], _rustup_calls(sandbox)


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
    return _write_executable(sandbox_bin / name, body)


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
    uname = _write_executable(bin_dir / "uname", "#!/bin/sh\necho Linux\n")
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

    sandbox = _make_sandbox(tmp_path)
    _write_rustup_stub(sandbox)
    _write_version_stub(sandbox, "mold", f"mold {mold_version}")
    _write_version_stub(sandbox, "clang", "clang version 19.1.0")
    env = generated_project_env(
        {
            "PATH": f"{sandbox.bin}:{sandbox.core}",
            "HOME": str(sandbox.home),
            "RUSTUP_LOG": str(sandbox.base / "rustup.log"),
            "FAKE_TOOLCHAINS": f"{channel}-x86_64-unknown-linux-gnu (default)",
            "FAKE_COMPONENTS": _installed_component_lines(sandbox, components),
        }
    )

    result = _run_script(project / "scripts" / "check-build-tools.sh", env)

    assert result.returncode == 0, result.stderr
    assert f"mold {mold_version}" in result.stderr, result.stderr
    assert f"toolchain {channel} available" in result.stderr, result.stderr
