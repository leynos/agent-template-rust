"""Rendered release publication guard tests."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from pytest_copier.plugin import CopierFixture

from tests.helpers.delivery_workflows import render_delivery_project
from tests.helpers.generated_files import (
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
)
from tests.helpers.rendering import APP


def _github_expression_to_python(expression: str) -> str:
    """Translate the subset of GitHub expression syntax the guard uses."""
    converted = expression.replace("&&", " and ").replace("||", " or ")
    converted = re.sub(r"(?<![=!<>])!(?!=)", " not ", converted)
    converted = re.sub(r"\btrue\b", "True", converted)
    converted = re.sub(r"\bfalse\b", "False", converted)
    converted = re.sub(r"\bnull\b", "None", converted)
    converted = re.sub(r"\bstartsWith\(", "starts_with(", converted)
    return converted


def _evaluate_bool_op(node: ast.BoolOp, context: dict[str, Any]) -> bool:
    """Evaluate a translated boolean operation."""
    values = [_evaluate_expression(value, context) for value in node.values]
    return all(values) if isinstance(node.op, ast.And) else any(values)


def _evaluate_compare(node: ast.Compare, context: dict[str, Any]) -> bool:
    """Evaluate a translated comparison."""
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


def _evaluate_call(node: ast.Call, context: dict[str, Any]) -> Any:
    """Evaluate a whitelisted translated function call."""
    if isinstance(node.func, ast.Name) and node.func.id == "starts_with":
        value = _evaluate_expression(node.args[0], context)
        prefix = _evaluate_expression(node.args[1], context)
        return str(value).startswith(str(prefix))
    raise ValueError(f"unsupported call: {node.func!r}")


def _evaluate_expression(node: ast.AST, context: dict[str, Any]) -> Any:
    """Evaluate the whitelisted nodes of a translated guard expression."""
    match node:
        case ast.Expression():
            return _evaluate_expression(node.body, context)
        case ast.BoolOp():
            return _evaluate_bool_op(node, context)
        case ast.Compare():
            return _evaluate_compare(node, context)
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
            return _evaluate_call(node, context)
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
    project = render_delivery_project(
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
    assert weakened != guard, (
        "expected the guard to contain the tag check removed by the mutation"
    )
    assert _evaluate_publication_guard(
        weakened,
        event_name="workflow_dispatch",
        ref="refs/heads/main",
        dry_run=False,
    ), "expected the weakened guard to show why the tag check is required"
