# Validate Documentation Snapshots with mdast JSON

This ExecPlan (execution plan) is a living document. The sections
`Constraints`, `Tolerances`, `Risks`, `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work
proceeds.

Status: DRAFT

## Purpose / Big Picture

Documentation snapshot tests should fail when the meaning or structure of a
Markdown document changes, not when line wrapping, table alignment, or other
formatting-only details change. Markdown formatting is already checked by
`markdownlint-cli2` and `mdtablefix`; snapshot tests should instead compare a
normalized Markdown abstract syntax tree.

After this change, the parent template tests and the tests rendered into
generated Rust projects will parse documentation files into mdast JSON. An
mdast document is the Markdown abstract syntax tree used by the unified
ecosystem: headings, paragraphs, lists, links, tables, code blocks, and other
document nodes represented as structured JSON. The snapshot tests will remove
position and offset fields before snapshotting so formatting changes do not
churn snapshots. A reviewer can observe success by changing only line wrapping
in a documented file and seeing the mdast snapshot remain stable, then changing
a heading, link target, list item, table cell, or code block content and seeing
the focused snapshot fail.

This plan does not derive from a roadmap task. It is a direct change request
for the `mdast-snapshot-assertions` branch.

## Constraints

The branch for this work is `mdast-snapshot-assertions`, tracking
`origin/mdast-snapshot-assertions`. The plan file is
`docs/execplans/mdast-snapshot-assertions.md`.

This repository is a Copier template. Files under `template/` are rendered
into downstream Rust projects, while files under `tests/` validate rendered
output through `pytest-copier`. Any generated-project test behaviour must be
implemented in `template/` and proven from the parent repository tests.

Follow the repository guidance in `AGENTS.md`: prefer Makefile targets, run
long gates through `tee` into `/tmp`, do not run format, lint, or test suites in
parallel, and commit after each completed and gated change.

The work must validate document semantics, not Markdown formatting. Do not use
raw Markdown text, bytes, or binary file snapshots for documentation semantics.
Do not remove `markdownlint-cli2` or `mdtablefix`; those tools remain
responsible for formatting.

Snapshot JSON must be deterministic and reviewable. It must omit parser source
locations such as byte offsets, line numbers, and column numbers. It must not
include filesystem-specific absolute paths, temporary directory names, or other
nondeterministic values.

Parent test dependencies must be declared in the Makefile's `uvx --with ...`
invocation before imported in tests. Generated Rust test dependencies must be
declared in `template/Cargo.toml.jinja` so rendered projects can run their
public test gates without manual setup.

The initial ExecPlan draft is an approval artifact only. Do not implement the
mdast conversion until the user explicitly approves this plan or asks for
revisions.

## Tolerances (Exception Triggers)

Stop and ask for direction if a Markdown parser cannot preserve GitHub
Flavoured Markdown constructs that this template relies on, such as tables,
task-list items, footnotes, fenced code blocks, or inline HTML.

Stop and ask for direction if supporting true mdast JSON requires adding a
runtime dependency outside the parent Python test environment and the generated
Rust dev-dependency set. For example, do not introduce a Node, Bun, or npm
snapshot pipeline without approval.

Stop and ask for direction if the generated project `make test` or parent
repository `make test` cannot pass within one 1200 second command and cannot be
split into smaller public gates.

Stop and ask for direction before deleting existing snapshot coverage rather
than replacing it with equivalent mdast JSON assertions.

Stop and ask for direction if the implementation requires changing generated
project public commands in a way unrelated to documentation snapshot
semantics.

## Risks

Python and Rust Markdown parsers may not emit identical mdast shapes. The plan
does not require identical implementations across languages; it requires both
parent and generated-project tests to snapshot normalized JSON whose nodes
represent document semantics. The mitigation is to define a small local
normalization contract in each environment and snapshot those normalized
objects, not parser-private representations.

The existing parent snapshot test in
`tests/test_template/test_snapshots.py` covers structured tooling files rather
than documentation files. Implementation may discover separate documentation
assertions instead of a direct replacement there. The mitigation is to search
for every documentation snapshot or raw Markdown snapshot assertion before
editing, then add the minimum missing coverage if no documentation snapshot
test currently exists.

Generated projects currently contain guidance about using `insta` snapshots,
but they may not yet render documentation snapshot tests. The mitigation is to
add generated tests only where they prove this requested behaviour and to keep
them focused on documentation files under `docs/`.

Markdown parser dependency versions may change after this plan is drafted. The
mitigation is to resolve current compatible versions during implementation
using the package manager commands already used by the repository, then record
the selected versions in this plan's `Decision Log`.

Snapshot updates can accidentally bless a formatting-sensitive representation.
The mitigation is to add an explicit regression test that parses two Markdown
strings with different wrapping but the same semantics and asserts their
normalized mdast JSON is equal.

## Progress

- [x] 2026-06-28: Loaded the `leta` skill first as required for code
  navigation, then loaded the `execplans` skill for this draft and the
  `rust-router` skill for generated Rust test planning.
- [x] 2026-06-28: Confirmed the starting branch was `session/aab84371`, not
  `main`, and renamed it locally to `mdast-snapshot-assertions`.
- [x] 2026-06-28: Inspected `AGENTS.md`, `docs/developers-guide.md`,
  `template/AGENTS.md.jinja`, `tests/test_template/test_snapshots.py`, and
  current snapshot files to identify the relevant test surfaces.
- [x] 2026-06-28: Drafted this ExecPlan as a review artifact before
  implementation.
- [x] 2026-06-28: Ran `make test 2>&1 | tee
  /tmp/test-agent-template-rust-mdast-snapshot-assertions-plan.out`; result was
  50 passed and 1 skipped.
- [ ] Obtain explicit user approval for implementation.
- [ ] Establish failing parent-repository tests for normalized mdast snapshots.
- [ ] Establish failing generated-project tests for normalized mdast snapshots.
- [ ] Implement parent-repository mdast normalization and snapshot assertions.
- [ ] Implement generated Rust-project mdast normalization and snapshot
  assertions.
- [ ] Update documentation for the new semantic snapshot contract.
- [ ] Run formatting, linting, and test gates sequentially with `/tmp` logs.
- [ ] Commit the approved implementation changes after gates pass.

## Surprises & Discoveries

The parent repository has one existing syrupy snapshot file at
`tests/test_template/__snapshots__/test_snapshots.ambr`, but that snapshot
currently covers structured tooling outputs such as Cargo config, Makefile
text, and GitHub Actions workflows. The obvious documentation-related parent
tests are currently contract assertions in `tests/helpers/tooling_contracts/`
rather than Markdown document snapshots.

The generated template contains guidance in `template/AGENTS.md.jinja` that
recommends `insta` snapshots for stable output boundaries, but the rendered
template currently has no obvious generated `insta` documentation snapshot
test file.

The repository documentation already states that parent tests use `syrupy` for
generated structured file snapshots. That wording will need to remain true for
tooling snapshots while new wording explains mdast JSON snapshots for
documentation semantics.

## Decision Log

Use normalized mdast JSON as the documentation snapshot contract rather than
raw Markdown. This follows the request directly and separates semantic
assertions from formatting checks owned by `markdownlint-cli2` and
`mdtablefix`.

Keep parent and generated-project implementations local to their runtimes. The
parent repository should use a Python helper under `tests/helpers/` so pytest
tests can snapshot JSON-compatible objects with syrupy. Generated Rust projects
should use Rust dev-dependencies and `insta` JSON snapshots so `make test`
continues to be the public generated-project gate.

Treat parser source positions as formatting noise. Normalization must remove
`position`, `start`, `end`, `offset`, `line`, and `column` style fields before
snapshot comparison.

Keep raw tooling-file snapshots out of scope unless they are documentation
snapshots. Existing snapshots for `Makefile`, `.cargo/config.toml`, and
GitHub Actions workflows validate structured tooling output, not Markdown
documentation semantics.

## Implementation Plan

Begin by inventorying current snapshot and documentation assertions. Search
`tests/`, `template/`, and generated output for `snapshot`, `insta`,
`assert_snapshot`, `docs/`, and Markdown file reads. Record every in-scope
documentation snapshot assertion in this plan. If no generated-project
documentation snapshot test exists, create one as new coverage rather than
pretending an existing test was converted.

For the parent repository red step, add a helper test that proves
normalization is semantic. The test should parse two Markdown snippets that
have equivalent structure but different line wrapping or table spacing and
assert the normalized mdast JSON objects are equal. Add or update a
documentation snapshot test that renders a project, reads a representative
generated documentation file such as `docs/contents.md` or the relevant
section of `docs/repository-layout.md`, converts it to normalized mdast JSON,
and compares that JSON-compatible object with a syrupy snapshot. Run the
focused pytest command and confirm it fails for the expected reason before
implementation.

For the parent repository green step, add a Markdown-to-mdast helper under
`tests/helpers/`, using a Python dependency declared in the Makefile's
`uvx --with ...` list. The helper should expose a small API such as
`parse_markdown_semantics(markdown: str) -> object`. It should parse Markdown,
convert the parser result into plain dictionaries and lists, and recursively
remove source-position fields. Re-run the focused pytest command until it
passes, then update the syrupy snapshot only after checking that the JSON
contains meaningful headings, links, lists, tables, and code block nodes.

For the generated-project red step, add a rendered Rust test file under
`template/tests/` that reads one or more generated documentation files with
`include_str!` or `std::fs`, parses them to normalized mdast JSON, and compares
the result with `insta` JSON snapshots. Also add a unit test that parses two
formatting variants of the same Markdown and asserts their normalized JSON is
equal. Render a temporary project through the parent tests and run the
generated public test gate, expecting it to fail before the Rust helper and
snapshots exist.

For the generated-project green step, add the required Rust dev-dependencies
to `template/Cargo.toml.jinja`. Prefer a Rust Markdown parser that can produce
mdast-compatible nodes and serialize them through `serde_json`. Add a small
normalization helper inside the generated test module that removes source
positions and returns deterministic JSON. Keep snapshots scoped to
documentation semantics, for example headings and link structure in
`docs/contents.md` plus the repository tree section in
`docs/repository-layout.md`. Re-run the generated public gate until it passes.

For refactor, remove duplication between parent pytest assertions if multiple
documentation files need the same normalization. In generated Rust tests, keep
helper functions private to the test module unless another generated test
needs them. Update `docs/developers-guide.md` and the generated
`template/docs/developers-guide.md.jinja` if contributor workflow or snapshot
update instructions change.

## Validation

Run focused parent tests first, logging to `/tmp`:

```sh
uvx \
  --with pytest-copier \
  --with pyyaml \
  --with syrupy \
  --with make-parser \
  --with hypothesis \
  pytest tests/test_template -k 'snapshot or documentation' \
  2>&1 | tee /tmp/test-mdast-snapshot-assertions-focused-parent.out
```

The red run should fail because the expected normalized mdast snapshot or
helper behaviour does not exist yet. The green run should pass after the
helper and snapshots are implemented.

Render and validate a generated project through the parent test harness rather
than hand-editing rendered output. If a focused parent test is added for the
generated documentation snapshot test, run it with `tee` and confirm it invokes
the generated public test gate.

Run the full parent gate after focused checks pass:

```sh
make test 2>&1 | tee /tmp/test-agent-template-rust-mdast-snapshot-assertions.out
```

Expected result: pytest reports all tests passing. If output is truncated,
inspect the `/tmp` log before committing.

If documentation files or generated Markdown tooling instructions change, run
the generated or parent formatting and Markdown checks through their public
Makefile targets where available, sequentially and with `/tmp` logs.

## Outcomes & Retrospective

This section is intentionally empty in the draft. During implementation, record
the final parser choices, snapshot files added or changed, gates run, log
paths, commit hashes, and any lessons about parser compatibility or snapshot
scope.
