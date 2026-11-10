"""Sandbox fixtures for the generated build-tool scripts.

The generated project ships shell scripts that read pins, consult rustup and
unpack a pinned ``mold`` archive. These helpers build a PATH-limited sandbox
with fake toolchains and fake releases so the build-tool tests can observe
checks, installations and checksum failures without touching the machine.
"""

from __future__ import annotations

import hashlib
import io
import json
import platform
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path

from tests.helpers.subprocess_env import generated_project_env

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_SCRIPTS = REPO_ROOT / "template" / "scripts"
TEMPLATE_MOLD = REPO_ROOT / "template" / "tools" / "mold"
CHANNEL = "nightly-2026-11-06"
CRANELIFT = "rustc-codegen-cranelift-preview"

# The scripts call these programs to read pins and unpack archives. A sandbox
# PATH keeps them while hiding every other tool, so an absent mold, clang or
# rustup really is absent.
CORE_TOOLS = (
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


def write_executable(path: Path, body: str) -> Path:
    """Write *body* to *path*, make it executable, and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def make_sandbox(tmp_path: Path) -> Sandbox:
    """Create a PATH-limited sandbox with an empty tool bin directory."""
    base = tmp_path / "sandbox"
    bin_dir = base / "bin"
    core = base / "core"
    home = base / "home"
    workspace = base / "workspace"
    for directory in (bin_dir, core, home, workspace):
        directory.mkdir(parents=True)
    for name in CORE_TOOLS:
        resolved = shutil.which(name)
        if resolved is not None:
            (core / name).symlink_to(resolved)
    return Sandbox(base=base, bin=bin_dir, core=core, home=home, workspace=workspace)


def mold_arch() -> str:
    """Return the release architecture name for the running machine."""
    return "aarch64" if platform.machine() in {"aarch64", "arm64"} else "x86_64"


def write_workspace_pins(
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
        name = f"mold-{version}-{mold_arch()}-linux.tar.gz"
        sums = f"{'0' * 64}  {name}\n"
    (tools / "SHA256SUMS").write_text(sums, encoding="utf-8")
    rendered_components = ", ".join(f'"{component}"' for component in components)
    (sandbox.workspace / "rust-toolchain.toml").write_text(
        f'[toolchain]\nchannel = "{CHANNEL}"\ncomponents = [{rendered_components}]\n',
        encoding="utf-8",
    )


def write_mold_release(sandbox: Sandbox, version: str) -> tuple[str, str]:
    """Write a fake mold archive and return its name and correct checksum line."""
    arch = mold_arch()
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


def write_rustup_stub(sandbox: Sandbox) -> Path:
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
    return write_executable(sandbox.bin / "rustup", body)


def write_version_stub(sandbox: Sandbox, name: str, output: str) -> Path:
    """Write a stub that prints *output*, ignoring its arguments."""
    body = f"#!/bin/sh\nprintf '%s\\n' {json.dumps(output)}\n"
    return write_executable(sandbox.bin / name, body)


def installed_component_lines(components: tuple[str, ...]) -> str:
    """Return rustup-style component listing lines for *components*."""
    return "\n".join(
        f"{component}-x86_64-unknown-linux-gnu" for component in components
    )


def script_env(
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


def installer_env(sandbox: Sandbox, version: str = "9.9.9") -> dict[str, str]:
    """Return an environment that points the installer at the fake release."""
    return script_env(
        sandbox,
        {
            "BUILD_TOOLS_PREFIX": str(sandbox.base / "prefix"),
            "MOLD_RELEASE_BASE_URL": (sandbox.workspace / "releases").as_uri(),
            "MOLD_VERSION_FILE": str(sandbox.workspace / "tools/mold/VERSION"),
            "MOLD_SHA256SUMS_FILE": str(sandbox.workspace / "tools/mold/SHA256SUMS"),
            "RUST_TOOLCHAIN_FILE": str(sandbox.workspace / "rust-toolchain.toml"),
        },
    )


def run_script(
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


def rustup_calls(sandbox: Sandbox) -> list[tuple[str, str]]:
    """Return the recorded rustup calls as (auto-install, arguments) pairs."""
    log = sandbox.base / "rustup.log"
    if not log.exists():
        return []
    calls = []
    for line in log.read_text("utf-8").splitlines():
        auto_install, arguments = line.split("|", 1)
        calls.append((auto_install, arguments))
    return calls
