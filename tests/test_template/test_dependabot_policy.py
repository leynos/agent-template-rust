"""Rendered Dependabot policy tests."""

from __future__ import annotations

from pathlib import Path

from pytest_copier.plugin import CopierFixture

from tests.helpers.delivery_workflows import render_delivery_project
from tests.helpers.generated_files import (
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
    require_sequence,
)
from tests.helpers.rendering import LIB


def test_dependabot_groups_updates_and_applies_cooldowns(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Every ecosystem groups routine updates and cools down new releases."""
    project = render_delivery_project(
        tmp_path,
        copier,
        flavour=LIB,
        project_name="DependabotPolicy",
        package_name="dependabot_policy",
    )
    parsed = parse_yaml_mapping(
        read_generated_text(project / ".github/dependabot.yml"),
        "Dependabot configuration",
    )
    updates = require_sequence(parsed, "updates", "Dependabot configuration")
    by_ecosystem = {
        str(update["package-ecosystem"]): update
        for update in updates
        if isinstance(update, dict)
    }
    assert set(by_ecosystem) == {"github-actions", "cargo", "rust-toolchain"}, (
        "expected policy for workflow actions, Cargo crates and the toolchain"
    )

    actions = by_ecosystem["github-actions"]
    actions_groups = require_mapping(actions, "groups", "github-actions updates")
    shared_actions = require_mapping(
        actions_groups, "shared-actions", "github-actions groups"
    )
    assert shared_actions.get("patterns") == ["leynos/shared-actions*"], (
        "expected every shared-action caller to move in one pull request"
    )
    routine_actions = require_mapping(
        actions_groups, "github-actions", "github-actions groups"
    )
    assert routine_actions.get("patterns") == ["*"], (
        "expected the routine action group to match every package"
    )
    assert routine_actions.get("update-types") == ["minor", "patch"], (
        "expected routine action updates to skip major versions"
    )
    assert (
        require_mapping(actions, "schedule", "github-actions updates").get("interval")
        == "daily"
    ), "expected daily action update checks"
    actions_cooldown = require_mapping(actions, "cooldown", "github-actions updates")
    assert actions_cooldown.get("default-days") == 7, (
        "expected a seven-day cooldown for action updates"
    )

    cargo = by_ecosystem["cargo"]
    cargo_group = require_mapping(
        require_mapping(cargo, "groups", "cargo updates"),
        "minor-and-patch",
        "cargo groups",
    )
    assert cargo_group.get("patterns") == ["*"], (
        "expected the Cargo group to match every crate"
    )
    assert cargo_group.get("update-types") == ["minor", "patch"], (
        "expected the Cargo group to skip major versions"
    )
    cargo_cooldown = require_mapping(cargo, "cooldown", "cargo updates")
    assert cargo_cooldown.get("default-days") == 7, (
        "expected a seven-day cooldown for Cargo updates"
    )
    assert cargo_cooldown.get("semver-major-days") == 14, (
        "expected a slower cadence for major Cargo updates"
    )

    toolchain = by_ecosystem["rust-toolchain"]
    assert (
        require_mapping(toolchain, "schedule", "rust-toolchain updates").get("interval")
        == "daily"
    ), "expected daily toolchain update checks"
    assert (
        require_mapping(toolchain, "cooldown", "rust-toolchain updates").get(
            "default-days"
        )
        == 7
    ), "expected a seven-day cooldown for toolchain updates"
    assert "dependencies" in require_sequence(
        toolchain, "labels", "rust-toolchain updates"
    ), "expected toolchain updates to carry the dependencies label"
