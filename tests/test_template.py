"""Template rendering tests for the Rust Copier project.

This module verifies that the template renders useful Rust library and
application projects, that generated public quality gates work, and that key
tooling contracts are present in the generated files. The tests expect the
pytest-copier ``copier`` fixture configured by ``tests.conftest`` and can be
run with ``make test`` from the parent template repository.

Example:
    Run ``make test`` to render the template and execute all generated-project
    contract checks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture
from syrupy.assertion import SnapshotAssertion

from tests.helpers.generated_files import (
    parse_toml_file,
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
    require_optional_mapping,
)
from tests.helpers.rendering import APP, LIB, render_project
from tests.helpers.tooling_contracts import assert_generated_tooling_contracts


def test_template_renders(tmp_path: Path, copier: CopierFixture) -> None:
    """Template renders with default values and passes public gates."""
    project = render_project(
        tmp_path, copier, project_name="Example", package_name="example"
    )
    assert (project / "Cargo.toml").exists(), (
        "expected Cargo.toml to exist in generated project"
    )
    assert (project / "src" / f"{LIB}.rs").exists(), (
        f"expected src/{LIB}.rs to exist in generated project"
    )
    project.run("make all")


def test_template_renders_app_flavour(tmp_path: Path, copier: CopierFixture) -> None:
    """Template renders app flavour correctly and passes public gates."""
    project = render_project(
        tmp_path,
        copier,
        project_name="AppExample",
        package_name="app_example",
        flavour=APP,
    )
    assert (project / "src" / "main.rs").exists(), (
        "expected src/main.rs to exist for app flavour"
    )
    assert (project / ".github" / "workflows" / "release.yml").exists(), (
        "expected release workflow to exist for app flavour"
    )
    project.run("make all")


def test_template_renders_lib_flavour(tmp_path: Path, copier: CopierFixture) -> None:
    """Template renders lib flavour correctly and passes public gates."""
    project = render_project(
        tmp_path,
        copier,
        project_name="LibExample",
        package_name="lib_example",
        flavour=LIB,
    )
    assert (project / "src" / "lib.rs").exists(), (
        "expected src/lib.rs to exist for lib flavour"
    )
    assert not (project / ".github" / "workflows" / "release.yml").exists(), (
        "expected release workflow to be omitted for lib flavour"
    )
    project.run("make all")


def test_makefile_validates(tmp_path: Path, copier: CopierFixture) -> None:
    """Generated Makefile validates with mbake."""
    project = render_project(
        tmp_path,
        copier,
        project_name="MakefileExample",
        package_name="makefile_example",
    )
    assert (project / "Makefile").exists(), (
        "expected generated project Makefile to exist"
    )
    project.run("mbake validate Makefile")


def test_clippy_runs(tmp_path: Path, copier: CopierFixture) -> None:
    """Generated project passes its full lint target."""
    project = render_project(
        tmp_path,
        copier,
        project_name="ClippyExample",
        package_name="clippy_example",
    )
    project.run("make lint")


@pytest.mark.parametrize("whitaker_location", ["path", "home", "missing"])
def test_makefile_resolves_whitaker_fallback(
    tmp_path: Path,
    copier: CopierFixture,
    whitaker_location: str,
) -> None:
    """Generated lint target resolves Whitaker from PATH or user install."""
    project = render_project(
        tmp_path,
        copier,
        project_name="WhitakerExample",
        package_name="whitaker_example",
    )
    home = tmp_path / "home"
    path_bin = tmp_path / "path-bin"
    user_bin = home / ".local" / "bin"
    cargo = tmp_path / "cargo"
    marker = tmp_path / "whitaker-ran"
    path_bin.mkdir(parents=True)
    user_bin.mkdir(parents=True)
    cargo.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    cargo.chmod(0o755)

    expected_whitaker = None
    if whitaker_location != "missing":
        expected_whitaker = (
            path_bin / "whitaker"
            if whitaker_location == "path"
            else user_bin / "whitaker"
        )
        expected_whitaker.write_text(
            f"#!/bin/sh\ntouch {marker}\nexit 0\n", encoding="utf-8"
        )
        expected_whitaker.chmod(0o755)
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"

    result = subprocess.run(
        [make, "lint"],
        cwd=project.path,
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": os.pathsep.join(
                [str(path_bin), "/usr/bin", "/bin"]
                if whitaker_location == "path"
                else ["/usr/bin", "/bin"]
            ),
            "CARGO": str(cargo),
        },
        check=False,
        capture_output=True,
        text=True,
    )

    if expected_whitaker is None:
        assert result.returncode != 0, "expected lint to fail without Whitaker"
        assert "whitaker" in result.stderr.lower(), (
            "expected missing Whitaker failure to identify the missing tool"
        )
    else:
        assert result.returncode == 0, result.stderr
        assert marker.exists(), (
            f"expected generated lint target to execute {whitaker_location} Whitaker"
        )


@pytest.mark.parametrize("flavour", [LIB, APP])
def test_template_compiles(
    tmp_path: Path, copier: CopierFixture, flavour: str
) -> None:
    """Generated project compiles with cargo check."""
    project = render_project(
        tmp_path,
        copier,
        project_name="CompileExample",
        package_name="compile_example",
        flavour=flavour,
    )
    project.run("cargo check --all-targets --all-features")


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
    ci_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/ci.yml"), "CI workflow"
    )
    release_workflow = parse_yaml_mapping(
        read_generated_text(project / ".github/workflows/release.yml"),
        "release workflow",
    )

    assert {
        "cargo_config": cargo_config,
        "makefile": makefile,
        "ci_workflow": ci_workflow,
        "release_workflow": release_workflow,
    } == snapshot, (
        "Snapshot mismatch for template outputs "
        "(cargo_config, makefile, ci_workflow, release_workflow)"
    )
