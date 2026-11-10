# Port missing Catnap build, validation, and delivery tooling without Netsuke

This ExecPlan is a living document. The sections `Progress`,
`Surprises & discoveries`, and `Decision log` must be updated as work proceeds.
It follows the repository's ExecPlan conventions and is self-contained: a
reader needs only this worktree and this file.

## Purpose and observable outcome

The parent template repository and every project rendered from it must expose
the reusable build, validation, and delivery behaviour that exists in Catnap,
without importing Netsuke, a Netsukefile, Ninja, or any Netsuke-specific
execution dependency. After the change, a contributor can run public Make
targets that lint YAML and GitHub Actions, preflight and explicitly install the
pinned build tools, format and verify Git-aware Markdown, run bounded tests,
check workflow contracts, and dispatch a safe release dry run.

The observable success condition is that the parent `make test` suite and the
relevant parent gates pass, and that rendered library and application projects
pass their public `make` gates, including the new targets, under both Polonius
settings.

## Conformance basis

- Source issue: <https://github.com/leynos/agent-template-rust/issues/164>.
- Catnap inventory revision:
  `f455f47c21747da3c0da7b43f85b93c0eac3ef82`.
- Template baseline:
  `bf6f9ae8366d7d4020b21faf23be89debaebdd76` (default branch) and
  `c3bd9b8253cf1471c7f296789d220b80de3ffccb` (guidance branch).
- Related issues whose scope overlaps but whose state is not evidence of
  absence: #122 (shared clang/lld/mold provisioning), #92 (Act linker
  provisioning), #75 (undeclared `mbake` command), #160 (contract-test quality).
- The repository's `AGENTS.md` and the user's global agent instructions are
  hard constraints.
- No Terms of Reference or technical design revision exists for this
  repository; this ExecPlan is the design record.

## Constraints

- Do not add Netsuke, a Netsukefile, or Ninja as an execution dependency.
- Translate behaviour into the existing Makefile, Copier template,
  pytest-copier tests, and GitHub Actions entrypoints.
- Preserve full action SHA pins. Do not replace a full SHA with a mutable tag.
- Rendered workflows, not Jinja source, are linted as YAML.
- The estate `.yamllint-estate.yml` is copied byte-for-byte; the repository
  `.yamllint.yml` may only extend it.
- Installation of build tools stays explicit. Preflight checks must not modify
  the host and must not auto-install.
- Coverage, Whitaker, and release routes stay free of incompatible development
  flags. Both Polonius configurations and all existing flag-override paths must
  survive.
- Do not duplicate parent PR automation workflows that already exist.
- Library renders have no application release workflow.
- A fresh generated project without a CodeScene token must remain green.
- Existing audit, mutation, spelling, Markdown, Mermaid, nextest, doctest, and
  Act facilities are retained.

## Tolerances (exception triggers)

Stop and escalate if a requirement cannot be met without a new tool that the
repository cannot provision reproducibly, if a shared action lacks a required
input or capability at a verified full SHA, if a generated stable release Cargo
cannot parse the generated configuration, or if preserving an existing
behaviour and satisfying the issue would require contradicting the issue's
explicit instruction.

## Risks

- The Copier snapshot file and the parent contract tests encode many existing
  textual details. Template edits will require snapshot and assertion updates.
- Shared-action revisions move independently. A newer pin may have different
  inputs, so each action must be verified before use.
- The default nightly pin may not support `[unstable] embed-metadata`. This must
  be verified against a real toolchain rather than assumed.
- Rendering every combination is expensive. Tests select representative
  library/application, Polonius on/off, and Linux/non-Linux cases.
- This repository is a template, not a generated application: certain release
  and UI behaviour can only be proved by rendering and by event-table
  evaluation, not by executing a real tagged release.

## Inventory dispositions

The disposition for each row is recorded here and rechecked against the current
branches before implementation.

- Strict YAML/workflow linting and shared configuration: implemented in
  milestone M1.
- Build-tool installer/checker scripts and mold release pins: implemented in
  M2.
- Development-build and footprint configuration: implemented in M2.
- Git-aware Markdown formatting and validation: implemented in M3.
- Nextest timeouts, nested-Cargo scheduling, explicit UI test lane:
  implemented in M3.
- Shared CV-005 executable workflow contracts: implemented in M4.
- Shared Whitaker installer action and rust-analyzer setup: implemented in M4.
- Dependency-update policy: implemented in M5.
- Release matrix execution and dry-run tooling: implemented in M5.
- PR automation helpers: already present in the parent; generated callers
  added in M5 only where they do not duplicate parent workflows.
