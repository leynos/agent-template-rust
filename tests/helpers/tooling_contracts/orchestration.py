"""Compose rendered tooling contract assertions for generated Rust projects."""

from __future__ import annotations

from typing import Any

from tests.helpers.tooling_contracts.cargo import (
    _assert_cargo_config_contracts,
    _assert_cargo_package_contracts,
)
from tests.helpers.tooling_contracts.documentation import (
    assert_documentation_navigation_contracts,
)
from tests.helpers.tooling_contracts.makefile import _assert_makefile_contracts
from tests.helpers.tooling_contracts.workflows import (
    _assert_ci_workflow_contracts,
    _assert_release_workflow_contracts,
)


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
    act_workflow: str,
    docs_contents: str,
    repository_layout: str,
    readme: str,
    test_stub: str,
    release_workflow: str | None,
) -> None:
    """Assert generated tooling contracts from a single validator.

    Parameters
    ----------
    package
        Parsed ``Cargo.toml`` package table for the generated project.
    metadata
        Parsed optional ``Cargo.toml`` package metadata table.
    flavour
        Generated project flavour, such as ``app`` or ``lib``.
    makefile
        Rendered generated-project ``Makefile`` text.
    cargo_config
        Rendered generated-project ``.cargo/config.toml`` text.
    dev_target
        Development target triple selected for the rendered project.
    rust_toolchain
        Rendered generated-project ``rust-toolchain.toml`` text.
    parsed_ci_workflow
        Parsed generated CI workflow mapping.
    ci_workflow
        Rendered generated CI workflow text.
    act_workflow
        Rendered generated act-validation workflow text.
    docs_contents
        Rendered ``docs/contents.md`` text.
    repository_layout
        Rendered ``docs/repository-layout.md`` text.
    readme
        Rendered generated-project ``README.md`` text.
    test_stub
        Rendered generated-project test stub text.
    release_workflow
        Rendered release workflow text for app projects, or ``None`` for
        library projects.

    Returns
    -------
    None
        The helper returns ``None`` when all generated tooling contracts pass.

    Raises
    ------
    AssertionError
        Raised when any generated Cargo metadata, Makefile, Cargo config, CI,
        documentation, README, test-stub, or release-workflow contract fails.

    Notes
    -----
    This public helper composes the private ``_assert_*`` validators so tests
    can validate a rendered project through one contract entrypoint.
    """
    _assert_cargo_package_contracts(package, metadata, flavour)
    _assert_makefile_contracts(makefile, flavour)
    _assert_cargo_config_contracts(cargo_config, dev_target, rust_toolchain)
    _assert_ci_workflow_contracts(
        parsed_ci_workflow, ci_workflow, act_workflow, test_stub
    )
    assert_documentation_navigation_contracts(
        docs_contents, repository_layout, flavour
    )
    assert "[Documentation contents](docs/contents.md)" in readme, (
        "expected generated README to link to the documentation contents"
    )
    assert "[User guide](docs/users-guide.md)" in readme, (
        "expected generated README to link to the user guide"
    )
    assert "[Developer guide](docs/developers-guide.md)" in readme, (
        "expected generated README to link to the developer guide"
    )
    if release_workflow is not None:
        _assert_release_workflow_contracts(release_workflow)
