"""Rendered delivery tooling tests.

The generated project owns its dependency-update policy, its pull-request
automation callers, and its application release workflow. These tests render
the template and assert the invariants those files must keep: every action
reference is pinned to a full commit SHA, untrusted dispatch input is validated
before use, and a release is published only from a tag ref with an explicit
non-dry-run dispatch.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_copier.plugin import CopierFixture, CopierProject

from tests.helpers.generated_files import (
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
    require_sequence,
)
from tests.helpers.rendering import APP, LIB, render_project

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


def _render(
    tmp_path: Path,
    copier: CopierFixture,
    *,
    flavour: str,
    project_name: str,
    package_name: str,
) -> CopierProject:
    """Render a generated project for a delivery-tooling test."""
    return render_project(
        tmp_path,
        copier,
        project_name=project_name,
        package_name=package_name,
        flavour=flavour,
    )


def _workflow_triggers(workflow: dict[Any, Any], label: str) -> dict[str, Any]:
    """Return a workflow's trigger mapping, quoted or unquoted ``on``."""
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict), f"expected {label} to declare triggers"
    return triggers


def _steps(job: dict[str, Any], label: str) -> list[dict[str, Any]]:
    """Return the mapping-shaped steps of a parsed workflow job."""
    steps = require_sequence(job, "steps", label)
    return [step for step in steps if isinstance(step, dict)]


def _named_step(job: dict[str, Any], name: str, label: str) -> dict[str, Any]:
    """Return the one step with ``name`` from a parsed workflow job."""
    matches = [step for step in _steps(job, label) if step.get("name") == name]
    assert len(matches) == 1, f"expected one {name!r} step in {label}"
    return matches[0]


def test_dependabot_groups_updates_and_applies_cooldowns(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Every ecosystem groups routine updates and cools down new releases."""
    project = _render(
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
    assert routine_actions.get("patterns") == ["*"]
    assert routine_actions.get("update-types") == ["minor", "patch"]
    assert (
        require_mapping(actions, "schedule", "github-actions updates").get("interval")
        == "daily"
    )
    actions_cooldown = require_mapping(actions, "cooldown", "github-actions updates")
    assert actions_cooldown.get("default-days") == 7

    cargo = by_ecosystem["cargo"]
    cargo_group = require_mapping(
        require_mapping(cargo, "groups", "cargo updates"),
        "minor-and-patch",
        "cargo groups",
    )
    assert cargo_group.get("patterns") == ["*"]
    assert cargo_group.get("update-types") == ["minor", "patch"]
    cargo_cooldown = require_mapping(cargo, "cooldown", "cargo updates")
    assert cargo_cooldown.get("default-days") == 7
    assert cargo_cooldown.get("semver-major-days") == 14, (
        "expected a slower cadence for major Cargo updates"
    )

    toolchain = by_ecosystem["rust-toolchain"]
    assert (
        require_mapping(toolchain, "schedule", "rust-toolchain updates").get("interval")
        == "daily"
    )
    assert (
        require_mapping(toolchain, "cooldown", "rust-toolchain updates").get(
            "default-days"
        )
        == 7
    )
    assert "dependencies" in require_sequence(
        toolchain, "labels", "rust-toolchain updates"
    )


@pytest.mark.parametrize("flavour", [LIB, APP])
def test_pull_request_automation_callers_are_pinned_and_scoped(
    tmp_path: Path, copier: CopierFixture, flavour: str
) -> None:
    """The automerge caller delegates only metadata to a pinned workflow."""
    project = _render(
        tmp_path,
        copier,
        flavour=flavour,
        project_name="PullRequestAutomation",
        package_name="pull_request_automation",
    )
    automerge_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/dependabot-automerge.yml"),
        "automerge workflow",
    )
    automerge_job = require_mapping(
        require_mapping(automerge_workflow, "jobs", "automerge workflow"),
        "automerge",
        "automerge workflow jobs",
    )
    permissions = require_mapping(automerge_job, "permissions", "automerge job")
    assert permissions == {
        "contents": "write",
        "pull-requests": "write",
        "checks": "read",
        "statuses": "read",
        "id-token": "write",
    }, "expected only the permissions the reusable workflow needs"
    uses = str(automerge_job.get("uses", ""))
    assert SHARED_AUTOMERGE_USES_RE.fullmatch(uses), (
        f"expected a full-SHA shared automerge reference, got {uses!r}"
    )
    condition = str(automerge_job.get("if", ""))
    assert "github.event_name == 'workflow_dispatch'" in condition
    assert "github.actor == 'dependabot[bot]'" in condition
    inputs = require_mapping(automerge_job, "with", "automerge job")
    assert inputs.get("pull-request-number") == (
        "${{ inputs.pull-request-number || github.event.pull_request.number }}"
    ), "expected the dispatch input to fall back to the event's pull request"

    delayed_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/delayed-pr-comment.yml"),
        "delayed comment workflow",
    )
    triggers = _workflow_triggers(delayed_workflow, "delayed comment workflow")
    dispatch = require_mapping(triggers, "workflow_dispatch", "delayed triggers")
    dispatch_inputs = require_mapping(dispatch, "inputs", "delayed triggers")
    for input_name in ("pr_number", "delay_minutes", "message"):
        declared = require_mapping(
            dispatch_inputs, input_name, "delayed workflow inputs"
        )
        assert declared.get("required") is True
    delayed_job = require_mapping(
        require_mapping(delayed_workflow, "jobs", "delayed comment workflow"),
        "delay-and-comment",
        "delayed workflow jobs",
    )
    assert require_mapping(delayed_job, "permissions", "delayed job") == {
        "pull-requests": "write"
    }, "expected the comment job to receive only pull-request write access"
    comment_step = _named_step(
        delayed_job, "Comment on pull request", "delayed workflow job"
    )
    assert COMMENT_ACTION_USES_RE.fullmatch(str(comment_step.get("uses", ""))), (
        "expected the comment action pinned to a full 40-hex commit SHA"
    )
    for step in _steps(delayed_job, "delayed workflow job"):
        assert "inputs.message" not in str(step.get("run", "")), (
            "expected the comment body to stay out of shell commands"
        )


def _run_validation_step(
    project: CopierProject, pr_number: str, delay_minutes: str
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the rendered validation script with untrusted dispatch values."""
    parsed = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/delayed-pr-comment.yml"),
        "delayed comment workflow",
    )
    job = require_mapping(
        require_mapping(parsed, "jobs", "delayed comment workflow"),
        "delay-and-comment",
        "delayed workflow jobs",
    )
    validation_step = _named_step(job, "Validate inputs", "delayed workflow job")
    script = str(validation_step.get("run", ""))
    assert script, "expected the validation step to run a script"
    output_path = project.path / "validation-output"
    output_path.write_text("", encoding="utf-8")
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "GITHUB_OUTPUT": str(output_path),
        "PR_NUMBER": pr_number,
        "DELAY_MINUTES": delay_minutes,
    }
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=project.path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result, output_path


