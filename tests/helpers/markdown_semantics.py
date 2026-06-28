"""Normalize Markdown documents as mdast JSON for semantic assertions."""

from __future__ import annotations

import re
from typing import Any

import mdast

_POSITION_KEYS = frozenset({"position", "line", "column", "offset"})
_SOFT_WHITESPACE = re.compile(r"[ \t\r\n]+")


def parse_markdown_semantics(markdown: str) -> object:
    """Parse Markdown into normalized mdast JSON."""
    tree = mdast.md_to_ast(markdown, config=_gfm_parse_options())
    return _normalise_node(tree)


def _gfm_parse_options() -> mdast.ParseOptions:
    return mdast.ParseOptions(
        gfm_autolink_literal=True,
        gfm_footnote_definition=True,
        gfm_label_start_footnote=True,
        gfm_strikethrough=True,
        gfm_table=True,
        gfm_task_list_item=True,
    )


def _normalise_node(value: Any) -> object:
    if isinstance(value, dict):
        normalised = {}
        node_type = value.get("type")
        for key, child in value.items():
            if key in _POSITION_KEYS:
                continue
            if key == "value" and node_type == "text" and isinstance(child, str):
                normalised[key] = _normalise_soft_text(child)
                continue
            normalised[key] = _normalise_node(child)
        return normalised

    if isinstance(value, list):
        return [_normalise_node(child) for child in value]

    return value


def _normalise_soft_text(value: str) -> str:
    return _SOFT_WHITESPACE.sub(" ", value)
