"""Rendered contributor guidance and decision-history contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.generated_files import read_generated_text
from tests.helpers.rendering import render_project

# Each value is a complete rendered Markdown block: a heading line, a paragraph,
# or a top-level bullet without its "- " marker. Wrapped source lines are joined,
# so an inserted negation or altered wording no longer matches the contract.
PLAN_APPROVAL_AND_ROADMAP_BULLET = (
    "When plan approval is required, deliver the plan for review and wait for "
    "approval before implementation. Keep the active plan current, and mark "
    "relevant roadmap entries complete only after their acceptance criteria pass."
)

PLANNING_AND_BOUNDARY_GUIDANCE = (
    "## Planning and verification",
    (
        "For non-trivial work, prepare or update a self-contained ExecPlan using "
        "the available planning guidance. Identify the outcome, relevant roadmap "
        "and design references, prerequisites, scope exclusions, and observable "
        "acceptance criteria. Signpost relevant documentation and skills."
    ),
    (
        "Identify affected behavioural contracts, invariants, and failure modes "
        "before choosing the implementation. Use these to pressure-test the "
        "proposed API and verification strategy."
    ),
    (
        "Plan the smallest useful increment. Preserve decision gates and stopping "
        "conditions; defer abstractions, dependencies, macros, or published "
        "components until the preceding evidence justifies them."
    ),
    (
        "Where formal verification is selected, first sketch the independent "
        "model, premises, invariants, representation relationships, and principal "
        "proof obligations. Treat proposed lemmas as provisional. Defer detailed "
        "proof engineering until implementation exposes the verification "
        "conditions; do not add assumptions, admissions, or trusted proof bodies "
        "merely to make incomplete proofs pass. Unproved statements may remain in "
        "the plan until that milestone."
    ),
    (
        "Give each major milestone explicit acceptance commands, including "
        "applicable proof checks and the formatting, linting, and test gates. "
        "Keep commits coherent and useful as rollback points."
    ),
    PLAN_APPROVAL_AND_ROADMAP_BULLET,
    "## Architecture and operational boundaries",
    (
        "Keep domain policy separate from filesystem, process, network, framework, "
        "and telemetry adapters. Inject dependencies where needed through existing "
        "interfaces or narrow closures; avoid speculative layers and dependency "
        "cycles."
    ),
    (
        "Make fallibility, mutation, and side-effects explicit in APIs. Preserve "
        "I/O, parsing, and permission errors rather than silently converting them "
        "into absence, `false`, or empty success. Compose side-effects at "
        "orchestration boundaries; queries must not hide writes or unrelated "
        "workflow policy."
    ),
    (
        "For streams, subprocesses, retries, caches, queues, and background tasks, "
        "define applicable size limits, deadlines, ownership, cancellation, and "
        "cleanup. A timeout does not bound accumulated bytes. Include waiting and "
        "cleanup in the operation's budget. Define partial-failure and retry "
        "behaviour where updates span multiple effects; keep locks narrow and "
        "ordered, avoiding holds across awaits or external calls unless explicitly "
        "justified."
    ),
    (
        "Validate untrusted inputs before privileged effects, use structured APIs "
        "instead of executable string construction, and grant only required "
        "permissions."
    ),
    (
        "For each changed behaviour, identify a plausible incorrect implementation "
        "and ensure the test rejects it. Assert observable results, errors, and "
        "side-effects; mock calls or configuration text alone do not prove "
        "execution. Negative tests must establish the precondition that would "
        "expose the defect."
    ),
    (
        "Exercise the boundary that owns the promise: public API, executable, or "
        "protocol adapter. Private-helper tests complement this coverage. Fakes "
        "must support relevant failures and verify their propagation through "
        "orchestration. Test local integration contracts rather than third-party "
        "tools themselves."
    ),
    (
        "Test relevant partial failures, cancellation, shutdown, and cleanup with "
        "deterministic coordination where practical. Avoid relying solely on sleeps "
        "or exact deltas from shared global counters. Restore fixture resources even "
        "when assertions fail, and account for host capabilities and privileges."
    ),
    (
        "Select verification proportionately: named examples or `rstest` tables for "
        "finite contracts, `proptest` for broad input spaces or operation "
        "sequences, and `kani` for exhaustive exploration within explicit bounds. "
        "Use `verus` for selected lemmas or contractual invariants requiring "
        "unbounded proof over a suitable semantic model. Proofs must establish the "
        "property from appropriate premises, not restate or assume it. "
        "Straightforward integration and presentation work must not acquire "
        "artificial proof obligations. Keep executable integration and behavioural "
        "tests alongside proofs."
    ),
    (
        "Keep secrets, credentials, raw payloads, and sensitive paths out of logs, "
        "errors, traces, and snapshots. Prefer stable error categories and bounded "
        "contextual fields over arbitrary error text."
    ),
    (
        "For new operational telemetry, document and exercise the application's "
        "collection path. Verify a relevant event produces a non-zero signal "
        "through that path; helper-only assertions or comparisons of zero counters "
        "do not establish useful instrumentation."
    ),
)

DECISION_HISTORY_REFERENCE = (
    (
        "**Decision history:** Preserve accepted ADR decisions; record subsequent "
        "changes through the [ADR amendment and supersession process]"
        "(docs/documentation-style-guide.md#amendment-and-supersession). Capture "
        "proof-driven API, representation, and invariant decisions in the design "
        "documentation."
    ),
)

AMENDMENT_PROCESS_GUIDANCE = (
    "### Amendment and supersession",
    (
        "An accepted ADR is a historical record of the decision made at that time. "
        "Preserve its original context, decision, and consequences; do not rewrite "
        "them to describe later behaviour."
    ),
    (
        "For a clarification that does not change the decision, amend the ADR in "
        "place, update its `Date`, and record the change in an `## Amendment` "
        "section that states the date and what was clarified."
    ),
    (
        "For a changed decision, create a new ADR with the next sequence number. "
        "State `Supersedes: [ADR-NNN](adr-NNN-short-description.md)` in the new "
        "record, and change the superseded record's `Status` to `Superseded by "
        "[ADR-MMM](adr-MMM-short-description.md)` without deleting the original "
        "record."
    ),
    (
        "Link the replacing ADR from every design document and index that "
        "referenced the superseded decision."
    ),
    (
        "Run the documentation and spelling gates after either change so links "
        "and terminology stay current."
    ),
)

REMOVED_HOST_TOOL_NAMES = (
    "mbake",
    "strace",
    "gdb",
    "ripgrep",
    "ltrace",
    "valgrind",
    "bpftrace",
    "lsof",
    "htop",
    "iotop",
    "ncdu",
    "tree",
    "bat",
    "delta",
    "tcpdump",
    "nmap",
    "lldb",
    "eza",
    "fzf",
    "hyperfine",
    "shellcheck",
    "fd",
    "checkmake",
    "srgn",
    "difft",
)

REMOVED_HOST_TOOL_INVENTORY = (
    "## Additional tooling",
    "The following tooling is available in this environment",
    *(f"- `{name}`" for name in REMOVED_HOST_TOOL_NAMES),
)


def _normalized(text: str) -> str:
    """Collapse whitespace so guidance matches across line wrapping."""
    return " ".join(text.split())


def _block_text(lines: list[str]) -> str:
    """Join a block's lines and drop a leading top-level bullet marker."""
    return _normalized(" ".join(lines)).removeprefix("- ")


