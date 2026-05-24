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

import tomllib
from pathlib import Path

import pytest
import yaml
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
    license_year: int | None = 2026,
    dev_target: str = "x86_64-unknown-linux-gnu",
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
    license_year : int | None, default=2026
        Licence year supplied to the Copier template.
    dev_target : str, default="x86_64-unknown-linux-gnu"
        Development target supplied to the Copier template.

    Returns
    -------
    CopierProject
        Rendered project wrapper for file assertions and command execution.
    """
    answers: dict[str, str | int] = {
        "project_name": project_name,
        "package_name": package_name,
        "package_description": f"{project_name} package used by template tests.",
        "repository_url": f"https://github.com/example/{package_name}",
        "homepage_url": f"https://example.com/{package_name}",
        "package_keywords": "rust,template",
        "package_categories": "development-tools",
        "license_holder": f"{project_name} Dev",
        "license_email": f"{package_name}@example.com",
        "flavour": flavour,
        "dev_target": dev_target,
    }
    if license_year is not None:
        answers["license_year"] = license_year

    return copier.copy(tmp_path, **answers)


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

    cargo_toml = (project / "Cargo.toml").read_text(encoding="utf-8")
    cargo = tomllib.loads(cargo_toml)
    package = cargo["package"]
    metadata = package.get("metadata", {})
    makefile = (project / "Makefile").read_text(encoding="utf-8")
    cargo_config = (project / ".cargo/config.toml").read_text(encoding="utf-8")
    ci_workflow = (project / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    readme = (project / "README.md").read_text(encoding="utf-8")
    rust_toolchain = (project / "rust-toolchain.toml").read_text(encoding="utf-8")
    test_stub = (project / "tests/stub.rs").read_text(encoding="utf-8")
    parsed_ci_workflow = yaml.safe_load(ci_workflow)

    checkout_steps = [
        step
        for job in parsed_ci_workflow["jobs"].values()
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    ]
    assert checkout_steps, "expected generated CI workflow to check out sources"
    assert all(
        step.get("with", {}).get("persist-credentials") is False
        for step in checkout_steps
    ), "expected generated CI checkout steps to disable credential persistence"

    assert package["description"] == "ToolingExample package used by template tests.", (
        "expected generated Cargo.toml to include package description"
    )
    assert package["repository"] == "https://github.com/example/tooling_example", (
        "expected generated Cargo.toml to include repository URL"
    )
    assert package["homepage"] == "https://example.com/tooling_example", (
        "expected generated Cargo.toml to include homepage URL"
    )
    assert package["keywords"] == ["rust", "template"], (
        "expected generated Cargo.toml to include package keywords"
    )
    assert package["categories"] == ["development-tools"], (
        "expected generated Cargo.toml to include package categories"
    )
    assert package["license"] == "ISC", (
        "expected generated Cargo.toml to include ISC licence"
    )
    assert "TEST_CMD :=" in makefile, (
        "expected generated Makefile to define a test command fallback"
    )
    assert "nextest run,test" in makefile, (
        "expected generated Makefile to fall back to cargo test without cargo-nextest"
    )
    assert "$(CARGO) $(TEST_CMD)" in makefile, (
        "expected generated Makefile test target to use the selected test command"
    )
    assert "coverage: ## Generate lcov coverage with lld" in makefile, (
        "expected generated Makefile to include an lld-backed coverage target"
    )
    assert "COVERAGE_LINKER_FLAGS ?= -fuse-ld=lld" in makefile, (
        "expected generated Makefile coverage target to select lld"
    )
    assert 'CFLAGS="$(COVERAGE_LINKER_FLAGS)"' in makefile, (
        "expected generated Makefile coverage target to set CFLAGS"
    )
    assert 'LDFLAGS="$(COVERAGE_LINKER_FLAGS)"' in makefile, (
        "expected generated Makefile coverage target to set LDFLAGS"
    )
    assert "$(WHITAKER) --all -- $(CARGO_FLAGS)" in makefile, (
        "expected generated Makefile lint target to run Whitaker"
    )
    assert 'codegen-backend = "cranelift"' in cargo_config, (
        "expected generated cargo config to enable Cranelift"
    )
    if "linux" in dev_target:
        assert f"[target.{dev_target}]" in cargo_config, (
            "expected generated cargo config to include Linux target settings"
        )
        assert 'link-arg=-fuse-ld=mold' in cargo_config, (
            "expected generated cargo config to use mold linker for Linux"
        )
    else:
        assert f"[target.{dev_target}]" not in cargo_config, (
            "expected generated cargo config to avoid mold target blocks "
            "for non-Linux targets"
        )
        assert 'link-arg=-fuse-ld=mold' not in cargo_config, (
            "expected generated cargo config to avoid mold for non-Linux targets"
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
    assert "coverage uses lld for llvm-tools compatibility" in ci_workflow, (
        "expected generated CI workflow to document mold and lld roles"
    )
    assert "clang lld mold" in ci_workflow, (
        "expected generated CI workflow to install clang, lld, and mold"
    )
    assert "fuse-ld=lld" in ci_workflow, (
        "expected generated CI workflow coverage to use lld linker flags"
    )
    assert "CFLAGS: -fuse-ld=lld" in ci_workflow, (
        "expected generated CI workflow coverage to set CFLAGS for lld"
    )
    assert "LDFLAGS: -fuse-ld=lld" in ci_workflow, (
        "expected generated CI workflow coverage to set LDFLAGS for lld"
    )
    assert "Development builds use `mold` on Linux" in readme, (
        "expected generated README to document mold for development builds"
    )
    assert "Coverage generation uses `lld`" in readme, (
        "expected generated README to document lld for coverage"
    )
    assert "Delete this file as soon as the project has real" in test_stub, (
        "expected generated test stub to explain when to delete it"
    )

    if flavour == APP:
        binstall = metadata.get("binstall")
        assert binstall is not None, (
            "expected app flavour Cargo.toml to include binstall metadata"
        )
        assert (
            binstall["pkg-url"]
            == "https://github.com/example/tooling_example/releases/download/"
            "v{ version }/tooling_example-{ target }{ binary-ext }"
        ), "expected app flavour binstall metadata to include package URL"
        assert binstall["pkg-fmt"] == "bin", (
            "expected app flavour binstall metadata to describe binary artifacts"
        )
        assert binstall["disabled-strategies"] == ["quick-install", "compile"], (
            "expected app flavour binstall metadata to disable unsupported strategies"
        )
        release_workflow = (project / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )
        parsed_release_workflow = yaml.safe_load(release_workflow)
        release_checkout_steps = [
            step
            for job in parsed_release_workflow["jobs"].values()
            for step in job["steps"]
            if step.get("uses", "").startswith("actions/checkout@")
        ]
        assert release_checkout_steps, (
            "expected app release workflow to check out sources"
        )
        assert all(
            step.get("with", {}).get("persist-credentials") is False
            for step in release_checkout_steps
        ), "expected release workflow checkout steps to disable credentials"
        assert (
            "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
            in release_workflow
        ), "expected app release workflow to use pinned upload-artifact action"
        assert "CROSS_REVISION: v0.2.5" in release_workflow, (
            "expected app release workflow to pin cross revision"
        )
        assert "aarch64-pc-windows-gnullvm" not in release_workflow, (
            "expected app release workflow to omit unsupported cross targets"
        )
        assert 'key: cross-${{ env.CROSS_REVISION }}' in release_workflow, (
            "expected app release workflow to cache cross by revision"
        )
        assert "files: |" in release_workflow, (
            "expected app release workflow to upload release files"
        )
    else:
        assert "binstall" not in metadata, (
            "expected lib flavour Cargo.toml to omit binstall metadata"
        )
