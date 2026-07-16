# User Guide

This repository is a Copier template for creating Rust projects. The generated
project is intended to be usable immediately after rendering.

## Copier Prompts

The template asks for normal project identity values such as project name,
package name, licence holder, and contact email. It also asks for package
metadata used in the generated `Cargo.toml`:

- `flavour` selects `lib` or `app` and determines the generated structure and
  release metadata.
- `package_description` becomes `[package].description`.
- `repository_url` becomes `[package].repository` and is used by generated
  app projects for cargo-binstall release URLs.
- `homepage_url` becomes `[package].homepage`.
- `package_keywords` becomes `[package].keywords`.
- `package_categories` becomes `[package].categories`.
- `rust_nightly_date` selects the pinned nightly toolchain date.
- `license_year` sets the copyright year in `LICENSE`.
- `dev_target` selects the target-specific Linux linker block generated in
  `.cargo/config.toml`.
- `codescene_project_id` is the CodeScene project id for the coverage gate. It
  defaults to empty, and every CodeScene step degrades gracefully while it is
  unset: the guarded upload in `coverage-main.yml` skips without a token, and
  the pull-request workflow leaves the changed-line `mode: check` gate deferred
  in a documented comment. Fill it in (and set the `CS_ACCESS_TOKEN` secret)
  once the repository is onboarded to CodeScene.

## Generated Tooling

Generated projects use Rust 2024, a pinned nightly toolchain, strict lint
settings, and documented starter code. Library projects render `src/lib.rs`.
Application projects render `src/main.rs`, `src/lib.rs`, release automation,
and `[package.metadata.binstall]` metadata for binary installation.

Development builds use Cranelift for debug code generation. On Linux targets,
`.cargo/config.toml` configures clang to link with `mold` so local debug builds
link quickly. Coverage generation uses `lld` instead because LLVM coverage
tools expect LLVM-compatible linker behaviour.

## Makefile Targets

The generated `Makefile` exposes these public targets:

- `make all` runs formatting checks, linting, tests, and spelling checks.
- `make check-fmt` verifies Rust formatting.
- `make lint` runs rustdoc, Clippy, and Whitaker with warnings denied.
- `make test` runs `cargo nextest run` when cargo-nextest is installed and
  falls back to `cargo test` otherwise. All projects also run doctests.
- `make build` builds the debug target.
- `make release` builds the release target.
- `make coverage` writes `lcov.info` using `cargo llvm-cov` and `lld`.
- `make audit` derives the Rust workspace root with `cargo metadata` and runs
  `cargo audit` once from that root.
- `make markdownlint` checks Markdown files and enforces en-GB-oxendict
  spelling through the pinned `typos` release.
- `make spelling` refreshes the shared Oxford dictionary when its published
  source is newer than the ignored local cache, generates `typos.toml`, and
  checks Markdown prose.
- `make nixie` validates Mermaid diagrams.

Install `clang`, `lld`, `mold`, `python3`, and `cargo-audit` before running the
full generated workflow locally on Linux.

## Scheduled Mutation Testing

Generated projects include `.github/workflows/mutation-testing.yml`, a scheduled
GitHub Actions workflow that runs mutation testing with `cargo-mutants`. It is a
thin caller of the shared `leynos/shared-actions` `mutation-cargo` reusable
workflow.

Mutation testing measures test-suite quality. It introduces small changes
(mutants) into the source and confirms the tests fail in response. A surviving
mutant marks a code path the tests do not meaningfully exercise, so promote it
into a new test rather than ignoring it.

The workflow runs on a daily schedule (09:15 UTC by default) and can also be
started manually from the **Actions** tab with **Run workflow**. Scheduled runs
mutate only files changed within the detection window, so routine runs stay
fast; a manual dispatch mutates the whole crate, fanned out across shards.
Because the runs are scheduled rather than gating pull requests, they surface
coverage gaps without slowing day-to-day CI, and they do not block merges.

When adopting the workflow in a new repository, stagger the cron slot: pick an
unclaimed daily time to avoid concurrent runs across related repositories. The
`mutation` job runs with a least-privilege token (`contents: read` plus
`id-token: write` for workflow-source resolution).