def _guidance_blocks(document: str) -> set[str]:
    """Split Markdown into normalized heading, paragraph, and bullet blocks."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw_line in document.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                blocks.append(current)
                current = []
            continue
        if current and line.startswith(("#", "- ")):
            blocks.append(current)
            current = []
        current.append(line)
    if current:
        blocks.append(current)
    return {_block_text(block) for block in blocks}


def _assert_guidance_blocks(document: str, required: tuple[str, ...]) -> None:
    """Assert each required guidance block appears verbatim in the document."""
    blocks = _guidance_blocks(document)
    missing = [text for text in required if _normalized(text) not in blocks]
    assert not missing, f"rendered guidance is missing {missing!r}"


def test_guidance_blocks_reject_negated_requirement() -> None:
    """A negated roadmap requirement does not satisfy the guidance contract."""
    document = (
        "## Planning and verification\n\n"
        "- When plan approval is required, deliver the plan for review and wait for "
        "approval before implementation. Keep the active plan current, and do not "
        "mark relevant roadmap entries complete only after their acceptance "
        "criteria pass.\n"
    )

    with pytest.raises(AssertionError, match="roadmap entries"):
        _assert_guidance_blocks(document, (PLAN_APPROVAL_AND_ROADMAP_BULLET,))


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

    _assert_guidance_blocks(agents, PLANNING_AND_BOUNDARY_GUIDANCE)


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

    _assert_guidance_blocks(agents, DECISION_HISTORY_REFERENCE)
    _assert_guidance_blocks(style_guide, AMENDMENT_PROCESS_GUIDANCE)


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
