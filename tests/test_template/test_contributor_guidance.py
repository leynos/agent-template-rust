"""Rendered contributor guidance and decision-history contract tests."""

from __future__ import annotations

from pathlib import Path

from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import read_generated_text
from tests.helpers.rendering import render_project

PLANNING_AND_BOUNDARY_GUIDANCE = (
    "## Planning and verification",
    "observable acceptance criteria",
    (
        "Identify affected behavioural contracts, invariants, and failure modes "
        "before choosing the implementation"
    ),
    "Preserve decision gates and stopping conditions",
    (
        "When plan approval is required, deliver the plan for review and wait "
        "for approval before implementation"
    ),
    (
        "mark relevant roadmap entries complete only after their acceptance "
        "criteria pass"
    ),
    "## Architecture and operational boundaries",
    (
        "Keep domain policy separate from filesystem, process, network, "
        "framework, and telemetry adapters"
    ),
    "Make fallibility, mutation, and side-effects explicit in APIs",
    (
        "Preserve I/O, parsing, and permission errors rather than silently "
        "converting them into absence, `false`, or empty success"
    ),
    "A timeout does not bound accumulated bytes",
    "Validate untrusted inputs before privileged effects",
    "Select verification proportionately",
    (
        "For each changed behaviour, identify a plausible incorrect "
        "implementation and ensure the test rejects it"
    ),
    ("Negative tests must establish the precondition that would expose the defect"),
    (
        "Keep secrets, credentials, raw payloads, and sensitive paths out of "
        "logs, errors, traces, and snapshots"
    ),
)

DECISION_HISTORY_REFERENCE = (
    "Preserve accepted ADR decisions; record subsequent changes through the "
    "[ADR amendment and supersession process](docs/documentation-style-guide.md#amendment-and-supersession)."
)

AMENDMENT_PROCESS_GUIDANCE = (
    "### Amendment and supersession",
    "An accepted ADR is a historical record of the decision made at that time.",
    (
        "For a clarification that does not change the decision, amend the ADR "
        "in place, update its `Date`, and record the change in an "
        "`## Amendment` section"
    ),
    "For a changed decision, create a new ADR with the next sequence number.",
    "`Supersedes: [ADR-NNN](adr-NNN-short-description.md)`",
    (
        "`Superseded by [ADR-MMM](adr-MMM-short-description.md)` without "
        "deleting the original record"
    ),
    (
        "Link the replacing ADR from every design document and index that "
        "referenced the superseded decision."
    ),
    "Run the documentation and spelling gates after either change",
)

REMOVED_HOST_TOOL_INVENTORY = (
    "## Additional tooling",
    "The following tooling is available in this environment",
    "`mbake` — A Makefile validator",
    "`bpftrace`",
    "`ncdu`",
    "`difft` **(Difftastic)**",
)


def _normalized(document: str) -> str:
    """Collapse whitespace so phrases match across line wrapping."""
    return " ".join(document.split())


def _assert_contains_all(document: str, required: tuple[str, ...]) -> None:
    """Assert a document retains each required guidance phrase."""
    normalized_document = _normalized(document)
    missing = [
        text for text in required if _normalized(text) not in normalized_document
    ]
    assert not missing, f"rendered guidance is missing {missing!r}"


def test_rendered_agents_retains_planning_and_boundary_contracts(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Rendered contributor guidance states the planning and boundary contracts."""
    project = render_project(
        tmp_path,
        copier,
        project_name="PlanningGuidanceExample",
        package_name="planning_guidance_example",
    )
    agents = read_generated_text(project / "AGENTS.md")

    _assert_contains_all(agents, PLANNING_AND_BOUNDARY_GUIDANCE)


def test_rendered_agents_links_documented_adr_amendment_process(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Decision-history guidance links an amendment process the guide documents."""
    project = render_project(
        tmp_path,
        copier,
        project_name="DecisionHistoryExample",
        package_name="decision_history_example",
    )
    agents = read_generated_text(project / "AGENTS.md")
    style_guide = read_generated_text(project / "docs" / "documentation-style-guide.md")

    _assert_contains_all(agents, (DECISION_HISTORY_REFERENCE,))
    _assert_contains_all(style_guide, AMENDMENT_PROCESS_GUIDANCE)


def test_rendered_agents_omits_host_tool_inventory(
    tmp_path: Path, copier: CopierFixture
) -> None:
    """Rendered contributor guidance does not reinstate the host tool inventory."""
    project = render_project(
        tmp_path,
        copier,
        project_name="ToolInventoryExample",
        package_name="tool_inventory_example",
    )
    agents = _normalized(read_generated_text(project / "AGENTS.md"))

    present = [text for text in REMOVED_HOST_TOOL_INVENTORY if text in agents]
    assert not present, f"host tool inventory has returned: {present!r}"
