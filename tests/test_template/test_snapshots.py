"""Rendered structured-file snapshot tests."""

from __future__ import annotations

from pathlib import Path

from pytest_copier.plugin import CopierFixture
from syrupy.assertion import SnapshotAssertion

from tests.helpers.generated_files import (
    parse_yaml_mapping,
    read_generated_text,
)
from tests.helpers.rendering import APP, render_project


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
    ci_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/ci.yml"), "CI workflow"
    )
    act_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/act-validation.yml"),
        "act-validation workflow",
    )
    release_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/release.yml"),
        "release workflow",
    )

    assert {
        "cargo_config": cargo_config,
        "makefile": makefile,
        "act_workflow": act_workflow,
        "ci_workflow": ci_workflow,
        "release_workflow": release_workflow,
    } == snapshot, (
        "Snapshot mismatch for template outputs "
        "(cargo_config, makefile, act_workflow, ci_workflow, release_workflow)"
    )
