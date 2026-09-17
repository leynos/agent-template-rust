"""Validate the parent repository's own spelling gate rule.

The template tests cover the rendered Makefile. This module covers the parent
Makefile, which differs deliberately: it gates with ``--scope all`` so the
`*.md.jinja` payload is checked too. The rule is executed with a stub builder
so the arguments are asserted without invoking the third-party tool.
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

    assert "TYPOS_CONFIG_BUILDER_VERSION ?= v0.1.1" in makefile, (
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
