"""Rendered documentation semantic snapshot tests."""

from __future__ import annotations

from pathlib import Path

from pytest_copier.plugin import CopierFixture
from syrupy.assertion import SnapshotAssertion

from tests.helpers.markdown_semantics import parse_markdown_semantics
from tests.helpers.rendering import APP, render_project


def test_markdown_semantics_ignore_formatting_noise() -> None:
    """Equivalent Markdown formatting yields the same normalized mdast JSON."""
    compact = """\
# Documentation

The generated project links to [docs](docs/contents.md) and explains
the workflow in one paragraph.

| Path | Purpose |
| - | - |
| `docs/contents.md` | Index |

- [x] Keep snapshots semantic
"""
    reflowed = """\
# Documentation

The generated project links to [docs](docs/contents.md) and explains the
workflow in one paragraph.

| Path                 | Purpose |
| -------------------- | ------- |
| `docs/contents.md`   | Index   |

- [x] Keep snapshots semantic
"""

    assert parse_markdown_semantics(compact) == parse_markdown_semantics(reflowed)


def test_generated_documentation_semantic_snapshots(
    tmp_path: Path, copier: CopierFixture, snapshot: SnapshotAssertion
) -> None:
    """Generated documentation matches reviewed normalized mdast snapshots."""
    project = render_project(
        tmp_path,
        copier,
        project_name="DocumentationSnapshotExample",
        package_name="documentation_snapshot_example",
        flavour=APP,
    )

    assert {
        "docs/contents.md": parse_markdown_semantics(
            (project / "docs/contents.md").read_text(encoding="utf-8")
        ),
        "docs/repository-layout.md": parse_markdown_semantics(
            (project / "docs/repository-layout.md").read_text(encoding="utf-8")
        ),
    } == snapshot
