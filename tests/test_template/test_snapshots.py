"""Rendered structured-file snapshot tests."""

from __future__ import annotations

import re
from pathlib import Path

from pytest_copier.plugin import CopierFixture
from syrupy.assertion import SnapshotAssertion

from tests.helpers.generated_files import (
    parse_yaml_mapping,
    read_generated_text,
)
from tests.helpers.rendering import APP, render_project

_PINNED_USES_RE = re.compile(r"^(?P<ref>.+)@[0-9a-f]{40}$")


# FIXME(https://github.com/leynos/agent-template-rust/issues/72): replace this
# hand-rolled traversal with a syrupy ``matcher=`` as part of the planned
# snapshot-testing overhaul (once AST-aware Markdown snapshots are ready).
def _redact_pinned_shas(value: object) -> object:
    """Replace 40-hex SHA-pinned ``uses`` refs with a stable placeholder."""
    match value:
        case dict() as mapping:
            return {
                key: _redact_mapping_entry(key, item) for key, item in mapping.items()
            }
        case list() as sequence:
            return [_redact_pinned_shas(item) for item in sequence]
        case _:
            return value


def _redact_mapping_entry(key: object, item: object) -> object:
    """Redact a pinned ``uses`` ref, otherwise recurse into the entry."""
    match (key, item):
        case ("uses", str() as pinned):
            return _PINNED_USES_RE.sub(r"\g<ref>@<sha>", pinned)
        case _:
            return _redact_pinned_shas(item)


def test_generated_structured_file_snapshots(
    tmp_path: Path, copier: CopierFixture, snapshot: SnapshotAssertion
) -> None:
    """Generated structured tooling files match reviewed snapshots."""
    project = render_project(
        tmp_path,
        copier,
        project_name="SnapshotExample",
        package_name="snapshot_example",
        flavour=APP,
    )

    cargo_config = read_generated_text(project / ".cargo/config.toml")
    makefile = read_generated_text(project / "Makefile")
    makefile_snapshot = makefile.replace("\t", "\\t")
    ci_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/ci.yml"), "CI workflow"
    )
    audit_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/audit.yml"), "audit workflow"
    )
    act_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/act-validation.yml"),
        "act-validation workflow",
    )
    coverage_main_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/coverage-main.yml"),
        "coverage-main workflow",
    )
    release_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/release.yml"),
        "release workflow",
    )

    assert (
        _redact_pinned_shas(
            {
                "cargo_config": cargo_config,
                "makefile": makefile_snapshot,
                "act_workflow": act_workflow,
                "audit_workflow": audit_workflow,
                "ci_workflow": ci_workflow,
                "coverage_main_workflow": coverage_main_workflow,
                "release_workflow": release_workflow,
            }
        )
        == snapshot
    ), (
        "Snapshot mismatch for template outputs (cargo_config, makefile, "
        "act_workflow, audit_workflow, ci_workflow, coverage_main_workflow, "
        "release_workflow)"
    )
