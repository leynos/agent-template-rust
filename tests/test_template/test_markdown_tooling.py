"""Rendered Markdown formatting tests."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import render_project
from tests.helpers.subprocess_env import generated_project_env

REPO_ROOT = Path(__file__).resolve().parents[2]

# The table is deliberately malformed and its heading line is long enough to
# need wrapping, so mdtablefix must change both files it selects. A formatter
# that ran but selected nothing would leave this text untouched.
MESSY_MARKDOWN = """# Markdown example

| Name |Value|
|--|--|
| alpha|1 |

This trailing paragraph exists so that the wrapping rules have a second kind
of defect to correct inside the same file, and the line is long enough that
mdtablefix must rewrite it.
"""


def _run_make(
    project: Path, target: str, *arguments: str
) -> subprocess.CompletedProcess[str]:
    """Run a generated-project Make target and capture its output."""
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"
    return subprocess.run(
        [make, target, *arguments],
        cwd=project,
        env=generated_project_env({}),
        check=False,
        capture_output=True,
        text=True,
    )


def test_rendered_check_fmt_reformats_git_visible_markdown(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Rendered formatting selects tracked and untracked Markdown only."""
    project = render_project(
        tmp_path,
        copier,
        project_name="MarkdownExample",
        package_name="markdown_example",
    )
    tracked = project / "docs" / "tracked-example.md"
    untracked = project / "docs" / "untracked-example.md"
    ignored = project / "target" / "ignored-example.md"
    ignored.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text(MESSY_MARKDOWN, encoding="utf-8")
    untracked.write_text(MESSY_MARKDOWN, encoding="utf-8")
    ignored.write_text(MESSY_MARKDOWN, encoding="utf-8")
    subprocess.run(
        ["git", "add", "docs/tracked-example.md"],
        cwd=project.path,
        check=True,
        capture_output=True,
    )

    check = _run_make(project.path, "check-fmt")

    output = f"{check.stdout}\n{check.stderr}"
    assert check.returncode != 0, (
        "expected check-fmt to reject malformed Markdown\n"
        f"stdout:\n{check.stdout}\nstderr:\n{check.stderr}"
    )
    assert "tracked-example.md" in output, (
        f"expected check-fmt to select tracked Markdown\noutput:\n{output}"
    )
    assert "untracked-example.md" in output, (
        f"expected check-fmt to select untracked Markdown\noutput:\n{output}"
    )
    assert "ignored-example.md" not in output, (
        f"expected check-fmt to skip ignored Markdown\noutput:\n{output}"
    )

    formatted = _run_make(project.path, "fmt")

    assert formatted.returncode == 0, (
        "expected fmt to format the selected Markdown\n"
        f"stdout:\n{formatted.stdout}\nstderr:\n{formatted.stderr}"
    )
    for path in (tracked, untracked):
        text = path.read_text(encoding="utf-8")
        assert "| alpha | 1     |" in text, (
            f"expected fmt to normalize the table in {path.name}: {text!r}"
        )
        assert "|--|--|" not in text, (
            f"expected fmt to rewrite the malformed separator in {path.name}"
        )
    assert "|--|--|" in ignored.read_text(encoding="utf-8"), (
        "expected fmt to leave ignored Markdown unformatted"
    )

    after = _run_make(project.path, "check-fmt")

    assert after.returncode == 0, (
        "expected check-fmt to accept the formatted project\n"
        f"stdout:\n{after.stdout}\nstderr:\n{after.stderr}"
    )


def test_parent_act_validation_provisions_the_markdown_formatter() -> None:
    """Act validation renders projects whose formatting gate needs mdtablefix."""
    workflow = (REPO_ROOT / ".github/workflows/act-validation.yml").read_text(
        encoding="utf-8"
    )

    assert re.search(r"install-mdtablefix@[0-9a-f]{40}\b", workflow), (
        "expected act validation to install the Markdown formatter pinned to a "
        "full 40-hex commit SHA"
    )
    assert workflow.index("install-mdtablefix") < workflow.index(
        "name: Test with act validation"
    ), (
        "expected act validation to provision the formatter before rendering and "
        "testing generated projects"
    )
