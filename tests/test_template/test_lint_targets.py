"""Rendered lint target tests."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from pytest_copier.plugin import CopierFixture
import pytest

from tests.helpers.generated_files import parse_toml_file
from tests.helpers.rendering import render_project
from tests.helpers.subprocess_env import generated_project_env
import shlex


def test_clippy_runs(tmp_path: Path, copier: CopierFixture) -> None:
    """Generated project passes its full lint target."""
    project = render_project(
        tmp_path,
        copier,
        project_name="ClippyExample",
        package_name="clippy_example",
    )
    project.run("make lint")


def test_generated_lint_configuration_enforces_environment_injection(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Generated lint configuration denies ambient environment operations."""
    project = render_project(
        tmp_path,
        copier,
        project_name="LintConfigurationExample",
        package_name="lint_configuration_example",
    )

    manifest = parse_toml_file(project / "Cargo.toml")
    clippy = parse_toml_file(project / "clippy.toml")

    assert manifest["lints"]["clippy"]["missing_assert_message"] == "deny", (
        "expected generated packages to require assertion messages"
    )
    assert manifest["lints"]["clippy"]["disallowed_methods"] == "deny", (
        "expected generated packages to deny configured methods"
    )
    assert manifest["lints"]["rust"] == {
        "unknown_lints": "deny",
        "renamed_and_removed_lints": "deny",
        "unsafe_code": "forbid",
        "missing_docs": "deny",
    }, "expected generated packages to deny unsafe or undocumented Rust code"
    assert manifest["lints"]["rustdoc"] == {
        "missing_crate_level_docs": "deny",
        "broken_intra_doc_links": "deny",
        "private_intra_doc_links": "deny",
        "bare_urls": "deny",
        "invalid_html_tags": "deny",
        "invalid_codeblock_attributes": "deny",
        "unescaped_backticks": "deny",
    }, "expected generated packages to deny malformed Rustdoc"
    assert clippy["disallowed-methods"] == [
        {"path": "std::env::var", "reason": "inject an environment reader"},
        {"path": "std::env::var_os", "reason": "inject an environment reader"},
        {"path": "std::env::vars", "reason": "inject an environment reader"},
        {"path": "std::env::vars_os", "reason": "inject an environment reader"},
        {
            "path": "std::env::set_var",
            "reason": "use a stub environment in tests",
        },
        {
            "path": "std::env::remove_var",
            "reason": "use a stub environment in tests",
        },
    ], "expected generated Clippy policy to list every ambient environment method"