@pytest.mark.parametrize(
    ("pr_number", "delay_minutes", "expected_seconds"),
    [
        ("12", "5", "300"),
        ("0", "0", "0"),
        ("123456", "90", "5400"),
        ("12", "010", "600"),
    ],
)
def test_delayed_pr_comment_accepts_whole_numbers(
    tmp_path: Path,
    copier: CopierFixture,
    pr_number: str,
    delay_minutes: str,
    expected_seconds: str,
) -> None:
    """The validation step converts a whole-minute delay to seconds."""
    project = _render(
        tmp_path,
        copier,
        flavour=LIB,
        project_name="DelayedComment",
        package_name="delayed_comment",
    )
    result, output_path = _run_validation_step(project, pr_number, delay_minutes)

    assert result.returncode == 0, result.stderr
    assert f"delay-seconds={expected_seconds}" in output_path.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("pr_number", "delay_minutes"),
    [
        ("abc", "5"),
        ("12", "1.5"),
        ("-1", "5"),
        ("12", ""),
        ("12; rm -rf /", "5"),
        ("12", "$(id)"),
    ],
)
def test_delayed_pr_comment_rejects_other_input(
    tmp_path: Path,
    copier: CopierFixture,
    pr_number: str,
    delay_minutes: str,
) -> None:
    """Non-numeric and shell-shaped input is rejected before use."""
    project = _render(
        tmp_path,
        copier,
        flavour=LIB,
        project_name="InvalidDelayedComment",
        package_name="invalid_delayed_comment",
    )
    result, _output_path = _run_validation_step(project, pr_number, delay_minutes)

    assert result.returncode != 0, (
        f"expected {pr_number!r} and {delay_minutes!r} to be rejected"
    )


