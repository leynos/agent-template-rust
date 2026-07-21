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
- `make fmt` formats Rust and Markdown sources.
- `make lint` runs rustdoc, Clippy, and Whitaker with warnings denied.
- `make typecheck` type-checks the workspace without building.
- `make test` runs `cargo nextest run` when cargo-nextest is installed and
  falls back to `cargo test` otherwise. All projects also run doctests.
- `make build` builds the debug target.
- `make release` builds the release target.
- `make coverage` writes `lcov.info` using `cargo llvm-cov` and `lld`.
- `make audit` derives the Rust workspace root with `cargo metadata` and runs
  `cargo audit` once from that root. Generated CI skips this gate for
  Dependabot pull requests so whole-lockfile advisories do not block unrelated
  dependency bumps; human pull requests still run it. The separate
  `.github/workflows/audit.yml` workflow runs weekly and can also be triggered
  manually to keep the lockfile covered.
- `make markdownlint` checks Markdown files and enforces en-GB-oxendict
  spelling through the pinned `typos` release.
- `make spelling` refreshes the shared Oxford dictionary when its published
  source is newer than the ignored local cache, generates `typos.toml`, and
  checks Markdown prose.
- `make nixie` validates Mermaid diagrams.

Install `clang`, `lld`, `mold`, `python3`, and `cargo-audit` before running the
full generated workflow locally on Linux.
