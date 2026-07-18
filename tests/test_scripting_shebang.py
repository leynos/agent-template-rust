"""Validate the uv script shebang prescribed by the scripting standard.

``#!/usr/bin/env -S uv run python`` executes the interpreter directly and
ignores the PEP 723 inline-metadata block, so a directly invoked script
fails at import time on machines without its dependencies preinstalled.
The prescribed form is ``#!/usr/bin/env -S uv run --script``. These tests
guard the repository and template trees against the broken form and prove
the prescribed form resolves inline dependencies before execution.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

BROKEN_SHEBANG = "#!/usr/bin/env -S uv run python\n"
PRESCRIBED_SHEBANG = "#!/usr/bin/env -S uv run --script\n"

PROBE_SCRIPT = """\
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["packaging"]
# ///
import packaging

print(packaging.__name__)
"""


def _pep723_scripts() -> list[Path]:
    """Return every tracked Python file opening with a PEP 723 metadata block.

    A PEP 723 script declares its block at the top of the file (immediately
    after the shebang), so only the first few lines are examined; embedded
    fixture strings elsewhere in a file do not count.
    """
    scripts = []
    for path in sorted(REPO_ROOT.glob("**/*.py")):
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        head = path.read_text(encoding="utf-8").splitlines()[:3]
        if any(line.strip() == "# /// script" for line in head):
            scripts.append(path)
    return scripts


def test_no_pep723_script_ships_the_broken_shebang() -> None:
    """No repository or template script heads a PEP 723 block with the broken form."""
    scripts = _pep723_scripts()
    assert scripts, "expected at least one PEP 723 script in the repository"
    offenders = [
        path
        for path in scripts
        if path.read_text(encoding="utf-8").startswith(BROKEN_SHEBANG)
    ]
    assert not offenders, (
        "these PEP 723 scripts use `uv run python`, which ignores the inline "
        f"metadata block: {[str(p) for p in offenders]}"
    )


def test_pep723_scripts_use_the_prescribed_shebang() -> None:
    """Every PEP 723 script starts with the prescribed --script shebang."""
    offenders = [
        path
        for path in _pep723_scripts()
        if not path.read_text(encoding="utf-8").startswith(PRESCRIBED_SHEBANG)
    ]
    assert not offenders, (
        "these PEP 723 scripts do not use the prescribed "
        f"`uv run --script` shebang: {[str(p) for p in offenders]}"
    )


def test_prescribed_shebang_resolves_inline_dependencies(tmp_path: Path) -> None:
    """A directly executed script under the prescribed shebang imports its deps."""
    if shutil.which("uv") is None:
        pytest.skip("uv is not on PATH")
    script = tmp_path / "probe.py"
    script.write_text(PROBE_SCRIPT, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        [str(script)],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
        timeout=300,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "packaging"