def test_application_release_matrix_uses_native_macos_and_cross_builders(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Each matrix leg's runner agrees with its builder and target."""
    project = _render(
        tmp_path,
        copier,
        flavour=APP,
        project_name="ReleaseMatrix",
        package_name="release_matrix",
    )
    workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/release.yml"),
        "release workflow",
    )
    build = require_mapping(
        require_mapping(workflow, "jobs", "release workflow"),
        "build",
        "release workflow jobs",
    )
    strategy = require_mapping(build, "strategy", "release build job")
    assert strategy.get("fail-fast") is False, (
        "expected one failing leg not to cancel the others"
    )
    matrix = require_mapping(strategy, "matrix", "release build strategy")
    include = require_sequence(matrix, "include", "release build matrix")
    assert include, "expected release matrix legs"
    targets = [str(entry["target"]) for entry in include]
    assert len(targets) == len(set(targets)), "expected one leg per target"
    for entry in include:
        builder = entry["builder"]
        runner = str(entry["runner"])
        target = str(entry["target"])
        if builder == "cargo":
            assert runner.startswith("macos-"), (
                f"expected native builder for {target} to use a macOS runner"
            )
        else:
            assert builder == "cross"
            assert runner == "ubuntu-latest", (
                f"expected cross builder for {target} to use a Linux runner"
            )
    runners_by_target = {entry["target"]: entry["runner"] for entry in include}
    assert runners_by_target["x86_64-apple-darwin"] == "macos-15-intel"
    assert runners_by_target["aarch64-apple-darwin"] == "macos-latest"

    steps = _steps(build, "release build job")
    setup = next(
        step
        for step in steps
        if SETUP_RUST_USES_RE.fullmatch(str(step.get("uses", "")))
    )
    setup_inputs = require_mapping(setup, "with", "release setup-rust step")
    assert setup_inputs.get("use-sccache") == "false", (
        "expected a release build not to install or save sccache"
    )
    assert setup_inputs.get("expect-cache") == "any"
    assert setup_inputs.get("toolchain") == "stable", (
        "expected the release build to use stable Cargo"
    )
    assert "rustflags" not in setup_inputs, (
        "expected no nightly development flags on the release toolchain"
    )

    native = _named_step(build, "Build release binary (native)", "release build job")
    native_command = str(native.get("run", ""))
    assert native_command.startswith("cargo +stable build --release --target ")
    native_env = require_mapping(native, "env", "native release step")
    assert native_env.get("RUSTFLAGS") == ""
    cross = _named_step(build, "Build release binary (cross)", "release build job")
    cross_command = str(cross.get("run", ""))
    assert cross_command.startswith("cross +stable build --release --target ")
    cross_env = require_mapping(cross, "env", "cross release step")
    assert cross_env.get("RUSTFLAGS") == ""
    assert cross_env.get("CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER") == "cc", (
        "expected the cross image to use gcc rather than the clang config"
    )
    add_target = _named_step(build, "Add native target", "release build job")
    assert 'rustup target add "${{ matrix.target }}"' in str(add_target.get("run"))
    prepare = _named_step(build, "Prepare artifact", "release build job")
    assert "shasum -a 256" in str(prepare.get("run")), (
        "expected a checksum beside every release artefact"
    )
    assert any(
        UPLOAD_ARTIFACT_USES_RE.fullmatch(str(step.get("uses", ""))) for step in steps
    ), "expected release artefacts to be uploaded by a pinned action"

    release = require_mapping(
        require_mapping(workflow, "jobs", "release workflow"),
        "release",
        "release workflow jobs",
    )
    assert release.get("needs") == "build"
    assert require_mapping(release, "permissions", "release job") == {
        "contents": "write"
    }
    release_steps = _steps(release, "release job")
    assert any(
        DOWNLOAD_ARTIFACT_USES_RE.fullmatch(str(step.get("uses", "")))
        for step in release_steps
    )
    assert any(
        SOFT_PROPS_RELEASE_USES_RE.fullmatch(str(step.get("uses", "")))
        for step in release_steps
    )


def _github_expression_to_python(expression: str) -> str:
    """Translate the subset of GitHub expression syntax the guard uses."""
    converted = expression.replace("&&", " and ").replace("||", " or ")
    converted = re.sub(r"(?<![=!<>])!(?!=)", " not ", converted)
    converted = re.sub(r"\btrue\b", "True", converted)
    converted = re.sub(r"\bfalse\b", "False", converted)
    converted = re.sub(r"\bnull\b", "None", converted)
    converted = re.sub(r"\bstartsWith\(", "starts_with(", converted)
    return converted


