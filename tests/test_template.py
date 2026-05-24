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
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_copier.plugin import CopierFixture, CopierProject
from syrupy.assertion import SnapshotAssertion

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


def assert_generated_tooling_contracts(
    *,
    package: dict[str, Any],
    metadata: dict[str, Any],
    flavour: str,
    makefile: str,
    cargo_config: str,
    dev_target: str,
    rust_toolchain: str,
    parsed_ci_workflow: dict[str, Any],
    ci_workflow: str,
    readme: str,
    test_stub: str,
    release_workflow: str | None,
) -> None:
    """Assert generated tooling contracts from a single validator."""
    _assert_cargo_package_contracts(package, metadata, flavour)
    _assert_makefile_contracts(makefile)
    _assert_cargo_config_contracts(cargo_config, dev_target, rust_toolchain)
    _assert_ci_workflow_contracts(parsed_ci_workflow, ci_workflow, test_stub)
    assert "Development builds use `mold` on Linux" in readme, (
        "expected generated README to document mold for development builds"
    )
    assert "Coverage generation uses `lld`" in readme, (
        "expected generated README to document lld for coverage"
    )
    if release_workflow is not None:
        _assert_release_workflow_contracts(release_workflow)


def _assert_cargo_package_contracts(
    package: dict[str, Any], metadata: dict[str, Any], flavour: str
) -> None:
    """Assert generated Cargo package metadata contracts."""
    assert package.get("description") == "ToolingExample package used by template tests.", (
        "expected generated Cargo.toml to include package description"
    )
    assert package.get("repository") == "https://github.com/example/tooling_example", (
        "expected generated Cargo.toml to include repository URL"
    )
    assert package.get("homepage") == "https://example.com/tooling_example", (
        "expected generated Cargo.toml to include homepage URL"
    )
    assert package.get("keywords") == ["rust", "template"], (
        "expected generated Cargo.toml to include package keywords"
    )
    assert package.get("categories") == ["development-tools"], (
        "expected generated Cargo.toml to include package categories"
    )
    assert package.get("license") == "ISC", (
        "expected generated Cargo.toml to include ISC licence"
    )

    if flavour == APP:
        binstall = metadata.get("binstall")
        assert isinstance(binstall, dict), (
            "expected app flavour Cargo.toml to include binstall metadata"
        )
        assert (
            binstall.get("pkg-url")
            == "https://github.com/example/tooling_example/releases/download/"
            "v{ version }/tooling_example-{ target }{ binary-ext }"
        ), "expected app flavour binstall metadata to include package URL"
        assert binstall.get("pkg-fmt") == "bin", (
            "expected app flavour binstall metadata to describe binary artifacts"
        )
        assert binstall.get("disabled-strategies") == ["quick-install", "compile"], (
            "expected app flavour binstall metadata to disable unsupported strategies"
        )
    else:
        assert "binstall" not in metadata, (
            "expected lib flavour Cargo.toml to omit binstall metadata"
        )


def _assert_makefile_contracts(makefile: str) -> None:
    """Assert generated Makefile tooling contracts."""
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
    assert 'echo "Whitaker binary: $(WHITAKER)"' in makefile, (
        "expected generated Makefile lint target to log Whitaker resolution"
    )
    assert 'echo "coverage linker flags: $(COVERAGE_LINKER_FLAGS)"' in makefile, (
        "expected generated Makefile coverage target to log linker flags"
    )


def _assert_cargo_config_contracts(
    cargo_config: str, dev_target: str, rust_toolchain: str
) -> None:
    """Assert generated Cargo config and toolchain contracts."""
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


def _assert_ci_workflow_contracts(
    parsed_ci_workflow: dict[str, Any],
    ci_workflow: str,
    test_stub: str,
) -> None:
    """Assert generated CI workflow and adjacent documentation contracts."""
    jobs = require_mapping(parsed_ci_workflow, "jobs", "CI workflow")
    checkout_steps = extract_checkout_steps(jobs)
    assert checkout_steps, "expected generated CI workflow to check out sources"
    assert all(
        step.get("with", {}).get("persist-credentials") is False
        for step in checkout_steps
    ), "expected generated CI checkout steps to disable credential persistence"

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
    assert "Whitaker cache hit:" in ci_workflow, (
        "expected generated CI workflow to log Whitaker cache status"
    )
    assert "Installing Whitaker installer at" in ci_workflow, (
        "expected generated CI workflow to log Whitaker installation"
    )
    assert "Whitaker binary:" in ci_workflow, (
        "expected generated CI workflow to log Whitaker binary resolution"
    )
    assert "Log coverage linker configuration" in ci_workflow, (
        "expected generated CI workflow to log coverage linker configuration"
    )

    assert "Delete this file as soon as the project has real" in test_stub, (
        "expected generated test stub to explain when to delete it"
    )


def _assert_release_workflow_contracts(release_workflow: str) -> None:
    """Assert generated release workflow contracts."""
    parsed_release_workflow = parse_yaml_mapping(release_workflow, "release workflow")
    jobs = require_mapping(parsed_release_workflow, "jobs", "release workflow")
    release_checkout_steps = extract_checkout_steps(jobs)
    assert release_checkout_steps, "expected app release workflow to check out sources"
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


def extract_checkout_steps(jobs: dict[str, Any]) -> list[dict[str, Any]]:
    """Return checkout steps from a parsed GitHub Actions jobs mapping."""
    return [
        step
        for job in jobs.values()
        if isinstance(job, dict)
        for step in job.get("steps", [])
        if isinstance(step, dict)
        and step.get("uses", "").startswith("actions/checkout@")
    ]
