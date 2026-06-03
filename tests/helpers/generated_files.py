"""Parse generated project files for template contract tests."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml


def read_generated_text(path: Path) -> str:
    """Read a generated file with assertion-focused error context.

    Parameters
    ----------
    path : Path
        Path to the generated text file.

    Returns
    -------
    str
        UTF-8 decoded file contents.

    Raises
    ------
    pytest.fail.Exception
        Raised when the generated file cannot be read.
    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        pytest.fail(f"could not read generated file {path}: {error}")


def parse_toml_file(path: Path) -> dict[str, Any]:
    """Parse generated TOML with assertion-focused error context.

    Parameters
    ----------
    path : Path
        Path to the generated TOML file.

    Returns
    -------
    dict[str, Any]
        Parsed TOML mapping.

    Raises
    ------
    pytest.fail.Exception
        Raised when the generated file cannot be read or parsed as TOML.
    """
    text = read_generated_text(path)
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        pytest.fail(f"could not parse generated TOML {path}: {error}")
    return parsed


def parse_yaml_mapping(text: str, label: str) -> dict[str, Any]:
    """Parse generated YAML as a mapping with clear failure context.

    Parameters
    ----------
    text : str
        YAML document text to parse.
    label : str
        Human-readable label included in failure messages.

    Returns
    -------
    dict[str, Any]
        Parsed YAML mapping.

    Raises
    ------
    pytest.fail.Exception
        Raised when the YAML cannot be parsed or does not parse to a mapping.
    """
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as error:
        pytest.fail(f"could not parse generated {label}: {error}")
    if not isinstance(parsed, dict):
        pytest.fail(f"expected generated {label} to parse as a mapping")
    return parsed


def require_mapping(mapping: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    """Return a nested mapping or fail with the missing schema path.

    Parameters
    ----------
    mapping : dict[str, Any]
        Mapping to inspect.
    key : str
        Key expected to contain a nested mapping.
    label : str
        Human-readable schema path included in failure messages.

    Returns
    -------
    dict[str, Any]
        Nested mapping stored at ``key``.

    Raises
    ------
    pytest.fail.Exception
        Raised when ``key`` is absent or does not contain a mapping.
    """
    value = mapping.get(key)
    if not isinstance(value, dict):
        pytest.fail(f"expected {label} to include mapping key {key!r}")
    return value


def require_optional_mapping(
    mapping: dict[str, Any], key: str, label: str
) -> dict[str, Any]:
    """Return an optional nested mapping or an empty mapping.

    Parameters
    ----------
    mapping : dict[str, Any]
        Mapping to inspect.
    key : str
        Optional key that may contain a nested mapping.
    label : str
        Human-readable schema path included in failure messages.

    Returns
    -------
    dict[str, Any]
        Nested mapping stored at ``key`` when present, otherwise an empty
        mapping.

    Raises
    ------
    pytest.fail.Exception
        Raised when ``key`` is present but does not contain a mapping.
    """
    value = mapping.get(key, {})
    if not isinstance(value, dict):
        pytest.fail(f"expected {label} key {key!r} to be a mapping when present")
    return value


def require_sequence(mapping: dict[str, Any], key: str, label: str) -> list[Any]:
    """Return a nested sequence or fail with the missing schema path.

    Parameters
    ----------
    mapping : dict[str, Any]
        Mapping to inspect.
    key : str
        Key expected to contain a list.
    label : str
        Human-readable schema path included in failure messages.

    Returns
    -------
    list[Any]
        List stored at ``key``.

    Raises
    ------
    pytest.fail.Exception
        Raised when ``key`` is absent or does not contain a list.
    """
    value = mapping.get(key)
    if not isinstance(value, list):
        pytest.fail(f"expected {label} to include sequence key {key!r}")
    return value
