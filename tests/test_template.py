from __future__ import annotations

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

from datetime import datetime, UTC
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture, CopierProject

APP = "app"
LIB = "lib"

TEMPLATE_PATH = Path(__file__).parents[1]


def render_project(
    tmp_path: Path,
    copier: CopierFixture,
    *,
    project_name: str,
    package_name: str,
    flavour: str = LIB,
) -> CopierProject:
    """Render a generated Rust project with publishable metadata.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory used as the generated project destination.
    copier : CopierFixture
        pytest-copier fixture bound to this template repository.
    project_name : str
        Human-readable project name supplied to the Copier template.
    package_name : str
        Rust package name supplied to the Copier template.
    flavour : str, default=LIB
        Generated project flavour to render.

    Returns
    -------
    CopierProject
        Rendered project wrapper for file assertions and command execution.
    """
    return copier.copy(
        tmp_path,
        project_name=project_name,
        package_name=package_name,
        package_description=f"{project_name} package used by template tests.",
        repository_url=f"https://github.com/example/{package_name}",
        homepage_url=f"https://example.com/{package_name}",
        package_keywords="rust,template",
        package_categories="development-tools",
        license_year=datetime.now(tz=UTC).year,
        license_holder=f"{project_name} Dev",
        license_email=f"{package_name}@example.com",
        flavour=flavour,
    )


def run_quality_gates(project: CopierProject) -> None:
    """Run the generated project's public quality gate.

    Parameters
    ----------
    project : CopierProject
        Rendered generated project whose public gate should be executed.

    Returns
    -------
    None
        The function returns nothing and raises if the quality gate fails.
    """
    project.run("make all")


def read_generated_file(project: CopierProject, relative_path: str) -> str:
    """Read a generated file as UTF-8 text.

    Parameters
    ----------
    project : CopierProject
        Rendered generated project that contains the file.
    relative_path : str
        Path to read relative to the generated project root.

    Returns
    -------
    str
        UTF-8 decoded contents of the generated file.
    """
    return (project / relative_path).read_text(encoding="utf-8")


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
    run_quality_gates(project)


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
    run_quality_gates(project)


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
    run_quality_gates(project)


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


@pytest.mark.parametrize("flavour", [LIB, APP])
def test_generated_tooling_contracts(
    tmp_path: Path, copier: CopierFixture, flavour: str
) -> None:
    """Generated projects include the requested Rust tooling contracts."""
    project = render_project(
        tmp_path,
        copier,
        project_name="ToolingExample",
        package_name="tooling_example",
        flavour=flavour,
    )

    cargo_toml = read_generated_file(project, "Cargo.toml")
    makefile = read_generated_file(project, "Makefile")
    cargo_config = read_generated_file(project, ".cargo/config.toml")
    ci_workflow = read_generated_file(project, ".github/workflows/ci.yml")
    rust_toolchain = read_generated_file(project, "rust-toolchain.toml")
    test_stub = read_generated_file(project, "tests/stub.rs")

    assert 'description = "ToolingExample package used by template tests."' in cargo_toml, (
        "expected generated Cargo.toml to include package description"
    )
    assert 'repository = "https://github.com/example/tooling_example"' in cargo_toml, (
        "expected generated Cargo.toml to include repository URL"
    )
    assert 'license = "ISC"' in cargo_toml, (
        "expected generated Cargo.toml to include ISC licence"
    )
    assert "$(CARGO) nextest run" in makefile, (
        "expected generated Makefile to run tests with cargo-nextest"
    )
    assert "$(WHITAKER) --all -- $(CARGO_FLAGS)" in makefile, (
        "expected generated Makefile lint target to run Whitaker"
    )
    assert 'codegen-backend = "cranelift"' in cargo_config, (
        "expected generated cargo config to enable Cranelift"
    )
    assert "[target.x86_64-unknown-linux-gnu]" in cargo_config, (
        "expected generated cargo config to include Linux target settings"
    )
    assert 'link-arg=-fuse-ld=mold' in cargo_config, (
        "expected generated cargo config to use mold linker"
    )
    assert "rustc-codegen-cranelift-preview" in rust_toolchain, (
        "expected generated rust-toolchain to include Cranelift component"
    )
    assert "llvm-tools-preview" in rust_toolchain, (
        "expected generated rust-toolchain to include llvm tools component"
    )
    assert "Cache Whitaker installation" in ci_workflow, (
        "expected generated CI workflow to cache Whitaker installation"
    )
    assert (
        "leynos/shared-actions/.github/actions/setup-rust"
        "@e4c6b0e200a057edf927c45c298e7ddf229b3934" in ci_workflow
    ), "expected generated CI workflow to use the pinned shared setup-rust action"
    assert "cargo-nextest" in ci_workflow, (
        "expected generated CI workflow to install cargo-nextest"
    )
    assert "fuse-ld=lld" in ci_workflow, (
        "expected generated CI workflow coverage to use lld linker flags"
    )
    assert "Delete this file as soon as the project has real" in test_stub, (
        "expected generated test stub to explain when to delete it"
    )

    if flavour == APP:
        assert "[package.metadata.binstall]" in cargo_toml, (
            "expected app flavour Cargo.toml to include binstall metadata"
        )
        release_workflow = read_generated_file(project, ".github/workflows/release.yml")
        assert (
            "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
            in release_workflow
        ), "expected app release workflow to use pinned upload-artifact action"
        assert "CROSS_REVISION: v0.2.5" in release_workflow, (
            "expected app release workflow to pin cross revision"
        )
        assert 'key: cross-${{ env.CROSS_REVISION }}' in release_workflow, (
            "expected app release workflow to cache cross by revision"
        )
        assert "files: |" in release_workflow, (
            "expected app release workflow to upload release files"
        )
    else:
        assert "[package.metadata.binstall]" not in cargo_toml, (
            "expected lib flavour Cargo.toml to omit binstall metadata"
        )
