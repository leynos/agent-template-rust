"""Rendered lint and environment-policy guidance tests."""

from __future__ import annotations

from pathlib import Path

from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import read_generated_text
from tests.helpers.rendering import render_project


def _assert_contains_all(document: str, required_text: tuple[str, ...]) -> None:
    """Assert a document contains each stable policy phrase."""
    normalized_document = " ".join(document.split())
    for text in required_text:
        normalized_text = " ".join(text.split())
        assert normalized_text in normalized_document, (
            f"expected policy guidance to contain {text!r}"
        )


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
            (
                'RUSTDOCFLAGS="$(RUSTDOC_FLAGS)" '
                'RUSTFLAGS="$(DEV_RUST_FLAGS)" cargo doc --no-deps'
            ),
            "cargo clippy --workspace --all-targets --all-features -- -D warnings",
            (
                'RUSTFLAGS="$(DEV_RUST_FLAGS)" whitaker --all -- '
                "--all-targets --all-features"
            ),
            (
                "TEST_CMD := $(if $(shell $(CARGO) nextest --version "
                "2>/dev/null),nextest run,test)"
            ),
            "test: export RUSTFLAGS := $(DEV_RUST_FLAGS)",
            "$(CARGO) $(TEST_CMD) $(TEST_FLAGS) $(BUILD_JOBS)",
            (
                'RUSTDOCFLAGS="$(RUSTDOC_FLAGS)" $(CARGO) test --doc '
                "--workspace --all-features"
            ),
            "with `cargo-nextest` when available",
            "falling back to `cargo test`",
            "with Rust warnings denied",
            "all-feature workspace doctests separately with Rustdoc warnings denied",
            "Documentation warnings, Clippy warnings, and Whitaker findings",
            "Every module **must** begin with a module level (`//!`) comment",
            "Document public APIs using Rustdoc comments (`///`)",
            "Every `assert!`, `assert_eq!`, and `assert_ne!` invocation",
            "custom diagnostic message",
            "Completed execplans are historical documents",
            "Do not retroactively update completed execplan documents",
            "place that payload behind `Box`; use `Arc` only when shared ownership",
            "Add snapshot tests using `insta`",
            "pair them with semantic assertions for business rules and schema contracts",
            "normalize nondeterministic fields before snapshotting",
            "Do not accept brittle snapshots",
            "Add compile-time behaviour tests using `trybuild`",
            "compile-fail and compile-pass contracts",
        ),
    )


def test_rendered_stub_asserts_expected_cargo_package_metadata(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Generated stub checks Cargo metadata against the rendered package name."""
    package_name = "metadata_stub_example"
    project = render_project(
        tmp_path,
        copier,
        project_name="MetadataStubExample",
        package_name=package_name,
    )
    stub = read_generated_text(project / "tests" / "stub.rs")

    assert (
        f'assert_eq!(\n        env!("CARGO_PKG_NAME"),\n        "{package_name}",'
        in stub
    )
    assert "Cargo package metadata should match the generated package name" in stub


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
        "Declare the current `mockable` dependency",
        "Wire the environment adapter at the composition root",
        "construct `mockable::DefaultEnv` only in production",
        "Update contributor guidance in `AGENTS.md`",
        "the `assert_cmd` child-process exception",
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
            "Triage: Accepted",
            "We decided to inject `mockable::Env`",
            "construct `mockable::DefaultEnv` only",
            "production composition root",
            "use `mockable::MockEnv` in tests",
            "We reject direct",
            "`std::env` access in domain code",
            "Process-wide locks are prohibited",
            "serial-test attributes",
            "`assert_cmd`",
        ),
    )