def _evaluate_expression(node: ast.AST, context: dict[str, Any]) -> Any:
    """Evaluate the whitelisted nodes of a translated guard expression."""
    match node:
        case ast.Expression():
            return _evaluate_expression(node.body, context)
        case ast.BoolOp():
            values = [_evaluate_expression(value, context) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        case ast.Compare():
            left = _evaluate_expression(node.left, context)
            for operator, comparator in zip(node.ops, node.comparators, strict=True):
                right = _evaluate_expression(comparator, context)
                if isinstance(operator, ast.Eq):
                    matched = left == right
                elif isinstance(operator, ast.NotEq):
                    matched = left != right
                else:  # pragma: no cover - the guard uses only equality
                    raise TypeError(f"unsupported comparison: {operator!r}")
                if not matched:
                    return False
                left = right
            return True
        case ast.UnaryOp() if isinstance(node.op, ast.Not):
            return not _evaluate_expression(node.operand, context)
        case ast.Constant():
            return node.value
        case ast.Name():
            return context[node.id]
        case ast.Attribute():
            return _evaluate_expression(node.value, context)[node.attr]
        case ast.Subscript():
            return _evaluate_expression(node.value, context)[
                _evaluate_expression(node.slice, context)
            ]
        case ast.Call():
            if isinstance(node.func, ast.Name) and node.func.id == "starts_with":
                value = _evaluate_expression(node.args[0], context)
                prefix = _evaluate_expression(node.args[1], context)
                return str(value).startswith(str(prefix))
            raise ValueError(f"unsupported call: {node.func!r}")
        case _:  # pragma: no cover - guards use a small expression subset
            raise ValueError(f"unsupported expression node: {node!r}")


def _evaluate_publication_guard(guard: str, **event: Any) -> bool:
    """Evaluate a release publication guard for one event row."""
    translated = ast.parse(_github_expression_to_python(guard), mode="eval")
    github = {
        "event_name": event["event_name"],
        "ref": event["ref"],
        "actor": event.get("actor", "dependabot[bot]"),
    }
    inputs = {"dry-run": event.get("dry_run")}
    return bool(_evaluate_expression(translated, {"github": github, "inputs": inputs}))


def test_release_publication_guard_event_table(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Publication needs a tag ref and an explicit non-dry-run dispatch."""
    project = _render(
        tmp_path,
        copier,
        flavour=APP,
        project_name="PublicationGuard",
        package_name="publication_guard",
    )
    workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/release.yml"),
        "release workflow",
    )
    release = require_mapping(
        require_mapping(workflow, "jobs", "release workflow"),
        "release",
        "release workflow jobs",
    )
    guard = str(release.get("if", ""))
    assert guard, "expected the release job to carry a publication guard"

    table: list[tuple[dict[str, Any], bool]] = [
        ({"event_name": "push", "ref": "refs/tags/v1.2.3"}, True),
        (
            {
                "event_name": "workflow_dispatch",
                "ref": "refs/tags/v1.2.3",
                "dry_run": False,
            },
            True,
        ),
        (
            {
                "event_name": "workflow_dispatch",
                "ref": "refs/tags/v1.2.3",
                "dry_run": True,
            },
            False,
        ),
        (
            {
                "event_name": "workflow_dispatch",
                "ref": "refs/heads/main",
                "dry_run": False,
            },
            False,
        ),
        (
            {
                "event_name": "workflow_dispatch",
                "ref": "refs/heads/main",
                "dry_run": True,
            },
            False,
        ),
    ]
    for event, expected in table:
        assert _evaluate_publication_guard(guard, **event) is expected, (
            f"expected publication for {event!r} to be {expected}"
        )

    # Non-vacuity: a guard that omits the tag check would publish from a branch
    # dispatch, so the table above distinguishes the real guard.
    weakened = guard.replace(" && startsWith(github.ref, 'refs/tags/')", "")
    assert weakened != guard
    assert _evaluate_publication_guard(
        weakened,
        event_name="workflow_dispatch",
        ref="refs/heads/main",
        dry_run=False,
    ), "expected the weakened guard to show why the tag check is required"


def test_library_render_has_no_release_workflow(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """A library has no application binary to release."""
    project = _render(
        tmp_path,
        copier,
        flavour=LIB,
        project_name="LibraryRelease",
        package_name="library_release",
    )

    assert not (project / ".github/workflows/release.yml").exists()
