"""Render the template and hold its CodeScene publisher to the CV-005 shape.

The tooling contracts check the same shape after ``make all``; this module
renders without building, so each flavour's publisher and pull-request
workflow are proved cheaply, and a template mutation fails here in seconds.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import parse_yaml_mapping, read_generated_text
from tests.helpers.rendering import APP, LIB, render_project
from tests.helpers.tooling_contracts.codescene_publisher import (
    assert_ci_workflow_reaches_no_codescene,
    assert_codescene_publisher_contract,
    assert_lanes_share_the_ratchet,
)


@pytest.mark.parametrize("flavour", [LIB, APP])
@pytest.mark.parametrize("enable_polonius", [True, False])
def test_rendered_publisher_keeps_the_token_out_of_every_env(
    tmp_path: Path,
    copier: CopierFixture,
    flavour: str,
    enable_polonius: bool,
) -> None:
    """Each render uploads from main alone, with the token in no ``env``."""
    project = render_project(
        tmp_path,
        copier,
        project_name="PublisherExample",
        package_name="publisher_example",
        flavour=flavour,
        enable_polonius=enable_polonius,
    )
    workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/coverage-main.yml"),
        "coverage-main workflow",
    )
    ci_workflow = read_generated_text(project / ".github/workflows/ci.yml")
    assert_codescene_publisher_contract(workflow)
    assert_ci_workflow_reaches_no_codescene(ci_workflow)
    assert_lanes_share_the_ratchet(
        parse_yaml_mapping(ci_workflow, "CI workflow"), workflow
    )
