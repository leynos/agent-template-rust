"""Rendered lint and environment-policy guidance tests."""

from __future__ import annotations

from pathlib import Path

from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import read_generated_text
from tests.helpers.rendering import render_project


def _assert_contains_all(document: str, required_text: tuple[str, ...]) -> None:
    """Assert a document contains each stable policy phrase."""
    for text in required_text:
        assert text in document, f"expected policy guidance to contain {text!r}"


def test_rendered_agents_requires_injected_environment_and_diagnostics(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Rendered contributor guidance states the enforceable policy boundaries."""
    project = render_project(
        tmp_path,
        copier,
        project_name="PolicyGuidanceExample",
        package_name="policy_guidance_example",
    )
    agents = read_generated_text(project / "AGENTS.md")

    _assert_contains_all(
        agents,
        (
            "must accept an injected environment: `mockable::Env`",
            "`mockable::DefaultEnv` supplied at the production composition root",
            "`mockable::MockEnv` in tests",
            "`assert_cmd` may configure",
            "`Command::env`/`Command::env_clear`",
            "Subprocess isolation is the sole exemption",
            "Process-wide locks are not an escape hatch",
            "shared `Mutex`, `OnceLock`, or `serial_test` attribute",
            "Clippy warnings MUST be disallowed",
            "Every module **must** begin with a module level (`//!`) comment",
            "Document public APIs using Rustdoc comments (`///`)",
            "Every `assert!`, `assert_eq!`, and `assert_ne!` invocation",
            "custom diagnostic message",
        ),
    )


def test_policy_documentation_covers_validation_and_migration(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Maintained and rendered guides document the enforceable policy."""
    project = render_project(
        tmp_path,
        copier,
        project_name="PolicyDocumentationExample",
        package_name="policy_documentation_example",
    )
    maintained_user_guide = read_generated_text(Path("docs/users-guide.md"))
    rendered_user_guide = read_generated_text(project / "docs" / "users-guide.md")
    developer_guide = read_generated_text(Path("docs/developers-guide.md"))
    decision = read_generated_text(
        Path("docs/adr-005-injected-environment-boundary.md")
    )
    user_policy = (
        "`unknown_lints`, `renamed_and_removed_lints`",
        "`unsafe_code`",
        "`missing_docs`",
        "`missing_crate_level_docs`",
        "`invalid_codeblock_attributes`",
        "`missing_assert_message`",
        "`disallowed_methods`",
        "process-environment readers, iterators, and mutation functions",
        "these policies are not advisory",
        "`mockable::DefaultEnv`",
        "`mockable::MockEnv`",
        "`assert_cmd`",
        "`Command::env` and `Command::env_clear`",
        "`make lint` builds documentation",
        "all-feature workspace doctests",
        "Rustdoc warnings denied",
        "Migrate an Existing",
        "`[lints.clippy]`, `[lints.rust]`, and `[lints.rustdoc]`",
    )

    _assert_contains_all(maintained_user_guide, user_policy)
    _assert_contains_all(rendered_user_guide, user_policy)
    _assert_contains_all(
        developer_guide,
        (
            "Generated Lint and Environment Contract",
            "warnings as failures",
            "only the composition root constructs `mockable::DefaultEnv`",
            "`test_make_lint_rejects_rust_and_rustdoc_policy_violations`",
            "[ADR-005](adr-005-injected-environment-boundary.md)",
        ),
    )
    _assert_contains_all(
        decision,
        (
            "direct `std::env` access",
            "constructing `mockable::DefaultEnv` only",
            "at the production composition root",
            "using `mockable::MockEnv` in tests",
            "Process-wide locks are prohibited",
            "serial-test attributes",
            "`assert_cmd`",
        ),
    )
