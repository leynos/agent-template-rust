"""Rendered en-GB-oxendict spelling gate contract tests."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import read_generated_text
from tests.helpers.rendering import render_project


def test_spelling_gate_enabled_by_default(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Default renders include the spelling gate files and wiring."""
    project = render_project(
        tmp_path,
        copier,
        project_name="SpellingExample",
        package_name="spelling_example",
    )

    assert (project / "typos.toml").exists(), (
        "expected generated project to include typos.toml by default"
    )
    assert (project / "scripts" / "generate_typos_config.py").exists(), (
        "expected generated project to include the typos.toml generator"
    )

    makefile = read_generated_text(project / "Makefile")
    assert "TYPOS_VERSION ?=" in makefile, (
        "expected generated Makefile to pin the typos version"
    )
    assert "TYPOS = uv tool run typos@$(TYPOS_VERSION)" in makefile, (
        "expected generated Makefile to run typos through uv tool run"
    )
    assert (
        "markdownlint: spellcheck ## Lint Markdown files and enforce "
        "en-GB-oxendict spelling"
    ) in makefile, "expected generated markdownlint target to depend on spellcheck"
    assert "python3 scripts/generate_typos_config.py --check" in makefile, (
        "expected generated spellcheck target to run the generator drift check"
    )
    assert "$(TYPOS) --config typos.toml --force-exclude" in makefile, (
        "expected generated spellcheck target to run typos over Markdown files"
    )

    ci_workflow = read_generated_text(project / ".github/workflows/ci.yml")
    assert "- name: Spelling (typos)" in ci_workflow, (
        "expected generated CI to include the spelling step"
    )
    assert "run: make spellcheck" in ci_workflow, (
        "expected generated CI spelling step to call the Makefile target"
    )
    setup_uv_index = ci_workflow.index("- name: Setup uv")
    spelling_index = ci_workflow.index("- name: Spelling (typos)")
    assert setup_uv_index < spelling_index, (
        "expected the spelling step to run after uv is installed"
    )

    repository_layout = read_generated_text(project / "docs/repository-layout.md")
    assert "typos.toml" in repository_layout, (
        "expected generated layout to document the spelling configuration"
    )
    assert "scripts/generate_typos_config.py" in repository_layout, (
        "expected generated layout to document the typos.toml generator"
    )


def test_spelling_gate_config_matches_generator(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """The generated typos.toml parses and matches the generator output."""
    project = render_project(
        tmp_path,
        copier,
        project_name="SpellingDrift",
        package_name="spelling_drift",
    )

    # The generator's --check mode parses the rendered document with
    # tomllib (failing fast on duplicate extend-words keys), asserts the
    # exact entry count, and diffs the committed file against the
    # generator output.
    project.run("python3 scripts/generate_typos_config.py --check")

    parsed = tomllib.loads(read_generated_text(project / "typos.toml"))
    assert parsed["default"]["locale"] == "en-gb", (
        "expected generated typos.toml to use the en-gb locale"
    )
    assert parsed["default"]["extend-words"], (
        "expected generated typos.toml to restore Oxford -ize spellings"
    )


def test_spelling_gate_disabled_leaves_no_trace(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Disabled renders omit the spelling gate files and wiring."""
    project = render_project(
        tmp_path,
        copier,
        project_name="NoSpelling",
        package_name="no_spelling",
        en_gb_oxendict=False,
    )

    assert not (project / "typos.toml").exists(), (
        "expected disabled render to omit typos.toml"
    )
    assert not (project / "scripts").exists(), (
        "expected disabled render to omit the scripts directory"
    )

    makefile = read_generated_text(project / "Makefile")
    assert "typos" not in makefile, (
        "expected disabled render Makefile to omit typos wiring"
    )
    assert "spellcheck" not in makefile, (
        "expected disabled render Makefile to omit the spellcheck target"
    )
    assert "markdownlint: ## Lint Markdown files" in makefile, (
        "expected disabled render to keep the plain markdownlint target"
    )

    ci_workflow = read_generated_text(project / ".github/workflows/ci.yml")
    assert "Spelling (typos)" not in ci_workflow, (
        "expected disabled render CI to omit the spelling step"
    )
    assert "make spellcheck" not in ci_workflow, (
        "expected disabled render CI to omit the spellcheck call"
    )

    repository_layout = read_generated_text(project / "docs/repository-layout.md")
    assert "typos.toml" not in repository_layout, (
        "expected disabled render layout to omit the spelling configuration"
    )

    agents = read_generated_text(project / "AGENTS.md")
    assert "typos" not in agents, (
        "expected disabled render AGENTS.md to omit spelling gate guidance"
    )

    developers_guide = read_generated_text(project / "docs/developers-guide.md")
    assert "Spelling gate" not in developers_guide, (
        "expected disabled render developer guide to omit the spelling section"
    )
