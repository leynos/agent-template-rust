"""Validate direct helper-module error handling and edge cases."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from tests.helpers.generated_files import (
    parse_toml_file,
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
    require_optional_mapping,
    require_sequence,
)
from tests.helpers.rendering import read_generated_file
from tests.helpers.tooling_contracts import assert_ci_coverage_action_contract


def test_read_generated_text_converts_os_errors(tmp_path: Path) -> None:
    """Convert generated-file read errors into pytest failures."""
    missing_path = tmp_path / "nonexistent_generated.txt"

    with pytest.raises(pytest.fail.Exception, match="could not read generated file"):
        read_generated_text(missing_path)


def test_parse_toml_file_reports_decode_errors(tmp_path: Path) -> None:
    """Convert generated TOML decode errors into pytest failures."""
    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text("[package\nname = 'broken'\n", encoding="utf-8")

    with pytest.raises(pytest.fail.Exception, match="could not parse generated TOML"):
        parse_toml_file(cargo_toml)


def test_parse_yaml_mapping_reports_invalid_yaml() -> None:
    """Convert generated YAML parser errors into pytest failures."""
    with pytest.raises(pytest.fail.Exception, match="could not parse generated CI"):
        parse_yaml_mapping("jobs: [unterminated", "CI")


def test_parse_yaml_mapping_requires_mapping_root() -> None:
    """Reject generated YAML documents that do not parse to mappings."""
    with pytest.raises(
        pytest.fail.Exception,
        match="expected generated CI workflow to parse as a mapping",
    ):
        parse_yaml_mapping("- lint\n- test\n", "CI workflow")


def test_generated_file_schema_helpers_require_expected_shapes() -> None:
    """Fail with schema-path context for wrong nested value shapes."""
    mapping: dict[str, Any] = {
        "jobs": {"build-test": {}},
        "steps": [{"name": "Check"}],
    }

    assert require_mapping(mapping, "jobs", "CI workflow") == {"build-test": {}}, (
        "expected require_mapping(mapping, 'jobs', 'CI workflow') to return jobs"
    )
    assert require_optional_mapping(mapping, "missing", "CI workflow") == {}, (
        "expected absent optional mappings to become empty mappings"
    )
    assert require_sequence(mapping, "steps", "CI build-test job") == [
        {"name": "Check"}
    ], "expected require_sequence to return the steps list"

    with pytest.raises(
        pytest.fail.Exception,
        match="expected CI workflow to include mapping key 'jobs'",
    ):
        require_mapping({"jobs": []}, "jobs", "CI workflow")

    with pytest.raises(
        pytest.fail.Exception,
        match="expected CI workflow key 'metadata' to be a mapping when present",
    ):
        require_optional_mapping({"metadata": []}, "metadata", "CI workflow")

    with pytest.raises(
        pytest.fail.Exception,
        match="expected CI build-test job to include sequence key 'steps'",
    ):
        require_sequence({"steps": {}}, "steps", "CI build-test job")


def test_read_generated_file_uses_shared_error_contract(tmp_path: Path) -> None:
    """Read rendered files through the shared generated-file helper contract."""
    generated = tmp_path / "docs" / "users-guide.md"
    generated.parent.mkdir()
    generated.write_text("generated docs\n", encoding="utf-8")
    project = cast("Any", tmp_path)

    assert read_generated_file(project, "docs/users-guide.md") == "generated docs\n", (
        "expected read_generated_file(project, 'docs/users-guide.md') to return text"
    )
    with pytest.raises(pytest.fail.Exception, match="could not read generated file"):
        read_generated_file(project, "missing.md")


def test_ci_coverage_action_contract_validates_edges() -> None:
    """Validate CI coverage action edge cases."""
    assert_ci_coverage_action_contract(
        _ci_workflow(
            persist_credentials="false",
            coverage_inputs="          output-path: lcov.info\n          format: lcov\n",
        )
    )

    with pytest.raises(
        AssertionError,
        match="expected CI checkout steps to disable credential persistence",
    ):
        assert_ci_coverage_action_contract(
            _ci_workflow(
                persist_credentials="true",
                coverage_inputs=(
                    "          output-path: lcov.info\n          format: lcov\n"
                ),
            )
        )

    with pytest.raises(AssertionError, match="expected CI coverage output path"):
        assert_ci_coverage_action_contract(
            _ci_workflow(
                persist_credentials="false",
                coverage_inputs=(
                    "          output-path: coverage.xml\n          format: lcov\n"
                ),
            )
        )


def test_parent_makefile_test_target_contract() -> None:
    """Validate the parent repository ``test`` target command contract."""
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert ".PHONY: help test" in makefile, (
        "expected parent Makefile to mark help and test as phony targets"
    )
    assert "UV := $(shell command -v uvx 2>/dev/null)" in makefile, (
        "expected parent Makefile to resolve uvx before running tests"
    )
    assert "uvx is required to run template tests" in makefile, (
        "expected parent Makefile to fail early with a uvx installation message"
    )
    assert (
        "$(UV) --with pytest-copier --with pyyaml --with syrupy --with make-parser "
        "pytest tests/"
    ) in makefile, (
        "expected parent Makefile test target to run pytest through $(UV) with "
        "pytest-copier, pyyaml, syrupy, and make-parser"
    )


def _ci_workflow(*, persist_credentials: str, coverage_inputs: str) -> str:
    """Return a minimal generated CI workflow for coverage-contract tests."""
    return f"""\
name: CI
jobs:
  build-test:
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: {persist_credentials}
      - name: Test and Measure Coverage
        uses: leynos/shared-actions/.github/actions/generate-coverage@e4c6b0e200a057edf927c45c298e7ddf229b3934
        with:
{coverage_inputs}"""
