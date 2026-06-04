"""Assert rendered documentation contracts for generated Rust projects."""

from __future__ import annotations

from tests.helpers.rendering import APP


def assert_documentation_navigation_contracts(
    docs_contents: str, repository_layout: str, flavour: str
) -> None:
    """Assert generated documentation navigation and layout contracts.

    Parameters
    ----------
    docs_contents
        Rendered ``docs/contents.md`` text from the generated project.
    repository_layout
        Rendered ``docs/repository-layout.md`` text from the generated project.
    flavour
        Generated project flavour. App projects must document executable and
        release-workflow paths; library projects must document library paths.

    Returns
    -------
    None
        The helper returns ``None`` when all documentation contracts pass.

    Raises
    ------
    AssertionError
        Raised when generated documentation omits expected navigation links,
        repository layout entries, or flavour-specific paths.
    """
    assert "[Documentation contents](contents.md)" in docs_contents, (
        "expected generated contents file to link to itself"
    )
    assert "[Repository layout](repository-layout.md)" in docs_contents, (
        "expected generated contents file to link to the layout reference"
    )
    assert "[Documentation style guide](documentation-style-guide.md)" in (
        docs_contents
    ), "expected generated contents file to link to the style guide"
    assert "docs/contents.md" in repository_layout, (
        "expected generated layout to document the contents file"
    )
    assert "docs/repository-layout.md" in repository_layout, (
        "expected generated layout to document itself"
    )
    assert "Cargo.toml" in repository_layout, (
        "expected generated layout to document Cargo metadata"
    )
    assert "Makefile" in repository_layout, (
        "expected generated layout to document public command entrypoints"
    )
    assert "checks. - `" not in repository_layout, (
        "expected generated layout bullets to render on separate lines"
    )
    assert "responsibilities. - `" not in repository_layout, (
        "expected generated layout flavour bullets to render on separate lines"
    )

    if flavour == APP:
        assert ".github/workflows/release.yml" in repository_layout, (
            "expected app layout to document the release workflow"
        )
        assert "src/main.rs" in repository_layout, (
            "expected app layout to document the executable entrypoint"
        )
        assert "src/lib.rs" not in repository_layout, (
            "expected app layout to omit the library crate root"
        )
    else:
        assert ".github/workflows/release.yml" not in repository_layout, (
            "expected lib layout to omit the app release workflow"
        )
        assert "src/lib.rs" in repository_layout, (
            "expected lib layout to document the library crate root"
        )
        assert "src/main.rs" not in repository_layout, (
            "expected lib layout to omit the executable entrypoint"
        )
