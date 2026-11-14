"""Shared helpers for rendered delivery workflow tests.

The delivery tests render a generated project, parse its workflow files and
inspect one job's steps. These helpers keep that parsing in one place so each
test module names only the invariant it checks.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pytest_copier.plugin import CopierFixture, CopierProject

from tests.helpers.generated_files import require_sequence
from tests.helpers.rendering import render_project

SHARED_AUTOMERGE_USES_RE = re.compile(
    r"^leynos/shared-actions/\.github/workflows/dependabot-automerge\.yml"
    r"@[0-9a-f]{40}$"
)
COMMENT_ACTION_USES_RE = re.compile(
    r"^thollander/actions-comment-pull-request@[0-9a-f]{40}$"
)
UPLOAD_ARTIFACT_USES_RE = re.compile(r"^actions/upload-artifact@[0-9a-f]{40}$")
DOWNLOAD_ARTIFACT_USES_RE = re.compile(r"^actions/download-artifact@[0-9a-f]{40}$")
SOFT_PROPS_RELEASE_USES_RE = re.compile(r"^softprops/action-gh-release@[0-9a-f]{40}$")
SETUP_RUST_USES_RE = re.compile(
    r"^leynos/shared-actions/\.github/actions/setup-rust@[0-9a-f]{40}$"
)


def render_delivery_project(
    tmp_path: Path,
    copier: CopierFixture,
    *,
    flavour: str,
    project_name: str,
    package_name: str,
    enable_polonius: bool | None = None,
) -> CopierProject:
    """Render a generated project for a delivery-tooling test."""
    return render_project(
        tmp_path,
        copier,
        project_name=project_name,
        package_name=package_name,
        flavour=flavour,
        enable_polonius=enable_polonius,
    )


def workflow_triggers(workflow: dict[Any, Any], label: str) -> dict[str, Any]:
    """Return a workflow's trigger mapping, quoted or unquoted ``on``."""
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict), f"expected {label} to declare triggers"
    return triggers


def steps(job: dict[str, Any], label: str) -> list[dict[str, Any]]:
    """Return the mapping-shaped steps of a parsed workflow job."""
    parsed = require_sequence(job, "steps", label)
    return [step for step in parsed if isinstance(step, dict)]


def named_step(job: dict[str, Any], name: str, label: str) -> dict[str, Any]:
    """Return the one step with ``name`` from a parsed workflow job."""
    matches = [step for step in steps(job, label) if step.get("name") == name]
    assert len(matches) == 1, f"expected one {name!r} step in {label}"
    return matches[0]
