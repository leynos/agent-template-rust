from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def copier_template_paths() -> list[str]:
    """Copy only template inputs into pytest-copier's temporary Git repo."""
    return ["copier.yaml", "template"]
