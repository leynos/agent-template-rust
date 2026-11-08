"""Validate the parent repository's own spelling gate rule.

The template tests cover the rendered Makefile. This module covers the parent
Makefile, which differs deliberately: it gates with ``--scope all`` so the
`*.md.jinja` payload is checked too. The rule is executed with a stub builder
so the arguments are asserted without invoking the third-party tool. It also
covers the parent ``interrogate`` rule, which runs the pinned tool over
temporary workspaces to prove that Cargo target directories are excluded and
that nothing else is.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_GATE_ARGUMENTS = ["gate", "--repository", ".", "--scope", "all"]

STUB_BUILDER = """#!/usr/bin/env python3
\"\"\"Record the arguments the parent spelling rule passes to the gate.\"\"\"

import pathlib
import sys

pathlib.Path(sys.argv[1]).write_text("\\n".join(sys.argv[2:]), encoding="utf-8")
"""


def test_parent_makefile_pins_the_shared_gate_and_drops_the_vendored_generator() -> (
    None
):
    """The parent Makefile resolves the gate from a pinned builder tag."""
    makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "TYPOS_CONFIG_BUILDER_VERSION ?= v0.1.3" in makefile, (
        "expected the parent Makefile to pin the shared spelling gate version"
    )
    assert (
        "git+https://github.com/leynos/typos-config-builder.git"
        "@$(TYPOS_CONFIG_BUILDER_VERSION)"
    ) in makefile, (
        "expected the parent Makefile to resolve the gate from the pinned ref"
    )
    assert "scripts/generate_typos_config.py" not in makefile, (
        "expected the parent Makefile to drop the retired vendored generator"
    )
    assert "TYPOS_VERSION" not in makefile, (
        "expected the parent Makefile to drop the retired local Typos pin"
    )


def test_parent_spelling_rule_gates_the_whole_repository(tmp_path: Path) -> None:
    """Executing the parent rule passes ``--repository . --scope all``."""
    if shutil.which("make") is None:
        pytest.skip("make is unavailable")
    recorded = tmp_path / "arguments.txt"
    stub = tmp_path / "stub_builder.py"
    stub.write_text(STUB_BUILDER, encoding="utf-8")
    stub.chmod(0o755)

    completed = subprocess.run(
        [
            "make",
            "spelling",
            f"TYPOS_CONFIG_BUILDER={stub} {recorded}",
        ],
        cwd=REPOSITORY_ROOT,
        env={**os.environ, "MAKEFLAGS": ""},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert completed.returncode == 0, (
        f"expected the parent spelling rule to succeed:\n{completed.stderr}"
    )
    assert recorded.exists(), (
        "expected the parent spelling rule to invoke the pinned gate command"
    )
    assert recorded.read_text(encoding="utf-8").splitlines() == (
        EXPECTED_GATE_ARGUMENTS
    ), "expected the parent gate to cover every tracked file, not only Markdown"


DOCUMENTED_MODULE = (
    '"""Documented."""\n\n\ndef documented() -> None:\n    """Do nothing."""\n'
)
UNDOCUMENTED_MODULE = "def undocumented() -> None:\n    pass\n"


def _run_interrogate(
    workdir: Path, environment_overrides: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run the parent ``interrogate`` rule over *workdir*.

    Returns
    -------
    subprocess.CompletedProcess[str]
        The finished ``make`` process with its captured output.
    """
    environment = {**os.environ, "MAKEFLAGS": ""}
    for name in ("CARGO_TARGET_DIR", "CARGO_BUILD_TARGET_DIR"):
        environment.pop(name, None)
    environment.update(environment_overrides)
    return subprocess.run(
        [
            "make",
            "-f",
            str(REPOSITORY_ROOT / "Makefile"),
            "interrogate",
            "INTERROGATE_TARGETS=.",
        ],
        cwd=workdir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def _write(root: Path, name: str, source: str) -> None:
    """Write *source* to *name* under *root*, creating parent directories."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    ("generated", "environment"),
    [
        (["target/y.py", "crate/target/debug/x.py"], {}),
        (["build/out/z.py"], {"CARGO_TARGET_DIR": "build/out"}),
        (["build/[out]/z.py"], {"CARGO_BUILD_TARGET_DIR": "build/[out]"}),
        (["my build/out/z.py"], {"CARGO_TARGET_DIR": "my build/out"}),
    ],
    ids=[
        "target-directories",
        "cargo-target-dir",
        "metacharacters-are-literal",
        "whitespace-stays-one-path",
    ],
)
def test_parent_interrogate_ignores_cargo_target_directories(
    tmp_path: Path, generated: list[str], environment: dict[str, str]
) -> None:
    """Undocumented files under a Cargo target directory do not fail the gate."""
    if shutil.which("make") is None or shutil.which("uvx") is None:
        pytest.skip("make and uvx are required")
    _write(tmp_path, "owned.py", DOCUMENTED_MODULE)
    for name in generated:
        _write(tmp_path, name, UNDOCUMENTED_MODULE)

    completed = _run_interrogate(tmp_path, environment)

    assert completed.returncode == 0, (
        f"expected build output to be excluded:\n{completed.stdout}{completed.stderr}"
    )


@pytest.mark.parametrize(
    ("owned", "environment"),
    [
        ("owned.py", {}),
        ("target_utils.py", {}),
        ("tests/targets/helper.py", {}),
        ("build/o/owned.py", {"CARGO_TARGET_DIR": "build/[out]"}),
        ("build/out_helper.py", {"CARGO_TARGET_DIR": "build/out"}),
        ("my/owned.py", {"CARGO_TARGET_DIR": "my build"}),
    ],
    ids=[
        "plain-file",
        "target-prefix-file",
        "target-prefix-directory",
        "character-class-not-expanded",
        "target-dir-prefix-file",
        "whitespace-stays-one-path",
    ],
)
def test_parent_interrogate_still_fails_on_an_undocumented_owned_file(
    tmp_path: Path, owned: str, environment: dict[str, str]
) -> None:
    """Excluding target directories does not hide or loosen anything else."""
    if shutil.which("make") is None or shutil.which("uvx") is None:
        pytest.skip("make and uvx are required")
    _write(tmp_path, "target/y.py", UNDOCUMENTED_MODULE)
    _write(tmp_path, owned, UNDOCUMENTED_MODULE)

    completed = _run_interrogate(tmp_path, environment)

    assert completed.returncode != 0, (
        f"expected an undocumented owned file to fail:\n{completed.stdout}"
    )
    assert Path(owned).name in completed.stdout, (
        f"expected the report to name {owned}:\n{completed.stdout}"
    )
    assert "y.py" not in completed.stdout, (
        f"expected build output to stay excluded:\n{completed.stdout}"
    )


@pytest.mark.parametrize("tracked", ["target/owned.py", "crate/target/owned.py"])
def test_parent_interrogate_fails_loudly_on_tracked_python_under_target(
    tmp_path: Path, tracked: str
) -> None:
    """Tracked Python the exclusion would skip fails the gate rather than hide."""
    if shutil.which("make") is None or shutil.which("git") is None:
        pytest.skip("make and git are required")
    _write(tmp_path, "owned.py", DOCUMENTED_MODULE)
    _write(tmp_path, tracked, DOCUMENTED_MODULE)
    for command in (["init", "-q"], ["add", "-A"]):
        subprocess.run(["git", *command], cwd=tmp_path, check=True, timeout=60)

    completed = _run_interrogate(tmp_path, {"GIT_DIR": str(tmp_path / ".git")})

    assert completed.returncode != 0, "expected tracked Python under target/ to fail"
    assert tracked in completed.stderr, completed.stderr
