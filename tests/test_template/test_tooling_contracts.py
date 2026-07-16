"""Rendered tooling contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import (
    parse_toml_file,
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
    require_optional_mapping,
)
from tests.helpers.rendering import APP, LIB, render_project
from tests.helpers.tooling_contracts import (
    assert_coverage_main_workflow_contract,
    assert_generated_tooling_contracts,
)


@pytest.mark.parametrize(
    ("flavour", "dev_target"),
    [
        (LIB, "x86_64-unknown-linux-gnu"),
        (APP, "x86_64-unknown-linux-gnu"),
        (LIB, "aarch64-apple-darwin"),
    ],
)
def test_generated_tooling_contracts(
    tmp_path: Path, copier: CopierFixture, flavour: str, dev_target: str
) -> None:
    """Generated projects include the requested Rust tooling contracts."""
    project = render_project(
        tmp_path,
        copier,
        project_name="ToolingExample",
        package_name="tooling_example",
        flavour=flavour,
        dev_target=dev_target,
    )

    project.run("make all")
    project.run("mbake validate Makefile")
    project.run("cargo metadata --format-version=1 --no-deps")

    cargo = parse_toml_file(project / "Cargo.toml")
    package = require_mapping(cargo, "package", "Cargo.toml")
    metadata = require_optional_mapping(package, "metadata", "Cargo.toml package")
    makefile = read_generated_text(project / "Makefile")
    cargo_config = read_generated_text(project / ".cargo/config.toml")
    ci_workflow = read_generated_text(project / ".github/workflows/ci.yml")
    act_workflow = read_generated_text(project / ".github/workflows/act-validation.yml")
    coverage_main_workflow = read_generated_text(
        project / ".github/workflows/coverage-main.yml"
    )
    mutation_workflow = read_generated_text(
        project / ".github/workflows/mutation-testing.yml"
    )
    docs_contents = read_generated_text(project / "docs/contents.md")
    repository_layout = read_generated_text(project / "docs/repository-layout.md")
    readme = read_generated_text(project / "README.md")
    rust_toolchain = read_generated_text(project / "rust-toolchain.toml")
    test_stub = read_generated_text(project / "tests/stub.rs")
    typos_config = read_generated_text(project / "typos.toml")
    typos_overlay = read_generated_text(project / "typos.local.toml")
    spelling_generator = read_generated_text(
        project / "scripts/generate_typos_config.py"
    )
    spelling_core = read_generated_text(project / "scripts/typos_rollout.py")
    parsed_ci_workflow = parse_yaml_mapping(ci_workflow, "CI workflow")

    release_workflow = (
        read_generated_text(project / ".github/workflows/release.yml")
        if flavour == APP
        else None
    )
    assert_generated_tooling_contracts(
        package=package,
        metadata=metadata,
        flavour=flavour,
        makefile=makefile,
        cargo_config=cargo_config,
        dev_target=dev_target,
        rust_toolchain=rust_toolchain,
        parsed_ci_workflow=parsed_ci_workflow,
        ci_workflow=ci_workflow,
        act_workflow=act_workflow,
        mutation_workflow=mutation_workflow,
        docs_contents=docs_contents,
        repository_layout=repository_layout,
        readme=readme,
        test_stub=test_stub,
        release_workflow=release_workflow,
    )
    assert_coverage_main_workflow_contract(coverage_main_workflow)
    assert '[default]\nlocale = "en-gb"' in typos_config
    assert 'accepted = ["Flavored", "mold"]' in typos_overlay
    assert "DEFAULT_BASE_URL" in spelling_generator
    assert "_local_cache_is_current" in spelling_core
