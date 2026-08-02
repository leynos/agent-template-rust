"""Rendered en-GB-oxendict spelling gate contract tests."""

from __future__ import annotations

import tomllib
import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
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
    assert "TYPOS := uv tool run typos@$(TYPOS_VERSION)" in makefile, (
        "expected generated Makefile to run typos through uv tool run"
    )
    assert (
        "markdownlint: spellcheck ## Lint Markdown files and enforce "
        "en-GB-oxendict spelling"
    ) in makefile, "expected generated markdownlint target to depend on spellcheck"
    assert "uv run scripts/generate_typos_config.py" in makefile, (
        "expected generated spellcheck target to honour the generator's Python version"
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
    assert "Spelling policy" in read_generated_text(
        project / "docs/developers-guide.md"
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
    assert not (project / "typos.local.toml").exists(), (
        "expected disabled render to omit the spelling overlay"
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
    assert "Spelling policy" not in developers_guide, (
        "expected disabled render developer guide to omit the spelling section"
    )
    users_guide = read_generated_text(project / "docs/users-guide.md")
    assert "spellcheck" not in users_guide
    assert "en-GB-oxendict" not in users_guide


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    flavour=st.sampled_from(["app", "lib"]),
    enable_polonius=st.booleans(),
    en_gb_oxendict=st.booleans(),
    polonius_path=st.sampled_from(
        [".cargo/config.toml", "rust-toolchain.toml", "docs/polonius.md"]
    ),
)
def test_spelling_and_polonius_options_are_independent(
    tmp_path: Path,
    copier: CopierFixture,
    flavour: str,
    enable_polonius: bool,
    en_gb_oxendict: bool,
    polonius_path: str,
) -> None:
    """Spelling traces vary only with spelling while Polonius output stays fixed."""
    case_root = Path(tempfile.mkdtemp(dir=tmp_path))
    project = render_project(
        case_root / "selected",
        copier,
        project_name="OptionIndependence",
        package_name="option_independence",
        flavour=flavour,
        enable_polonius=enable_polonius,
        en_gb_oxendict=en_gb_oxendict,
    )
    counterpart = render_project(
        case_root / "counterpart",
        copier,
        project_name="OptionIndependence",
        package_name="option_independence",
        flavour=flavour,
        enable_polonius=enable_polonius,
        en_gb_oxendict=not en_gb_oxendict,
    )

    assert (project / "typos.toml").exists() is en_gb_oxendict
    assert (project / "scripts" / "generate_typos_config.py").exists() is (
        en_gb_oxendict
    )
    makefile = read_generated_text(project / "Makefile")
    assert ("spellcheck" in makefile) is en_gb_oxendict

    selected_path = project / polonius_path
    counterpart_path = counterpart / polonius_path
    assert selected_path.exists() is counterpart_path.exists()
    if selected_path.exists():
        assert selected_path.read_bytes() == counterpart_path.read_bytes()
    selected_polonius_lines = [
        line for line in makefile.splitlines() if "POLONIUS" in line
    ]
    counterpart_polonius_lines = [
        line
        for line in read_generated_text(counterpart / "Makefile").splitlines()
        if "POLONIUS" in line
    ]
    assert selected_polonius_lines == counterpart_polonius_lines