- Excluded: Netsuke, Netsukefile parsing/execution, Ninja, Catnap runtime
  dependencies, product fixtures, release names, and host-global
  debugger/system inventories (tracked by dev-env-rocky#357).

## Milestones

### M1: YAML, GitHub Actions, and shell lint gates

End state: the parent and rendered projects expose `lint-yaml`, `lint-actions`,
and (rendered) `lint-shell`; `lint` runs them; CI provisions the shared
`install-yaml-lint` action before the gates; real-tool and selection tests
exist.

Acceptance evidence: parent `make lint-yaml`, `make lint-actions`, and the new
pytest cases pass; a malformed staged YAML file and an invalid rendered
workflow are rejected; untracked and Jinja files are not linted.

### M2: Build tools, preflight, and compiler routes

End state: `scripts/build-tools-common.sh`, `scripts/install-build-tools.sh`,
`scripts/check-build-tools.sh`, and `tools/mold/{VERSION,SHA256SUMS}` exist in
the template; Make exposes `install-build-tools`, `install-cranelift`,
`check-build-tools`, `check-rust-toolchain`, and `check-coverage-tools`;
Cranelift and `-Zthreads=8` route through rustflags; coverage, Whitaker, and
release routes stay distinct; development footprint settings are present.

Acceptance evidence: installer/checker tests with fake and real tools;
effective-flag capture through a logging `RUSTC_WRAPPER`;
`cargo +stable metadata` parses the rendered configuration.

### M3: Markdown formatting and bounded test execution

End state: rendered `fmt` and `check-fmt` use mdtablefix with the parent's
flags and Git-aware selection; rendered `make test-ui` discovers compile-time
test targets and exits cleanly when none exist; `.config/nextest.toml` bounds
runs and serializes compiler-spawning tests.

Acceptance evidence: rendered Markdown selection tests, nextest configuration
tests, `test-ui` success and no-target cases, and the Cargo fallback test.

### M4: CV-005 contracts and shared Whitaker installation

End state: a `github_repository` answer is validated and rendered into
`.github/cv005.toml`; `make test-workflow-contracts` runs the pinned shared
checker; generated CI uses the shared `install-whitaker` action; the bespoke
publisher checker is retired.

Acceptance evidence: the shared checker passes over four renders; negative
mutations are rejected; token-absent projects stay green.

### M5: Dependency policy, PR automation, and release dry run

End state: rendered Dependabot configuration groups updates, applies cooldowns,
and tracks `rust-toolchain`; generated PR automation callers use full-SHA pins
and safe inputs; the application release matrix uses native macOS and cross
builders, disables fail-fast, supports a dry run, and never publishes from a
branch dispatch.

Acceptance evidence: policy and permission tests, input-validation tests,
release matrix relationship tests, and an event-table test of the publication
guard.

### M6: Documentation, snapshots, and executed validation

End state: parent and rendered guidance documents the implemented commands,
prerequisites, effective flags, platforms, and deliberate exceptions; snapshots
are regenerated and reviewed; executed evidence and limitations are recorded
here.

Acceptance evidence: parent gates, rendered public gates, shared workflow
contracts, and (where the environment allows) Act and a scratch release dry
run; recorded skips and platform limits.

## Verification plan

- M1 invariant: every tracked YAML file outside the agreed ignores parses under
  strict yamllint, and every rendered workflow passes actionlint. Verification:
  real-tool selection tests (staged/untracked/Jinja), defect-rejection tests,
  and four-render lint runs. Non-vacuity: a deliberately malformed file and a
  deliberately invalid workflow must fail.
- M2 invariants: checks never install; mold archives are checksum-verified;
  every RUSTFLAGS route preserves the selected Polonius state; coverage,
  Whitaker, and release routes contain no Cranelift or threads flag; stable
  Cargo parses the rendered configuration. Verification: fake-tool harnesses,
  logging Cargo/Whitaker stubs at the `RUSTFLAGS` boundary, and
  `cargo +stable metadata`. Non-vacuity: a corrupted checksum and a missing
  component must fail the checks.
- M3 invariants: Markdown selection includes tracked and untracked
  non-ignored files only; nextest bounds exist per test, per run, and per
  compiler-spawning group; `test-ui` selects only compile-time targets.
  Verification: rendered project runs and configuration parsing. Non-vacuity:
  ignored Markdown stays unformatted and a failing `compile_*` test fails
  `test-ui`.
- M4 invariants: the checker configuration names the rendered repository and
  the same coverage selection in every lane; the token is absent from
  environments and only passed to the upload action. Verification: shared
  checker over four renders and negative mutations. Non-vacuity: a mutated
  workflow must make the checker fail.
- M5 invariants: every action reference is a 40-character SHA; dispatch inputs
  are validated before use; publication requires a tag ref and explicit
  non-dry-run. Verification: parsing and event-table tests. Non-vacuity: a
  branch dispatch with `dry-run: false` must not publish.
- M6: execute the parent and rendered gates; record commands and results. Text
  assertions alone are not recorded as proof of workflow execution.

## Progress

- [x] 2026-11-09: Renamed branch and set the Lody session title.
- [x] 2026-11-09: Verified tool availability and Cargo configuration
  compatibility (stable 1.99 rejects `[profile.dev] codegen-backend`; nightly
  2026-11-06 supports `embed-metadata`, Cranelift, rust-analyzer, and
  `-Zpolonius=next`).
- [x] 2026-11-09: Copied the estate yamllint base and added the extending
  overlay.
- [x] 2026-11-09: M1 implementation and tests. Parent `lint-yaml` and
  `lint-actions` targets, the estate/overlay configuration, and the pytest
  selection tests are in place; the previously reported trailing-space defect in
  `template/.github/dependabot.yml` was fixed.
- [x] 2026-11-09: M2 implementation. Added `scripts/build-tools-common.sh`,
  `scripts/install-build-tools.sh`, `scripts/check-build-tools.sh` and
  `tools/mold/{VERSION,SHA256SUMS}` to the template; exposed the five install
  and check targets; routed Cranelift, `-Zthreads=8` and mold through
  `[build]`/Linux `cfg` rustflags and the composed Make routes; added the
  development footprint profile; wired contract assertions for the dev profile
  and the new targets.
- [x] 2026-11-09: M2 tests. `tests/test_template/test_build_tools.py` exercises
  the checker and installer against a PATH-limited fake toolchain and a fake
  mold release (missing toolchain, missing component, coverage-only mode,
  corrupted and matching checksums, Cranelift-only install), asserts the
  rendered assets and self-resolving pins, proves stable
  `cargo +stable metadata` parses both NLL and Polonius renders, and records
  the flags every Make route sets through a logging Cargo and Whitaker stub.
  Parent CI and act-validation render the template's default project before
  tests so rustup installs the single-source pinned toolchain.
- [x] 2026-11-09: M2 focused evidence. `tests/test_template/test_build_tools.py`
  passes 13 tests; `ruff check tests/` reports no issues; `mypy tests/` reports
  no issues across 38 files; `interrogate` reports 100% for the new module;
  parent `make lint-yaml`, `make lint-actions` and `make spelling` exit 0.
- [x] 2026-11-09: M3 implementation. Rendered `fmt` and `check-fmt` now call
  mdtablefix with the parent's Git-aware selection and rule set; the generated
  `.config/nextest.toml` bounds runs with a slow timeout, a global timeout and
  a serialized `nested-cargo` group for `binary(compile_*)`; `make test-ui`
  discovers `tests/compile_*.rs`, runs them in one shell guard, and reports an
  intentional no-op when none exist; both generated CI workflows install the
  pinned mdtablefix action and run `make test-ui` before coverage.
- [x] 2026-11-09: M3 tests. `tests/test_template/test_markdown_tooling.py`
  proves tracked and untracked Markdown are reformatted, ignored Markdown is
  untouched, and the parent Act workflow provisions mdtablefix before
  `make test`. `tests/test_template/test_test_lane.py` proves the nextest
  bounds, the no-op and failing UI lanes, the `TEST_CMD=test` fallback, and the
  workflow ordering. `tests/helpers/tooling_contracts/makefile.py` asserts the
  new targets, mdtablefix variables and UI-lane command.
- [x] 2026-11-09: M3 focused evidence. Both the default and
  `enable_polonius=true` renders are mdtablefix fixed points (12 and 13 files
  unchanged); `make check-fmt` and `make test-ui` exit 0 in both rendered
  projects.
- [x] 2026-11-09: M4 implementation and tests. `github_repository` is a
  validated Copier answer rendered into `.github/cv005.toml`; the rendered
  Makefile exposes `test-workflow-contracts` running the pinned shared CV-005
  checker through `uv tool run`; generated CI installs Whitaker through the
  shared action; the bespoke publisher checker and its tests are retired; and
  `tests/test_template/test_workflow_contracts.py` proves the checker passes
  over four renders and rejects a mutated publisher placement. A
  contract-helper defect was fixed: the assertion now looks for
  `$(CV005_CONTRACTS)` because the executable name never appears literally in
  the rendered Makefile.
- [x] 2026-11-09: M5 implementation and tests. The rendered Dependabot policy
  groups shared actions and routine GitHub Action updates, groups Cargo minor
  and patch updates, cools every fresh release for seven days, and tracks
  `rust-toolchain`; generated callers for dependabot-automerge and the delayed
  pull-request comment use full-SHA pins and validate dispatch input in the
  shell; the application release workflow builds native macOS legs with Cargo
  and the other legs with `cross`, disables fail-fast, uses stable Cargo with
  cleared `RUSTFLAGS`, supports a dry-run dispatch, and publishes only from a
  tag ref. `tests/test_template/test_delivery_tooling.py` covers the policy,
  permissions, input validation, matrix relationships, and the publication
  guard table with a weakened-guard non-vacuity check.
- [x] 2026-11-09: M5 focused evidence. The delivery, snapshot, and workflow
  contract suites pass (`16`, `1`, and `11` tests respectively); the cheap
  Polonius contract tests pass (`10`). The generated-project and property cases
  are executed in the final full-gate run recorded below.
- [x] 2026-11-09: M6 documentation. Parent and generated guides now describe the
  YAML, Actions, and shell gates, the build-tool installers and read-only
  checkers, nextest bounds, the explicit UI lane, CV-005 workflow contracts,
  the release dry-run and native macOS matrix, and the grouped Dependabot
  policy. The Polonius flag-flow figure and ADR-004 were corrected so the
  application release workflow is the documented stable-Cargo exception.
  `make check-fmt`, `make lint`, `make typecheck`, and `make spelling` pass.
- [x] 2026-11-09: M6 spelling and newline corrections. The shared gate enforces
  Oxford `-ize` forms and `artefact` in prose; the release template had lost
  its final newline during the port, which strict yamllint rejects. Both are
  fixed, upstream `artifact` tokens stay covered by narrow local patterns, and
  the snapshot is refreshed.
- [x] 2026-11-09/10: M6 executed validation. The full parent suite collected 201
  tests and finished with 199 passed, 2 expected `act` skips, and 0 failures.
  The suite includes the generated `make all` runs in four renders, the shared
  CV-005 workflow-contract checks, the cheap and expensive Polonius flag
  invariants, and the delivery tooling contracts. The canonical single-process
  run exceeded the monitoring limits under heavy host contention, so the suite
  completed across bounded file-scoped runs against the same clean HEAD; every
  test is accounted for and no failure was masked. `make check-fmt`,
  `make lint`, `make typecheck`, and `make spelling` also pass on that HEAD.
- [x] 2026-11-10: Resolved the first CodeRabbit review's findings. Both
  mdtablefix callers pin `version: "0.6.1"`; the delayed-comment delay is
  parsed in base ten and covers a leading-zero case; the release rule's
  prerequisites and the preflight assertions use whole-line parsing; the
  generated lint recipe puts the installed build tools on `PATH` for
  `cargo doc` and `cargo clippy`; the generated developer guide states the real
  installer prerequisites; the generated user guide documents restricting the
  `codescene` environment to `main`; and the gate-level Mermaid figure moved
  from the parent README to `docs/testing.md`, where the README links to it.
- [x] 2026-11-10: Post-review gate evidence at commit `a4dea59`. The parent
  `make check-fmt`, `make lint`, `make typecheck`, and `make spelling` pass.
  The full suite collects 202 tests; the canonical run was stopped at the
  2-hour harness limit after 132 tests with no failures, and bounded
  file-scoped runs completed the remainder against the same HEAD. Every file is
  accounted for: 200 passed and 2 expected `act` skips, with no failures or
  errors. A rendered app project passes `check-fmt`, `lint-yaml`,
  `lint-actions`, `lint-shell`, `test-workflow-contracts`, `spelling`, and
  `make test`; a rendered lib project passes `check-fmt` and the workflow
  contracts. The CodeRabbit re-review is the remaining step.
- [x] 2026-11-10: Resolved the second and third CodeRabbit reviews at commits
  `69975fc` and `fc454eb`. The generated AGENTS.md `make fmt` guidance now sits
  with the `make check-fmt` description; the delayed-comment wait reads its
  delay from step output through `env` rather than interpolating it into
  `run:`; and the generated user guide again lists `make markdownlint`.
- [x] 2026-11-10: Resolved the fourth CodeRabbit review. The delayed-comment
  job caps accepted delays at 300 minutes and sets `timeout-minutes: 330`; the
  release workflow adds native targets with
  `rustup target add --toolchain stable`; the Polonius contract assertions all
  carry failure messages; and the 682-line build-tool test module was split.
  Sandbox fixtures moved to `tests/helpers/build_tool_sandbox.py`, the
  flag-route and rendered-asset tests to
  `tests/test_template/test_build_tool_flags.py`, and the delivery tests were
  split into `tests/helpers/delivery_workflows.py` plus five focused test
  modules, so every module is now under the repository's 400-line limit. Ruff,
  mypy, `interrogate`, `make check-fmt`, `make lint`, `make typecheck`, and
  `make spelling` pass on the split modules, and the 13 build-tool tests pass.
- [x] 2026-11-10: Resolved the fifth CodeRabbit review. `github_repository` now
  defaults to the `owner/name` part of `repository_url` when that answer is a
  `github.com` URL, so an adopter who changes only the repository URL still
  renders a real repository into `.github/cv005.toml`; other URLs keep the
  `example/<package_name>` placeholder. Three parametrized cases prove the
  derivation, the `.git` suffix handling, and the fallback. The review's second
  finding claimed Dependabot cannot apply a cooldown to `rust-toolchain`; the
  GitHub options reference marks both cooldown columns as supported for that
  ecosystem, so the guide is accurate and required no change. The full parent
  suite reports 207 passed and 2 expected `act` skips with no failures, and the
  snapshot is unchanged because the default URL derives the same
  `example/<package_name>` value. `make check-fmt`, `make lint`,
  `make typecheck`, and `make spelling` pass.
- [x] 2026-11-10: Resolved the sixth CodeRabbit review. The nextest comment now
  states that `terminate-after` bounds a test by period multiplied by the count
  whatever output it produces; the parent developer guide names the five real
  delivery test modules; the Makefile contracts assert the UI target list and
  the `tests/compile_*.rs` discovery separately; the mdtablefix pins are
  matched by a full-SHA regex instead of a literal digest; the mold installer
  and checker tests skip on a non-Linux host; the release workflow assertions
  are extracted into three helpers; and the publication guard evaluator uses a
  dispatch table with a dedicated `ast.Expression` handler instead of a
  nine-return `match`. Focused tests pass, and `make check-fmt`, `make lint`,
  `make typecheck`, and `make spelling` pass before the full suite. One full
  suite run then reported 206 passed, 1 failed, and 2 expected `act` skips: the
  `unsafe-code` lint-rejection case saw `make lint` fail without emitting the
  named diagnostic while the host's compile queue was saturated. The same case
  passed in isolation and on the next full run, which reported 207 passed and 2
  expected `act` skips with no failures.
- [x] 2026-11-10: Rebased onto `origin/main` at `f9f8862` (the shared-actions
  group bump, #167). The replay of all 14 branch commits was conflict-free; the
  only range change is the parent CI install-whitaker pin, which now carries
  main's bumped SHA. The template callers and the parent Act mdtablefix step
  were updated to the same SHA, the decision was recorded below, and the parent
  gates plus the full suite were re-run against the rebased head.
- [x] 2026-11-10: Post-rebase validation and publication. On the rebased head
  `fc15131`, `make check-fmt`, `make lint`, `make typecheck`, and
  `make spelling` pass, and the full parent suite reports 207 passed, 2 expected
  `act` skips, and 0 failures in 583.10s. The branch was force-pushed with a
  lease bound to the previously recorded remote head `c8fd955`, the tracking
  ref was refreshed, and the remote head now equals `fc15131`. On that head the
  pull request's `build-test` (4m36s) and `act-validation` (6m48s) checks pass.

## Surprises & discoveries

- Stable Cargo 1.99 fails to parse `[profile.dev] codegen-backend` with
  "feature `codegen-backend` is required", so the existing template
  configuration cannot be used by a stable release build. Catnap's
  rustflags-based Cranelift routing fixes this.
- Stable Cargo accepts `[unstable] embed-metadata = false` without error.
  Nightly 2025-06-10 reports it as an unused key; nightly 2026-11-06 accepts
  it. The key therefore needs a date gate.
- `-Zcodegen-backend=cranelift` works from `build.rustflags` without an
  `[unstable] codegen-backend = true` entry on nightly 2026-11-06.
- The parent repository currently has one genuine strict-yamllint finding: a
  trailing-space line in `template/.github/dependabot.yml`.
- `make lint` now runs the YAML, workflow and shell gates before Cargo and
  Whitaker. Tests that isolate Whitaker resolution must therefore stub `git`,
  `xargs` and `uname` as well, and replace the capability preflight, because
  the restricted PATH deliberately hides the real toolchain.
- Removing `[profile.dev] codegen-backend` while adding a `[profile.dev]` table
  for the footprint does not wake the old stable-parsing failure, because the
  remaining keys (`incremental`, `debug`) are stable Cargo keys.
- The generated `test` target exports `RUSTFLAGS` so `cargo test --doc`
  inherits the same dev flags as the integration run; the release recipe still
  assigns an empty `RUSTFLAGS` and therefore drops inherited development flags
  deliberately.
- mdtablefix's `--wrap` reflows whole paragraphs to 80 columns and will absorb
  a Jinja control tag into the following prose when run on a template source.
  Formatting therefore has to be ported from the rendered output. A template
  Markdown source is safe to format directly only where its text is identical
  to the render: standalone documents such as `polonius.md`, and text that sits
  wholly inside a conditional block, which is absent in the other render.
- Rendered Markdown must be a formatting fixed point in every supported
  combination of answers. Variable-length substitutions in flowing prose
  (`{{ project_name }}`) made wrapping depend on the caller's project name, so
  those substitutions were removed from the affected paragraphs. The
  `polonius.md` verification table still substitutes `rust_nightly_date`, but
  the column widths come from fixed cells, and the substituted date is shorter
  than the placeholder, so the rendered table is stable.
- The first M3 run exposed that a checked-in `binary(compile_*)` nextest
  override breaks `make test` in a project with no matching binary: nextest
  validates the filter in every profile and exits 96. The override moved to a
  `ui` profile guarded by `all()`.
- `test-ui` keeps its guard and its run in one continued shell recipe. A plain
  `exit 0` on an earlier recipe line would only end that line, and the later
  line would still run nextest with an empty target list.
- `make` reports a failed recipe as its own exit status `2`, so a Make target
  that wraps a checker cannot distinguish the checker's violation status from
  its read-fault status. Tests and the plan assert "non-zero plus the specific
  clause" rather than a particular status code.
- PyYAML parses an unquoted top-level `on:` key as the boolean `True`, so any
  test that reads workflow triggers must fall back from `"on"` to `True`.
- Catnap's release workflow names its upload directory `artifacts`; the existing
  template used the same spelling, so the port keeps it and the tests name the
  step `Prepare artifact`. The shared spelling gate treats those as upstream
  tokens through narrow `typos.local.toml` patterns, while release-workflow
  prose uses the Oxford `artefact` spelling.
- The shared spelling gate enforces Oxford `-ize` forms (`serialized`,
  `initialized`, `normalized`) rather than British `-ise`, and rejects
  `artifact` in prose. New documentation and comments must use the Oxford
  forms; only upstream action and feature names stay exempt.
- The release workflow template lost its final newline when the M5 draft was
  written. Copier preserved the missing newline, so only the rendered-project
  `make lint-yaml` case exposed it. Always check the rendered text, not only
  the template source, for the strict yamllint end-of-file rule.
- Catnap's `binary(compile_*)` nextest overrides cannot be copied literally.
  nextest validates every `binary(...)` filter against the binaries it finds,
  in every profile, before running anything; a generated project with no
  `tests/compile_*.rs` therefore fails `cargo nextest run` outright (exit 96).
  The generated configuration therefore gives the default profile only the
  bounded timeouts and puts the serialized `nested-cargo` group and the longer
  timeout in a `ui` profile whose override filters on `all()`. `make test-ui`
  selects that profile through `UI_TEST_CMD`, and it only invokes the runner
  when the target list is non-empty. `cargo test` has no profiles, so the lane
  falls back to the plain runner for that path.
- A generated-project lint-rejection test can fail for the wrong reason when the
  host's compile queue is saturated. `make lint` still exits non-zero, but the
  failure is a compile-admission or cache fault rather than the injected lint,
  so the expected diagnostic never appears. The case passed in isolation and on
  the next full run; the test's first assertion (non-zero exit) cannot
  distinguish the two causes. Treat a lone failure of this shape under heavy
  contention as environmental, and re-run before changing the template.

## Decision log

- Use Catnap's `.yamllint-estate.yml` byte-for-byte and a two-line extending
  overlay, as the issue requires.
- Keep tool installation explicit; check targets remain read-only.
- Route Cranelift and threads through Cargo rustflags rather than
  `[profile.dev] codegen-backend`, because that preserves stable release
  parsing and matches Catnap's accepted approach.
- Bump the default `rust_nightly_date` to `2026-11-06` only because it was
  verified to ship every required component and flag; date-gate
  `embed-metadata` so a user-selected older nightly still renders.
- Reuse the existing shared-action pins where they provide the required
  capability, and advance to a verified full SHA only for actions the template
  does not yet use.
- The parent keeps its existing PR automation; generated projects receive
  callers only where the parent has none.
- Capture effective rustflags with logging `CARGO` and `WHITAKER` stubs rather
  than with a `RUSTC_WRAPPER`. The host's compile-admission rules forbid
  overriding or unsetting `RUSTC_WRAPPER`, and every Make route passes its
  flags to Cargo through `RUSTFLAGS`, so the Cargo boundary observes exactly
  the values that would reach rustc. The verification plan's "logging
  `RUSTC_WRAPPER`" wording is amended accordingly.
- Keep `RUSTUP_AUTO_INSTALL=0` in the checker rather than passing
  `--no-install`, so rustup's own default cannot install a toolchain even if a
  future rustup changes flag names.
- M3 will reuse the parent's mdtablefix invocation exactly
  (`--git --include-untracked` selection and
  `--wrap --renumber --breaks --ellipsis --fences` rules) and pin version 0.6.1
  in every lane, because `--check` and Git-aware selection first shipped
  together.
- M3's UI lane selects `tests/compile_*.rs` integration targets by file name.
  The template cannot assume a Catnap-style `tests/ui.rs` or a `trybuild`
  dependency, so the target discovers the convention, runs every match, and
  reports an intentional no-op when a project has none. The `ui` nextest
  profile gives every target the lane runs a single nested-Cargo slot and a
  longer timeout, because a `binary(...)` filter would be rejected in projects
  without compile-time tests.
- M3 runs the UI lane before coverage in both generated CI workflows, so
  compile-time contract tests are not instrumented and do not compete with the
  coverage build for the Cargo cache.
- `test-ui` stays out of the `all` aggregate. The lane is invoked explicitly by
  the CI and coverage workflows before coverage, which keeps ad hoc local
  `make all` inexpensive while still gating the generated project.
- The mdtablefix CI action is pinned at the same full SHA in the parent Act
  workflow and both generated project workflows, matching the estate's full-SHA
  pin policy.
- M4 runs the shared CV-005 checker through `uv tool run` from one pinned
  `leynos/shared-actions` revision instead of keeping a repository copy of the
  rules. The Makefile URL escapes the fragment separator as `\#`; an unescaped
  `#` starts a Make comment and truncates the command.
- M4 replaces the bespoke CodeScene publisher checker with the shared checker
  run over four renders. The negative mutation test asserts an exit other than
  zero plus the `environment.placement` clause, because `make` reports a
  non-zero recipe as its own exit status 2 and cannot distinguish the checker's
  violation status 1 from its read-fault status 2.
- M5 keeps every generated release build on stable Cargo, clears `RUSTFLAGS`
  on the build steps, and omits the setup-rust `rustflags` input. The release
  workflow therefore contains no Polonius, Cranelift, or threads flags even
  when the project's development toolchain is the Polonius nightly.
- M5 validates the delayed-comment dispatch inputs in the shell and passes
  them to the comment action as inputs. A dispatch is free-form text, so placing
  `inputs.message` or an unvalidated number directly in a `run:` step would
  allow command substitution.
- M5 adds generated callers for the parent's existing PR automation rather
  than duplicating their policy: the reusable automerge workflow stays pinned
  to a full SHA and receives only the permissions it needs, including
  `id-token: write` for OIDC-based reusable-workflow introspection.
- M5 keeps the generated Dependabot policy product-neutral: it groups shared
  actions and routine GitHub Action updates, groups Cargo minor and patch
  updates, and tracks `rust-toolchain`, without porting Catnap's product crate
  group.
- The generated lint recipe prefixes `cargo doc` and `cargo clippy` with
  `PATH="$(BUILD_TOOLS_PATH)"`, because both receive `DEV_RUST_FLAGS`, whose
  Linux `-fuse-ld=mold` argument needs the installed linker on `PATH` just as
  the test and build recipes do. AGENTS.md's excerpt, the snapshot, and the
  Makefile contracts assert the prefixed forms.
- The CodeScene environment comment no longer claims GitHub refuses a branch
  dispatch on its own. The template cannot create environment protection rules,
  so the generated user guide tells the adopter to restrict `codescene` to
  `main`; the workflow's upload guard remains a second, in-workflow layer.
- The parent README keeps only a signpost to the generated quality-gate flow.
  The gate-level Mermaid figure lives in `docs/testing.md`, so the README stays
  at the template's core functionality rather than reproducing target internals.
- The delayed-comment dispatch bounds `delay_minutes` at 300 and gives the job
  a 330-minute timeout. A GitHub job may run for at most six hours, so an
  unbounded delay input could occupy a runner indefinitely; bounding the input
  keeps the accepted worst case inside the job limit and gives the extra 30
  minutes to validation and the comment step.
- The release workflow adds native targets with
  `rustup target add --toolchain stable`, because setup-rust selects stable
  while `rustup` may already have another default toolchain. Naming the
  toolchain keeps the added target and the subsequent `cargo +stable build` in
  agreement.
- Build-tool and delivery test modules stay under the repository's 400-line
  limit by moving reusable sandbox and workflow parsing into `tests/helpers/`.
  Helpers take public names; test modules keep only their scenario-specific
  stubs and assertions.
- The `github_repository` answer derives `owner/name` from a `github.com`
  `repository_url` and falls back to `example/<package_name>` otherwise. The
  existing default `repository_url` already yields the placeholder value, so
  default renders and their snapshots do not move, while an adopter who changes
  only the URL gets a real repository in the contract configuration. Trailing
  slashes and a `.git` suffix are stripped from the derived name.
- The claim that Dependabot cannot cool down `rust-toolchain` updates was
  checked against GitHub's Dependabot options reference, whose compatibility
  table marks both the default-days and SemVer-bump cooldown columns as
  supported for the Rust toolchain ecosystem. The generated guide keeps its
  seven-day cooldown sentence, and the reviewer's finding was not actioned
  because current vendor documentation contradicts it.
- The publication guard evaluator dispatches on the exact node type and gives
  `ast.Expression` its own handler that recurses into `node.body`. Mapping that
  node to `_evaluate_expression` itself would re-dispatch the same node
  forever; the first attempt did exactly that and the focused test caught the
  recursion. `ast.UnaryOp` accepts only `ast.Not` and raises `TypeError` for
  any other operator, which satisfies Ruff's TRY004 rule for an invalid node
  type.
- The branch was rebased onto `origin/main` at `f9f8862`, which had bumped the
  shared-actions action and reusable-workflow pins from `38905b4` to `0eabb6b`
  in the parent workflows. The template's new mdtablefix, Whitaker and
  dependabot-automerge callers, and the parent Act mdtablefix step, adopt the
  bumped revision so both trees name one verified shared-actions commit. The
  CV005 package pin (`CV005_CONTRACTS_REF`) stays at `38905b4`: the Dependabot
  bump covers only action references, and the package pin is a separately
  exercised dependency whose compatibility the contract tests verify.

## Outcomes & retrospective

Every Catnap capability named in the issue is now available through the
existing Makefile, Copier template, pytest-copier tests, and GitHub Actions; no
Netsuke, Netsukefile, or Ninja dependency was introduced.

Delivered behaviour:

- The parent and generated projects run strict yamllint over every tracked YAML
  file (template `.jinja` sources excluded), actionlint with shellcheck over
  the workflows GitHub actually executes, and shellcheck over tracked scripts.
  The estate yamllint base is copied unchanged and the local overlay adds
  ignores only.
- The template ships read-only tool checkers and an explicit installer for the
  pinned `mold` release (checksum-verified against `tools/mold/SHA256SUMS`) and
  the Cranelift component. Development builds route Cranelift, `-Zthreads=8`,
  and Linux `mold` linking through Cargo rustflags and a composed Make
  `DEV_RUST_FLAGS`, so stable Cargo can still parse the configuration and
  release builds stay free of nightly development flags.
- Markdown formatting is ported from Catnap's mdtablefix selection, and
  `.config/nextest.toml` bounds tests with per-test and whole-run timeouts and
  a serialized compiler-spawning group. `make test-ui` provides an explicit
  compile-time contract lane with an intentional no-op.
- Generated workflows are checked by the shared CV-005 package, pinned from the
  Makefile and configured by `.github/cv005.toml`. Whitaker runs through the
  shared action and the rendered CI installs `rust-analyzer`.
- Dependabot groups shared actions, routine GitHub Actions, and Cargo
  minor/patch updates, cools fresh releases, and tracks `rust-toolchain`.
  Generated callers delegate to the shared automerge workflow and a validated
  delayed-comment workflow.
- The application release workflow uses native macOS runners, `cross` for
  Linux/Windows/FreeBSD, a non-fail-fast matrix, stable Cargo with cleared
  `RUSTFLAGS`, checksum files beside each artefact, and a dry-run dispatch that
  can never publish from a branch. Both Polonius modes remain supported and the
  release exception is documented in the guides and ADR-004.

Retrospective lessons:

- Verify the rendered output, not only the template source. A missing final
  newline and mdtablefix paragraph wrapping both passed the parent source gates
  and only failed in rendered-project `make all`.
- Strict spelling uses Oxford `-ize` forms and British `artefact` in prose;
  upstream action and feature tokens need narrow local patterns, not broad word
  allowances.
- Assert contract invariants and shapes, not literal action SHAs or exact exit
  codes, so Dependabot bumps and `make`'s recipe-status wrapping do not create
  false failures.
- Keep expensive validation honest about its limits: the full suite passed in
  bounded runs while the single process exceeded the harness cap under host
  contention, and that evidence gap is recorded rather than hidden.
