"""Rendered structured-file snapshot tests."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from hypothesis import given
from hypothesis import strategies as st
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


_HEX_ALPHABET = "0123456789abcdef"
_action_paths = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789/-._", min_size=1, max_size=20
)
_full_shas = st.text(alphabet=_HEX_ALPHABET, min_size=40, max_size=40)


def _pinned_uses_ref(path: str, sha: str) -> str:
    """Build a ``uses`` ref pinned to a full 40-hex commit SHA."""
    return f"{path}@{sha}"


def _unpinned_uses_ref(path: str, ref: str) -> str:
    """Build a ``uses`` ref pointing at a mutable branch or tag."""
    return f"{path}@{ref}"


_pinned_uses = st.builds(_pinned_uses_ref, _action_paths, _full_shas)
_unpinned_uses = st.one_of(
    st.builds(
        _unpinned_uses_ref, _action_paths, st.sampled_from(("main", "v1", "rolling"))
    ),
    st.text(max_size=20),
)
_uses_refs = st.one_of(_pinned_uses, _unpinned_uses)


def _workflow_children(children: st.SearchStrategy[Any]) -> st.SearchStrategy[Any]:
    """Extend the recursive workflow strategy with lists, dicts, and uses leaves."""
    return st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(st.text(min_size=1, max_size=5), children, max_size=3),
        st.fixed_dictionaries({"uses": _uses_refs}),
    )


_workflow_like = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.text(max_size=10),
        st.fixed_dictionaries({"uses": _uses_refs}),
    ),
    _workflow_children,
    max_leaves=15,
)


def _iter_uses_values(value: object) -> Iterator[str]:
    """Yield every ``uses`` string leaf in a nested workflow structure."""
    match value:
        case dict() as mapping:
            for key, item in mapping.items():
                match (key, item):
                    case ("uses", str() as uses):
                        yield uses
                    case _:
                        yield from _iter_uses_values(item)
        case list() as sequence:
            for item in sequence:
                yield from _iter_uses_values(item)


def _same_shape(original: object, redacted: object) -> bool:
    """Return whether two structures share container types, keys, and lengths."""
    match original, redacted:
        case dict() as original_map, dict() as redacted_map:
            return original_map.keys() == redacted_map.keys() and all(
                _same_shape(original_map[key], redacted_map[key])
                for key in original_map
            )
        case dict(), _:
            return False
        case list() as original_seq, list() as redacted_seq:
            return len(original_seq) == len(redacted_seq) and all(
                _same_shape(a, b)
                for a, b in zip(original_seq, redacted_seq, strict=True)
            )
        case list(), _:
            return False
        case _:
            return type(original) is type(redacted)


@given(structure=_workflow_like)
def test_redact_pinned_shas_removes_every_pinned_sha(structure: object) -> None:
    """Redaction strips every pinned SHA, is idempotent, and preserves shape."""
    redacted = _redact_pinned_shas(structure)

    assert all(
        _PINNED_USES_RE.match(uses) is None for uses in _iter_uses_values(redacted)
    ), "expected redaction to strip every pinned SHA from uses refs"
    assert _redact_pinned_shas(redacted) == redacted, (
        "expected redaction to be idempotent"
    )
    assert _same_shape(structure, redacted), (
        "expected redaction to preserve the structure shape"
    )


@given(path=_action_paths, sha=_full_shas)
def test_redact_pinned_shas_preserves_action_path(path: str, sha: str) -> None:
    """A pinned ``uses`` ref keeps its action path and drops only the SHA."""
    assert _redact_pinned_shas({"uses": f"{path}@{sha}"}) == {
        "uses": f"{path}@<sha>"
    }, "expected redaction to replace only the SHA and keep the action path"
