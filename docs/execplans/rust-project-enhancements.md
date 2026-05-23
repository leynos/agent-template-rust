# Import Rust Template Tooling

This ExecPlan (execution plan) is a living document. The sections
`Constraints`, `Tolerances`, `Risks`, `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work
proceeds.

Status: IN PROGRESS

## Purpose / Big Picture

The Rust Copier template should render projects that are ready for fast local
iteration and strict continuous integration. A generated project should use
Cranelift for local debug code generation, mold for local Linux linking, LLVM
linking when coverage tools need it in continuous integration, cargo-nextest
for tests, cargo-binstall metadata for binary installation, required crates.io
metadata prompts, and Whitaker linting with the same cache pattern used by
`../dear-diary`.

The observable success condition is that running this repository's template
tests renders both library and application projects, then the generated
projects pass their public gates through `make all`. The generated project
must include a disposable stub Rust test so nextest has at least one test until
real functionality replaces it.

## Constraints

Changes must obey the prompt and the scoped `template/AGENTS.md` guidance for
all files under `template/`. The branch is `rust-project-enhancements`, and the
plan file is `docs/execplans/rust-project-enhancements.md` as required by the
repository instruction.

Use the current worktree and the sibling repositories as authoritative source
inputs. The relevant imports are `../dear-diary/.cargo/config.toml`,
`../dear-diary/Makefile`, `../dear-diary/.github/workflows/ci.yml`,
`../dear-diary/Cargo.toml`, and the pytest-copier approach in
`../agent-template-python/tests/test_template.py`.

Prefer Makefile targets over direct commands. Run long gates with `tee` into
`/tmp` logs. Do not run format, lint, or test commands in parallel. Commit
after each completed and gated change. Use `coderabbit review --agent` after
major milestones and clear concerns before moving on.

GitHub Actions versions imported from `../dear-diary` must be replaced by
current SHAs sourced through Firecrawl-assisted lookup before completion.

## Tolerances

Stop and ask for direction if the generated template cannot pass `make all`
without removing one of the requested tools. Stop if `coderabbit review
--agent` reports a concern that conflicts with the user's explicit
requirements. Stop if any gate requires more than 1200 seconds as a single
command and cannot be split into smaller public targets. Stop if disk space or
`/tmp` fills up.

## Risks

Some generated project gates may download Rust components or install tools,
which can be slow and may contend for the shared Cargo cache. The mitigation is
to run gates sequentially and let Cargo's package-cache lock serialize access.

The template currently uses strict Clippy and rustdoc lints. Stub modules and
tests must be documented carefully so they satisfy lints while clearly telling
project owners to delete them once real code exists.

Pinned GitHub Action SHAs drift over time. The mitigation is to resolve the
current default-branch commit for each action repository during implementation
and record the resulting pins in the plan and pull request validation notes.

## Progress

- [x] 2026-05-23: Confirmed branch `rust-project-enhancements` and clean
  worktree.
- [x] 2026-05-23: Loaded `leta`, `execplans`, `grepai`, `firecrawl-mcp`, and
  `pr-creation` skills because the task requires Rust template work, a living
  plan, semantic search, Firecrawl-sourced action pins, and a final PR.
- [x] 2026-05-23: Inspected `../dear-diary` build, linker, CI, and metadata
  patterns.
- [x] 2026-05-23: Inspected `../agent-template-python` pytest-copier template
  testing approach.
- [ ] Import generated-project Rust toolchain, linker, nextest, Whitaker,
  cargo-binstall, metadata, and CI contracts.
- [ ] Replace imported GitHub Action version pins with current SHAs sourced
  through Firecrawl-assisted lookup.
- [ ] Extend pytest-copier tests so rendered projects pass formatting, linting,
  nextest, and generated Makefile checks through public targets.
- [ ] Run `coderabbit review --agent` after major milestones and resolve
  concerns.
- [ ] Gate, commit, push, and create a draft pull request.

## Surprises & Discoveries

There is no root `AGENTS.md` file in this repository. The in-scope project
guidance for generated template files is `template/AGENTS.md`.

GrepAI's `Projects` workspace is available, but `agent-template-rust` is not
indexed there. GrepAI can still help with indexed sibling projects, and exact
file reads are used for this template repository.

The branch currently points at the same commit as `main`, so the requested
implementation has not yet been committed.

## Decision Log

Use `cargo nextest run` as the generated project's test target and keep
coverage delegated to the shared `generate-coverage` action in CI. This matches
the requested nextest adoption while retaining the dear-diary coverage action
shape that can fall back away from mold when llvm-cov requires LLVM linking.

Use a generated `.cargo/config.toml` for local debug Cranelift and Linux mold
linking. In CI, set `CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER=clang` and
`RUSTFLAGS=-C link-arg=-fuse-ld=lld` only for the coverage step so llvm-cov is
not coupled to mold.

Validate generated projects through pytest-copier by invoking the generated
public `make all` target rather than stitching together private commands from
the parent repository.

## Outcomes & Retrospective

No final outcome yet. Completion requires current evidence for every requested
template feature, passing parent-template tests, `coderabbit review --agent`
with concerns resolved, committed changes, and a draft pull request.