@pytest.mark.parametrize(
    ("function_source", "expected_lint"),
    [
        (
            """

/// Validate that output is not empty.
pub fn validate_output(output: &str) {
    assert!(!output.is_empty());
}
""",
            "clippy::missing-assert-message",
        ),
        (
            """

/// Read the deployment mode directly from the process environment.
pub fn deployment_mode() -> Option<String> {
    std::env::var("DEPLOYMENT_MODE").ok()
}
""",
            "clippy::disallowed-methods",
        ),
    ],
    ids=["missing-assert-message", "ambient-environment-read"],
)
def test_make_lint_rejects_environment_policy_violations(
    tmp_path: Path,
    copier: CopierFixture,
    function_source: str,
    expected_lint: str,
) -> None:
    """Generated lint gate rejects representative policy violations."""
    project = render_project(
        tmp_path,
        copier,
        project_name="LintRejectionExample",
        package_name="lint_rejection_example",
    )
    lib_rs = project / "src" / "lib.rs"
    lib_rs.write_text(
        lib_rs.read_text(encoding="utf-8") + function_source,
        encoding="utf-8",
    )
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"

    result = subprocess.run(
        [make, "lint"],
        cwd=project.path,
        check=False,
        capture_output=True,
        text=True,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0, "expected make lint to reject the policy violation"
    assert expected_lint in output, f"expected make lint to report {expected_lint}"


@pytest.mark.parametrize(
    ("source", "expected_diagnostic"),
    [
        pytest.param(
            """//! Crate documentation.\n\n/// An unsafe operation.\npub unsafe fn unchecked() {}\n""",
            "unsafe-code",
            id="unsafe-code",
        ),
        pytest.param(
            """//! Crate documentation.\n\npub fn undocumented() {}\n""",
            "missing-docs",
            id="missing-public-api-docs",
        ),
        pytest.param(
            """/// A documented function.\npub fn documented() {}\n""",
            "missing-crate-level-docs",
            id="missing-crate-level-docs",
        ),
        pytest.param(
            """//! See [`MissingItem`].\n\n/// A documented function.\npub fn documented() {}\n""",
            "broken-intra-doc-links",
            id="broken-intra-doc-links",
        ),
        pytest.param(
            """//! Crate documentation.\n\nstruct PrivateItem;\n\n/// Returns a [`PrivateItem`].\npub fn documented() {}\n""",
            "private-intra-doc-links",
            id="private-intra-doc-links",
        ),
        pytest.param(
            """//! Crate documentation.\n\n/// See https://example.com for details.\npub fn documented() {}\n""",
            "bare-urls",
            id="bare-urls",
        ),
        pytest.param(
            """//! Crate documentation.\n\n/// An <invalid> HTML element.\npub fn documented() {}\n""",
            "invalid-html-tags",
            id="invalid-html-tags",
        ),
        pytest.param(
            """//! Crate documentation.\n\n/// ```should-panic\n/// assert_eq!(1, 2);\n/// ```\npub fn documented() {}\n""",
            "invalid-codeblock-attributes",
            id="invalid-codeblock-attributes",
        ),
        pytest.param(
            """//! Crate documentation.\n\n/// An `unclosed code span.\npub fn documented() {}\n""",
            "unescaped-backticks",
            id="unescaped-backticks",
        ),
    ],
)
def test_make_lint_rejects_rust_and_rustdoc_policy_violations(
    tmp_path: Path,
    copier: CopierFixture,
    source: str,
    expected_diagnostic: str,
) -> None:
    """Generated lint gate rejects representative Rust and Rustdoc violations."""
    project = render_project(
        tmp_path,
        copier,
        project_name="RustdocLintRejectionExample",
        package_name="rustdoc_lint_rejection_example",
    )
    (project / "src" / "lib.rs").write_text(source, encoding="utf-8")
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"

    result = subprocess.run(
        [make, "lint"],
        cwd=project.path,
        check=False,
        capture_output=True,
        text=True,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0, f"expected make lint to reject {expected_diagnostic}"
    assert expected_diagnostic in output, (
        f"expected make lint to report {expected_diagnostic}"
    )


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
    tool_bin = tmp_path / "tool-bin"
    user_bin = home / ".local" / "bin"
    cargo = tmp_path / "cargo"
    marker = tmp_path / "whitaker-ran"
    path_bin.mkdir(parents=True)
    tool_bin.mkdir()
    user_bin.mkdir(parents=True)
    bash = shutil.which("bash")
    assert bash is not None, "expected bash to be available for generated tests"
    for bin_dir in (path_bin, tool_bin):
        (bin_dir / "bash").symlink_to(bash)
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
            f"#!/bin/sh\n: > {shlex.quote(str(marker))}\n", encoding="utf-8"
        )
        expected_whitaker.chmod(0o755)
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"

    result = subprocess.run(
        [make, "lint"],
        cwd=project.path,
        env=generated_project_env(
            {
                "HOME": str(home),
                "PATH": str(
                    path_bin if whitaker_location == "path" else tool_bin
                ),
                "CARGO": str(cargo),
            }
        ),
        check=False,
        capture_output=True,
        text=True,
    )

    if expected_whitaker is None:
        assert result.returncode != 0, (
            "expected lint to fail without Whitaker\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        assert "whitaker" in result.stderr.lower(), (
            "expected missing Whitaker failure to identify the missing tool\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    else:
        assert result.returncode == 0, (
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        assert marker.exists(), (
            f"expected generated lint target to execute {whitaker_location} Whitaker\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        assert f"Whitaker binary: {expected_whitaker}" in result.stdout, (
            "expected generated lint target to resolve the configured Whitaker\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
