"""Parse generated project files for template contract tests."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml


def read_generated_text(path: Path) -> str:
    """Read a generated file with assertion-focused error context."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        pytest.fail(f"could not read generated file {path}: {error}")


def parse_toml_file(path: Path) -> dict[str, Any]:
    """Parse generated TOML with assertion-focused error context."""
    text = read_generated_text(path)
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        pytest.fail(f"could not parse generated TOML {path}: {error}")
    return parsed


def parse_yaml_mapping(text: str, label: str) -> dict[str, Any]:
    """Parse generated YAML as a mapping with clear failure context."""
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as error:
        pytest.fail(f"could not parse generated {label}: {error}")
    if not isinstance(parsed, dict):
        pytest.fail(f"expected generated {label} to parse as a mapping")
    return parsed


def require_mapping(mapping: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    """Return a nested mapping or fail with the missing schema path."""
    value = mapping.get(key)
    if not isinstance(value, dict):
        pytest.fail(f"expected {label} to include mapping key {key!r}")
    return value


def require_optional_mapping(
    mapping: dict[str, Any], key: str, label: str
) -> dict[str, Any]:
    """Return an optional nested mapping or an empty mapping."""
    value = mapping.get(key, {})
    if not isinstance(value, dict):
        pytest.fail(f"expected {label} key {key!r} to be a mapping when present")
    return value


def require_sequence(mapping: dict[str, Any], key: str, label: str) -> list[Any]:
    """Return a nested sequence or fail with the missing schema path."""
    value = mapping.get(key)
    if not isinstance(value, list):
        pytest.fail(f"expected {label} to include sequence key {key!r}")
    return value
