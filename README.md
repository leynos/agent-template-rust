# agent-template-rust

This repository provides a [Copier](https://copier.readthedocs.io/) template
for starting new Rust projects. Running Copier with this template generates a
fresh crate preconfigured with sensible defaults and continuous integration.

The template requires **Copier 9.0** or later to avoid incompatibilities.

## How to use

1. Install Copier 9.0 or later: `pip install copier`.
2. Run `copier copy gh:leynos/agent-template-rust <destination>`.
3. Fill in the prompts for project, crate, license, and nightly toolchain date.
4. Change into the created directory and start coding.

## What you get

- **Cargo setup** using the 2024 edition and Clippy's pedantic lint level
  enabled【F:template/Cargo.toml†L1-L9】.
- **Pinned toolchain** file specifying a configurable nightly release
  【F:template/rust-toolchain.toml.jinja†L1-L3】.
- **Optional Polonius support**, recommended and enabled by default for
  applications, with coherent Cargo, Makefile, coverage, release, and agent
  guidance that can be disabled for wider library compiler compatibility.
- **Project metadata prompts** for repository URL, homepage, crates.io keywords,
  crates.io categories, nightly date, and optional Linux development target.
- **Fast generated tooling** including Cranelift debug code generation, Linux
  `mold` linking for development builds, cargo-nextest tests with a cargo-test
  fallback, Whitaker linting, and a lld-backed coverage target.
- **Starter code** providing either a binary entry point or a library
  function depending on flavour【F:template/src/{% if flavour == APP
  %}main.rs{% else %}lib.rs{% endif %}.jinja†L1-L10】.
- **GitHub CI workflow** that formats, lints, tests, and holds pull requests
  to a coverage ratchet【F:template/.github/workflows/ci.yml†L1-L35】, with
  main's coverage uploaded to CodeScene by a separate push-to-main publisher
  【F:template/.github/workflows/coverage-main.yml.jinja†L1-L40】.
- **Release workflow** for cross-platform binaries when the app flavour is used
  【F:template/.github/workflows/{% if flavour == APP %}release.yml{% endif
  %}.jinja†L1-L114】.
- **Markdownlint** configuration applying consistent line length rules
  【F:template/.markdownlint-cli2.jsonc†L1-L11】.
- **Codecov settings** requiring 80% patch coverage and a small project
  threshold【F:template/codecov.yml†L1-L8】.
- **ISC license template** ready for your details【F:template/LICENSE†L1-L9】.
- **Starter README** referencing Copier for
  regeneration【F:template/README.md†L1-L3】.

Use this template when you need a minimal scaffold for CLI tools or small
utilities. The included workflow ensures coverage metrics are collected and
linters run from the very first commit.

## Testing

Run the parent template tests through the repository `Makefile`. Run
`make help` to list the available parent Makefile targets. The `test` target
uses `uvx` to provide `pytest-copier`, `PyYAML`, `syrupy`, and `make-parser`
without a manually managed virtual environment:

```bash
make test
```

Optional local GitHub Actions validation is gated behind `WITH_ACT=1` and
requires `act` plus a Docker-compatible container runtime:

```bash
make test WITH_ACT=1
```

Parent and generated-project CI run this mode in a separate
`act-validation.yml` workflow on manual dispatch. Hosted tests and coverage
remain the ordinary pull-request gate.

## Generated Quality Gate Flow

The generated `make all` gate runs `check-fmt`, `lint`, `test`, and `spelling`
sequentially, including under `make -j`. Lint runs rustdoc and Clippy before
Whitaker; tests choose nextest or Cargo, then run workspace doctests. Hosted CI
also audits dependencies and measures LLVM coverage. A separate publisher
advances the main-branch coverage baseline and uploads guarded CodeScene data.
Manual Act validation runs the ordinary suite without hosted coverage.

Additional details are in [`docs/testing.md`](docs/testing.md).

User-facing generated-project behaviour is documented in
[`docs/users-guide.md`](docs/users-guide.md), with upgrade guidance in the
[`0.2.0 migration guide`](docs/migrations/0.2.0.md) and the
[`0.3.0 migration guide`](docs/migrations/0.3.0.md), plus the
[build-standard migration guide](docs/migrations/peregrine-build-standard.md).
Parent-template development requirements are documented in
[`docs/developers-guide.md`](docs/developers-guide.md).
