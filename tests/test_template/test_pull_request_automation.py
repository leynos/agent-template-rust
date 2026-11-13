"""Verify the rendered pull-request automation callers.

The generated project ships thin callers for shared pull-request automation:
``dependabot-automerge.yml`` delegates to the pinned reusable workflow and
``delayed-pr-comment.yml`` posts through a pinned action. These tests render
application and library projects with ``render_delivery_project`` and parse
each caller with the ``delivery_workflows`` helpers, asserting full-SHA pins,
the permissions each caller grants, and the trigger types it accepts. Callers
must hand the shared workflow metadata only, never a broader token scope.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.delivery_workflows import (
    COMMENT_ACTION_USES_RE,
    SHARED_AUTOMERGE_USES_RE,
    named_step,
    render_delivery_project,
    steps,
    workflow_triggers,
)
from tests.helpers.generated_files import (
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
)
from tests.helpers.rendering import APP, LIB


@pytest.mark.parametrize("flavour", [LIB, APP])
def test_pull_request_automation_callers_are_pinned_and_scoped(
    tmp_path: Path, copier: CopierFixture, flavour: str
) -> None:
    """The automerge caller delegates only metadata to a pinned workflow."""
    project = render_delivery_project(
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
    assert "github.event_name == 'workflow_dispatch'" in condition, (
        "expected the automerge caller to accept a manual dispatch"
    )
    assert "github.actor == 'dependabot[bot]'" in condition, (
        "expected the automerge caller to act for a Dependabot push"
    )
    # GitHub only cancels a superseded run for a pusher without write access, so
    # selecting on the pushing actor alone would leave a maintainer's push to a
    # Dependabot pull request unaudited. Selecting on the pull request's author
    # reaches the reusable workflow's commit audit on every such push.
    assert (
        "(github.event_name == 'pull_request_target' && "
        "github.event.pull_request.user.login == 'dependabot[bot]')" in condition
    ), (
        "expected the automerge caller to run for any push to a "
        f"Dependabot-authored pull request, got {condition!r}"
    )
    inputs = require_mapping(automerge_job, "with", "automerge job")
    assert inputs.get("pull-request-number") == (
        "${{ inputs.pull-request-number || github.event.pull_request.number }}"
    ), "expected the dispatch input to fall back to the event's pull request"

    dispatch_job = require_mapping(
        require_mapping(automerge_workflow, "jobs", "automerge workflow"),
        "dispatch-coverage",
        "automerge workflow jobs",
    )
    assert dispatch_job.get("needs") == "automerge", (
        "expected the coverage dispatch to follow the merge attempt"
    )
    assert require_mapping(dispatch_job, "permissions", "dispatch job") == {
        "actions": "write",
        "pull-requests": "read",
    }, "expected the dispatch job to receive only the access it needs"
    dispatch_step = named_step(
        dispatch_job,
        "Dispatch coverage for the merged trunk commit",
        "dispatch job",
    )
    dispatch_env = require_mapping(dispatch_step, "env", "dispatch step")
    assert dispatch_env.get("PULL_REQUEST_NUMBER") == (
        "${{ inputs.pull-request-number || github.event.pull_request.number }}"
    ), "expected the dispatch step to resolve the same pull request"
    # The job has no checkout, so `gh` cannot infer the repository from a local
    # Git directory, and the numeric pull-request argument does not select one.
    assert dispatch_env.get("GH_REPO") == "${{ github.repository }}", (
        "expected the checkout-free dispatch to name the repository for gh"
    )
    assert dispatch_env.get("GH_TOKEN") == "${{ secrets.GITHUB_TOKEN }}", (
        "expected the dispatch to authenticate with the workflow token"
    )
    dispatch_run = str(dispatch_step.get("run", ""))
    assert "gh pr view" in dispatch_run and "mergedAt" in dispatch_run, (
        "expected the dispatch step to confirm the pull request really merged"
    )
    assert 'if [ "$base" = "main" ]' in dispatch_run, (
        "expected the dispatch step to require a merge into main"
    )
    assert "gh workflow run coverage-main.yml --ref main" in dispatch_run, (
        "expected the dispatch to start coverage for main"
    )

    delayed_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/delayed-pr-comment.yml"),
        "delayed comment workflow",
    )
    triggers = workflow_triggers(delayed_workflow, "delayed comment workflow")
    dispatch = require_mapping(triggers, "workflow_dispatch", "delayed triggers")
    dispatch_inputs = require_mapping(dispatch, "inputs", "delayed triggers")
    for input_name in ("pr_number", "delay_minutes", "message"):
        declared = require_mapping(
            dispatch_inputs, input_name, "delayed workflow inputs"
        )
        assert declared.get("required") is True, (
            f"expected the {input_name} dispatch input to be required"
        )
    delayed_job = require_mapping(
        require_mapping(delayed_workflow, "jobs", "delayed comment workflow"),
        "delay-and-comment",
        "delayed workflow jobs",
    )
    assert require_mapping(delayed_job, "permissions", "delayed job") == {
        "pull-requests": "write"
    }, "expected the comment job to receive only pull-request write access"
    comment_step = named_step(
        delayed_job, "Comment on pull request", "delayed workflow job"
    )
    assert COMMENT_ACTION_USES_RE.fullmatch(str(comment_step.get("uses", ""))), (
        "expected the comment action pinned to a full 40-hex commit SHA"
    )
    for step in steps(delayed_job, "delayed workflow job"):
        assert "inputs.message" not in str(step.get("run", "")), (
            "expected the comment body to stay out of shell commands"
        )
