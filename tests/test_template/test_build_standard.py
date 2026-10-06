"""Exercise rendered build routes and verified installer boundaries."""

from __future__ import annotations

import hashlib
import os
import shlex
import subprocess
import tarfile
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture, CopierProject

from tests.helpers.generated_files import parse_toml_file, parse_yaml_mapping
from tests.helpers.rendering import APP, LIB, render_project
from tests.helpers.subprocess_env import generated_project_env


def executable(path: Path, body: str) -> Path:
    """Write a controlled executable for command-boundary tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/bash\nset -euo pipefail\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def run_make(
    project: CopierProject, *arguments: str, overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a public command with controlled environment overrides."""
    return subprocess.run(
        [
            "make",
            *arguments,
            *(
                f"{key}={value}"
                for key, value in (overrides or {}).items()
                if key.startswith("BUILD_HOST_")
            ),
        ],
        cwd=project.path,
        env=generated_project_env(overrides or {}),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@pytest.mark.parametrize("flavour", [APP, LIB])
@pytest.mark.parametrize("polonius", [False, True])
@pytest.mark.parametrize(
    "dev_target", ["x86_64-unknown-linux-gnu", "", "aarch64-apple-darwin"]
)
def test_development_and_production_command_environments(
    tmp_path: Path, copier: CopierFixture, flavour: str, polonius: bool, dev_target: str
) -> None:
    """Development keeps caller flags; production and Whitaker choose their routes."""
    project = render_project(
        tmp_path,
        copier,
        project_name="Routes",
        package_name="routes",
        flavour=flavour,
        enable_polonius=polonius,
        dev_target=dev_target,
    )
    config = parse_toml_file(project / ".cargo/config.toml")
    assert "-Zthreads=8" in config["build"]["rustflags"]
    native = dev_target == "x86_64-unknown-linux-gnu"
    assert bool(config.get("target")) is native
    if native:
        assert (
            config["target"][dev_target]["linker"] == "scripts/native-clang-linker.sh"
        )
    log = tmp_path / "commands"
    cargo = executable(
        tmp_path / "cargo",
        f"""
if [ "$*" = 'nextest --version' ]; then exit 1; fi
printf '%s|%s|%s|%s|%s|%s\\n' "$*" "${{RUSTFLAGS-unset}}" \\
  "${{CARGO_PROFILE_DEV_CODEGEN_BACKEND-unset}}" \\
  "${{CARGO_ENCODED_RUSTFLAGS-unset}}" "${{DYLINT_RUSTFLAGS-unset}}" \\
  "${{CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS-unset}}" >> {shlex.quote(str(log))}
""",
    )
    base = {
        "CARGO": str(cargo),
        "WHITAKER": str(cargo),
        "CHECK_BUILD_TOOLS": "/bin/true",
        "RUSTFLAGS": "--cfg inherited",
        "BUILD_HOST_OS": "Linux",
        "BUILD_HOST_ARCH": "x86_64",
        "BUILD_HOST_TRIPLE": "x86_64-unknown-linux-gnu",
    }
    for target in ("build", "typecheck", "test", "lint-clippy"):
        log.unlink(missing_ok=True)
        result = run_make(project, target, overrides=base)
        assert result.returncode == 0, result.stderr
        for line in log.read_text().splitlines():
            flags = line.split("|")[1]
            assert "--cfg inherited" in flags
            assert "-D warnings" in flags and "-Zthreads=8" in flags
            assert ("-Zpolonius=next" in flags) is polonius
            assert ("-fuse-ld=mold" in flags) is native
    for target in ("coverage", "release", "package"):
        log.unlink(missing_ok=True)
        result = run_make(project, target, overrides=base)
        assert result.returncode == 0, result.stderr
        flags, backend = log.read_text().split("|")[1:3]
        assert (
            "inherited" not in flags
            and "-Zthreads" not in flags
            and "mold" not in flags
        )
        assert "-D warnings" in flags and backend == "llvm"
        assert ("-Zpolonius=next" in flags) is polonius
    log.unlink()
    hostile = {
        **base,
        "CARGO_ENCODED_RUSTFLAGS": "hostile",
        "CARGO_PROFILE_DEV_CODEGEN_BACKEND": "llvm",
        "CARGO_BUILD_TARGET": "aarch64-unknown-linux-gnu",
        "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS": "-C link-arg=-fuse-ld=lld",
    }
    result = run_make(project, "lint-whitaker", overrides=hostile)
    assert result.returncode == 0, result.stderr
    fields = log.read_text().strip().split("|")
    assert fields[1:4] == ["unset", "unset", "unset"]
    assert "-D warnings" in fields[4]
    assert ("-Zpolonius=next" in fields[4]) is polonius
    assert fields[5] == "unset"


@pytest.mark.parametrize("failed_gate", [None, "lint"])
def test_parallel_all_orders_gates_and_stops_on_failure(
    tmp_path: Path, copier: CopierFixture, failed_gate: str | None
) -> None:
    """Parallel Make cannot overlap the comprehensive public gates."""
    project = render_project(
        tmp_path, copier, project_name="Gates", package_name="gates"
    )
    log = tmp_path / "gates.log"
    gate = executable(
        tmp_path / "gate",
        f"""
printf '%s\\n' "$1" >> {shlex.quote(str(log))}
[ "$1" != {shlex.quote(failed_gate or "none")} ]
""",
    )
    fixture = project / "gate-fixture.mk"
    fixture.write_text(
        ".PHONY: check-fmt lint test spelling\n"
        + "".join(
            f"{name}:\n\t@{shlex.quote(str(gate))} {name}\n"
            for name in ("check-fmt", "lint", "test", "spelling")
        ),
        encoding="utf-8",
    )
    runner = executable(tmp_path / "make-gate", 'exec make -f gate-fixture.mk "$@"\n')
    result = run_make(project, "-j8", "all", f"MAKE={runner}")
    assert (result.returncode != 0) is (failed_gate is not None), result.stderr
    assert log.read_text().splitlines() == (
        ["check-fmt", "lint"]
        if failed_gate
        else ["check-fmt", "lint", "test", "spelling"]
    )


@pytest.fixture
def build_probe(
    tmp_path: Path, copier: CopierFixture
) -> tuple[CopierProject, dict[str, str]]:
    """Supply a complete toolchain and Clang link plan without network or Rust."""
    project = render_project(
        tmp_path, copier, project_name="Preflight", package_name="preflight"
    )
    tools = tmp_path / "bin"
    prefix = tmp_path / "prefix"
    executable(prefix / "bin/ld.mold", "echo 'mold 2.41.0 (compatible with GNU ld)'\n")
    executable(
        tools / "rustup",
        """
case "$*" in
  show) echo 'Default host: x86_64-unknown-linux-gnu';;
  'toolchain list') echo 'nightly-2026-08-27-x86_64-unknown-linux-gnu';;
  'component list --toolchain nightly-2026-08-27 --installed')
    printf '%s-x86_64-unknown-linux-gnu\\n' clippy llvm-tools rustc-codegen-cranelift rust-analyzer rustfmt;;
  'toolchain install '*) :;;
  *) exit 1;;
esac
""",
    )
    executable(
        tools / "clang",
        """
case "$*" in
  *-print-prog-name=ld.mold*) echo "$BUILD_TOOLS_PREFIX/bin/ld.mold";;
  *-###*) echo " \\"$BUILD_TOOLS_PREFIX/bin/ld.mold\\" " >&2;;
  *) printf '%s\\n' "$*" > "$CLANG_RECORD";;
esac
""",
    )
    executable(tools / "ld.lld", "exit 0\n")
    return project, {
        "PATH": f"{tools}:{os.environ['PATH']}",
        "BUILD_TOOLS_PREFIX": str(prefix),
    }


@pytest.mark.parametrize(
    ("variable", "value", "diagnostic"),
    [
        ("CARGO_ENCODED_RUSTFLAGS", "", "CARGO_ENCODED_RUSTFLAGS"),
        ("CARGO_BUILD_TARGET", "aarch64-unknown-linux-gnu", "CARGO_BUILD_TARGET"),
        ("CARGO_PROFILE_DEV_CODEGEN_BACKEND", "llvm", "Cranelift"),
        (
            "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER",
            "clang",
            "Clang linker wrapper",
        ),
    ],
)
def test_preflight_rejects_routes_that_bypass_the_build_standard(
    build_probe: tuple[CopierProject, dict[str, str]],
    variable: str,
    value: str,
    diagnostic: str,
) -> None:
    """The real preflight reports each unsupported environment override."""
    project, environment = build_probe
    ready = run_make(project, "check-build-tools", overrides=environment)
    assert ready.returncode == 0, ready.stderr
    failed = run_make(
        project, "check-build-tools", overrides={**environment, variable: value}
    )
    assert failed.returncode != 0 and diagnostic in failed.stderr, failed.stderr


@pytest.mark.parametrize("target", ["check-build-tools", "check-coverage-tools"])
@pytest.mark.parametrize("variable", ["CARGO_FLAGS", "TEST_FLAGS", "BUILD_JOBS"])
@pytest.mark.parametrize(
    "value", ["--target x86_64-unknown-linux-gnu", "--target=aarch64-unknown-linux-gnu"]
)
def test_preflight_rejects_explicit_targets(
    build_probe: tuple[CopierProject, dict[str, str]],
    target: str,
    variable: str,
    value: str,
) -> None:
    """Every Make option boundary rejects cross-target routing before Cargo."""
    project, environment = build_probe
    result = run_make(project, target, f"{variable}={value}", overrides=environment)
    assert result.returncode != 0 and "--target is outside" in result.stderr


@pytest.mark.parametrize("valid_digest", [False, True])
def test_installer_verifies_archive_before_unpacking(
    tmp_path: Path,
    build_probe: tuple[CopierProject, dict[str, str]],
    valid_digest: bool,
) -> None:
    """The installer accepts a recorded checksum and refuses a tampered one."""
    project, environment = build_probe
    payload = tmp_path / "payload/mold-2.41.0-x86_64-linux/bin/mold"
    executable(payload, "echo 'mold 2.41.0'\n")
    archive = tmp_path / "mold-2.41.0-x86_64-linux.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(payload.parent.parent, arcname=payload.parent.parent.name)
    digest = (
        hashlib.sha256(archive.read_bytes()).hexdigest() if valid_digest else "0" * 64
    )
    checksums = tmp_path / "SHA256SUMS"
    checksums.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    download = executable(
        tmp_path / "curl",
        f"""
while [ "$#" -gt 0 ]; do
  if [ "$1" = --output ]; then cp {shlex.quote(str(archive))} "$2"; exit; fi
  shift
done
exit 1
""",
    )
    destination = tmp_path / "installed"
    result = run_make(
        project,
        "install-build-tools",
        overrides={
            **environment,
            "PATH": f"{download.parent}:{environment['PATH']}",
            "MOLD_SHA256SUMS_FILE": str(checksums),
            "BUILD_TOOLS_PREFIX": str(destination),
        },
    )
    assert (result.returncode == 0) is valid_digest, result.stderr
    assert (destination / "bin/mold").exists() is valid_digest
    assert ("checksum mismatch" in result.stderr) is not valid_digest


def test_native_wrapper_checks_the_selected_linker(
    tmp_path: Path, build_probe: tuple[CopierProject, dict[str, str]]
) -> None:
    """Bare Cargo's wrapper checks mold and supplies Clang's search prefix."""
    project, environment = build_probe
    record = tmp_path / "clang-record"
    command = [
        str(project / "scripts/native-clang-linker.sh"),
        "-fuse-ld=mold",
        "input.o",
    ]
    controlled = generated_project_env({**environment, "CLANG_RECORD": str(record)})
    result = subprocess.run(
        command, env=controlled, capture_output=True, text=True, check=False, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert (
        record.read_text().strip()
        == f"-B {environment['BUILD_TOOLS_PREFIX']}/bin -fuse-ld=mold input.o"
    )
    (Path(environment["BUILD_TOOLS_PREFIX"]) / "bin/ld.mold").unlink()
    record.unlink()
    failed = subprocess.run(
        command, env=controlled, capture_output=True, text=True, check=False, timeout=30
    )
    assert failed.returncode != 0 and "missing or not executable" in failed.stderr
    assert not record.exists()


def test_hosted_and_act_workflows_keep_distinct_test_routes(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Hosted coverage, nested Act tests, installers, and grouping stay coherent."""
    project = render_project(
        tmp_path, copier, project_name="Workflow", package_name="workflow"
    )
    ci = parse_yaml_mapping((project / ".github/workflows/ci.yml").read_text(), "CI")
    steps = ci["jobs"]["build-test"]["steps"]
    named = {step["name"]: step for step in steps if "name" in step}
    assert named["Setup Rust"]["with"]["rustflags"] == ""
    assert named["Test and Measure Coverage"]["if"] == "env.ACT != 'true'"
    assert (
        named["Test and Measure Coverage"]["env"]["CARGO_PROFILE_DEV_CODEGEN_BACKEND"]
        == "llvm"
    )
    assert named["Test under Act"] == {
        "name": "Test under Act",
        "if": "env.ACT == 'true'",
        "env": {"WITH_ACT": "0"},
        "run": "make test",
    }
    names = list(named)
    assert names.index("Install the build standard") < names.index("Lint")
    assert names.index("Install mdtablefix") < names.index("Format")
    act = parse_yaml_mapping(
        (project / ".github/workflows/act-validation.yml").read_text(), "Act"
    )
    assert set(act["on"]) == {"workflow_dispatch"}
    dependabot = parse_yaml_mapping(
        (project / ".github/dependabot.yml").read_text(), "Dependabot"
    )
    for ecosystem in dependabot["updates"]:
        assert ecosystem["schedule"]["interval"] == "daily"
        assert ecosystem["groups"]["minor-and-patch"]["update-types"] == [
            "minor",
            "patch",
        ]


@pytest.mark.parametrize("value", ["", "2.41.0\n2.42.0\n", "2.41 0\n"])
def test_build_preflight_rejects_malformed_pins(
    tmp_path: Path, build_probe: tuple[CopierProject, dict[str, str]], value: str
) -> None:
    """Malformed pin files must not silently select a different release."""
    project, environment = build_probe
    pin = tmp_path / "VERSION"
    pin.write_text(value, encoding="utf-8")
    result = run_make(
        project,
        "check-build-tools",
        overrides={
            **environment,
            "MOLD_VERSION_FILE": str(pin),
        },
    )
    assert result.returncode != 0 and "version pin" in result.stderr


@pytest.mark.parametrize(
    "fault", ["wrong-version", "diverted-linker", "missing-component"]
)
def test_build_preflight_checks_tools_instead_of_trusting_their_presence(
    build_probe: tuple[CopierProject, dict[str, str]], fault: str
) -> None:
    """Version drift, linker diversion, and incomplete toolchains fail preflight."""
    project, environment = build_probe
    prefix = Path(environment["BUILD_TOOLS_PREFIX"])
    tools = Path(environment["PATH"].split(":")[0])
    if fault == "wrong-version":
        executable(prefix / "bin/ld.mold", "echo 'mold 2.40.0'\n")
        diagnostic = "does not match the pin"
    elif fault == "diverted-linker":
        executable(tools / "clang", "echo /usr/bin/ld.mold\n")
        diagnostic = "not pinned"
    else:
        rustup = tools / "rustup"
        rustup.write_text(
            rustup.read_text().replace(" rust-analyzer ", " "), encoding="utf-8"
        )
        diagnostic = "missing rust-analyzer"
    result = run_make(project, "check-build-tools", overrides=environment)
    assert result.returncode != 0 and diagnostic in result.stderr, result.stderr


@pytest.mark.parametrize("nextest_available", [False, True])
def test_test_gate_selects_runner_and_always_runs_doctests(
    tmp_path: Path, copier: CopierFixture, nextest_available: bool
) -> None:
    """Runner selection preserves the separate all-feature doctest gate."""
    project = render_project(
        tmp_path, copier, project_name="Runner", package_name="runner"
    )
    log = tmp_path / "runner.log"
    cargo = executable(
        tmp_path / "cargo",
        f"""
if [ "$*" = 'nextest --version' ]; then
    {'echo "cargo-nextest 0.9.100"; exit 0' if nextest_available else "exit 1"}
fi
printf '%s\\n' "$*" >> {shlex.quote(str(log))}
""",
    )
    result = run_make(project, "test", f"CARGO={cargo}", "CHECK_BUILD_TOOLS=/bin/true")
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [
        ("nextest run" if nextest_available else "test")
        + " --all-targets --all-features",
        "test --doc --workspace --all-features",
    ]


def test_parallel_lint_orders_documentation_clippy_and_whitaker(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """The aggregate lint recipe completes each Cargo operation in order."""
    project = render_project(tmp_path, copier, project_name="Lint", package_name="lint")
    log = tmp_path / "lint.log"
    cargo = executable(
        tmp_path / "cargo",
        f"""
if [ "$*" = 'nextest --version' ]; then exit 1; fi
printf '%s\\n' "$*" >> {shlex.quote(str(log))}
""",
    )
    result = run_make(
        project,
        "-j8",
        "lint",
        f"CARGO={cargo}",
        f"WHITAKER={cargo}",
        "CHECK_BUILD_TOOLS=/bin/true",
    )
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [
        "doc --no-deps",
        "clippy --all-targets --all-features -- -D warnings",
        "--all -- --all-targets --all-features",
    ]
