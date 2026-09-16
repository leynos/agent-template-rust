"""Real-binary smoke test for the generated project's spelling gate.

The shared ``typos-config-builder`` gate is not exercised by any unit test in
this repository: it is an external, pinned tool. This test proves the rendered
wiring works end to end by running ``make spelling`` in a generated project and
requiring a clean exit. It needs network access to resolve the pinned gate and
the live shared dictionary, so it is marked ``slow``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import render_project


def test_generated_project_ships_no_pregenerated_spelling_config(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """The template payload carries the overlay but no generated config."""
    project = render_project(
        tmp_path,
        copier,
        project_name="OverlayExample",
        package_name="overlay_example",
    )

    assert (project / "typos.local.toml").exists(), (
        "expected the rendered project to ship the narrow spelling overlay"
    )
    assert not (project / "typos.toml").exists(), (
        "expected the gate to generate typos.toml rather than the template"
    )
    assert not (project / "scripts/generate_typos_config.py").exists(), (
        "expected the retired vendored spelling generator to be absent"
    )
    assert not (project / "scripts/typos_rollout.py").exists(), (
        "expected the retired vendored spelling rollout module to be absent"
    )


@pytest.mark.slow
def test_generated_project_spelling_gate_passes(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """A freshly generated project passes its own ``make spelling`` gate."""
    if shutil.which("uv") is None:
        pytest.skip("uv is unavailable to resolve the pinned spelling gate")
    project = render_project(
        tmp_path,
        copier,
        project_name="SpellingExample",
        package_name="spelling_example",
    )

    project.run("make spelling")

    assert (project / "typos.toml").exists(), (
        "expected the gate to generate typos.toml on its first run"
    )
