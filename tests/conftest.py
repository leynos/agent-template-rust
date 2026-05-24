from __future__ import annotations

"""Pytest fixtures for configuring pytest-copier template selection.

This module narrows pytest-copier's temporary template repository to the real
Copier inputs used by this project. Tests can use the normal `copier` fixture;
pytest-copier reads `copier_template_paths` during setup and copies only
`copier.yaml` and `template/` before rendering generated projects.

Example:
    A test that accepts `copier` and calls `copier.copy(...)` automatically uses
    these template paths.
"""

import pytest


@pytest.fixture(scope="session")
def copier_template_paths() -> list[str]:
    """Copy only template inputs into pytest-copier's temporary Git repo."""
    return ["copier.yaml", "template"]
