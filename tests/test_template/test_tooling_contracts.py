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
from tests.helpers.tooling_contracts import assert_generated_tooling_contracts


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
    docs_contents = read_generated_text(project / "docs/contents.md")
    repository_layout = read_generated_text(project / "docs/repository-layout.md")
    readme = read_generated_text(project / "README.md")
    rust_toolchain = read_generated_text(project / "rust-toolchain.toml")
    test_stub = read_generated_text(project / "tests/stub.rs")
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
        docs_contents=docs_contents,
        repository_layout=repository_layout,
        readme=readme,
        test_stub=test_stub,
        release_workflow=release_workflow,
    )
