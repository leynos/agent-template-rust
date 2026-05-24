from __future__ import annotations

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
    """Render a generated Rust project with publishable metadata."""
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
    """Run the generated project's public quality gate."""
    project.run("make all")


def read_generated_file(project: CopierProject, relative_path: str) -> str:
    """Read a generated file as UTF-8."""
    return (project / relative_path).read_text(encoding="utf-8")


def test_template_renders(tmp_path: Path, copier: CopierFixture) -> None:
    """Template renders with default values and passes public gates."""
    project = render_project(
        tmp_path, copier, project_name="Example", package_name="example"
    )
    assert (project / "Cargo.toml").exists()
    assert (project / "src" / f"{LIB}.rs").exists()
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
    assert (project / "src" / "main.rs").exists()
    assert (project / ".github" / "workflows" / "release.yml").exists()
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
    assert (project / "src" / "lib.rs").exists()
    assert not (project / ".github" / "workflows" / "release.yml").exists()
    run_quality_gates(project)


def test_makefile_validates(tmp_path: Path, copier: CopierFixture) -> None:
    """Generated Makefile validates with mbake."""
    project = render_project(
        tmp_path,
        copier,
        project_name="MakefileExample",
        package_name="makefile_example",
    )
    assert (project / "Makefile").exists()
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

    assert 'description = "ToolingExample package used by template tests."' in cargo_toml
    assert 'repository = "https://github.com/example/tooling_example"' in cargo_toml
    assert 'license = "ISC"' in cargo_toml
    assert "$(CARGO) nextest run" in makefile
    assert "$(WHITAKER) --all -- $(CARGO_FLAGS)" in makefile
    assert 'codegen-backend = "cranelift"' in cargo_config
    assert "[target.x86_64-unknown-linux-gnu]" in cargo_config
    assert 'link-arg=-fuse-ld=mold' in cargo_config
    assert "rustc-codegen-cranelift-preview" in rust_toolchain
    assert "llvm-tools-preview" in rust_toolchain
    assert "Cache Whitaker installation" in ci_workflow
    assert "cargo-nextest" in ci_workflow
    assert "fuse-ld=lld" in ci_workflow
    assert "Delete this file as soon as the project has real" in test_stub

    if flavour == APP:
        assert "[package.metadata.binstall]" in cargo_toml
        release_workflow = read_generated_file(project, ".github/workflows/release.yml")
        assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in release_workflow
        assert "CROSS_REVISION: v0.2.5" in release_workflow
        assert 'key: cross-${{ env.CROSS_REVISION }}' in release_workflow
        assert "files: |" in release_workflow
    else:
        assert "[package.metadata.binstall]" not in cargo_toml
