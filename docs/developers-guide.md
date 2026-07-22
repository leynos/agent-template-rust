# Developers Guide

This guide documents the tooling needed to work on the template itself. It is
separate from the generated-project guide because this parent repository runs
pytest-copier tests that render temporary Rust projects.

## Parent Template Tests

Run the public parent gate:

```sh
make test
```

The target uses `uvx --with pytest-copier --with pyyaml --with syrupy --with
make-parser --with hypothesis pytest tests/`, so Python test dependencies must
be added to that invocation before tests import them. Keep long runs logged
through `tee` into `/tmp`, following the example in `AGENTS.md`.

The tests render both library and application projects, run generated public
gates such as `make all`, validate generated Makefiles with `mbake`, and parse
generated `Cargo.toml` files as TOML.

## Formatting, Linting, and Type Checking

The parent gates run Ruff and mypy over the `tests/` tree; install `uv` so
`uvx` can provision the tools on demand:

- `make check-fmt` verifies formatting with `ruff format --check`.
- `make fmt` rewrites formatting with `ruff format`.
- `make lint` runs `ruff check`.
- `make typecheck` runs `mypy` with the pytest dependency stubs and
  `types-PyYAML`.

## Shared Oxford Spelling Gate

Both the template repository and rendered projects enforce en-GB-oxendict
Markdown spelling with `typos` 1.48.0. The tracked `typos.toml` is generated;
never edit its entries manually. Put a verified product name, upstream term, or
repository-specific correction in `typos.local.toml`, then run:

```sh
uv run scripts/generate_typos_config.py
```

The generator collects the shared dictionary from
`leynos/agent-helper-scripts` into the ignored local cache only when the remote
source is newer. It validates and atomically replaces that cache, retains a
newer local copy, and supports offline reuse once populated. `make spelling`
regenerates the tracked configuration before checking maintained Markdown and
rendered Markdown templates.

Generated audit coverage is tested without network access by replacing Cargo
with a fake executable. The regression verifies that `make rust-audit` derives
the workspace root from `cargo metadata`, ignores manifests outside workspace
metadata, and invokes `cargo audit` once from the workspace root.

Generated CI skips the `cargo-audit` install, Python setup, and `make audit`
steps when `github.actor` is `dependabot[bot]`. That keeps whole-lockfile
advisories from blocking unrelated Dependabot PRs while leaving the audit gate
in place for human PRs. The compensating control is
`template/.github/workflows/audit.yml`, which runs weekly and can also be
triggered manually.

Optional GitHub Actions validation runs rendered workflows through `act`. It is
disabled by default and only runs when `WITH_ACT=1` is present:

```sh
make test WITH_ACT=1
```

The parent Makefile maps `WITH_ACT=1` to `RUN_ACT_VALIDATION=1` for pytest.
Those checks require `act` and either Docker or Podman. They prepare rendered
projects as temporary Git repositories, run the generated act-validation
workflow, and assert black-box evidence for Rust test execution.

Parent CI keeps Act validation in `.github/workflows/act-validation.yml`.
The main `.github/workflows/ci.yml` workflow runs ordinary `make test` without
`WITH_ACT=1` so the slower container-backed checks run in parallel instead of
blocking the main test and coverage path.

## Required Tooling

The parent tests expect these tools to be available when validating generated
projects:

- `uv` for isolated Python test dependency execution.
- `pytest-copier` for rendering Copier templates in tests.
- `PyYAML` for parsing rendered GitHub Actions workflows in tests.
- `syrupy` for generated structured file snapshots in tests.
- `make-parser` for generated Makefile structure assertions in tests.
- `hypothesis` for generated-file schema helper property tests.
- Rust and Cargo through `rustup`.
- cargo-nextest for generated fast test execution in CI, while generated
  Makefiles still fall back to `cargo test` for contributors.
- `mbake` for generated Makefile validation.
- `python3` for generated audit target workspace manifest extraction.
- `cargo-audit` for generated dependency vulnerability checks.
- `Whitaker` for generated lint gates.
- `clang`, `lld`, and `mold` for generated linker and coverage behaviour.
- `act` plus Docker or Podman for opt-in local GitHub Actions validation.

The generated project itself uses Cranelift for debug code generation, Linux
`mold` linking for development builds, and `lld` for coverage because coverage
is driven by LLVM tooling.

## Design Notes

Keep generated-project behaviour in `template/` and prove it from parent tests
under `tests/`. Prefer assertions that render a real project and run public
generated commands over checks that only inspect template source text.

GitHub Actions in both parent and generated workflows are SHA-pinned.
Dependabot owns bumping `leynos/shared-actions` pins in both the parent
workflows and the templates it renders; rendered workflow assertions in
`tests/helpers/tooling_contracts/workflows.py` check the *shape* of a
shared-actions `uses:` ref (correct path, pinned to a full 40-hex commit SHA)
rather than the exact SHA value, so a routine Dependabot bump does not fail
the contract. See `template/docs/developers-guide.md.jinja`'s "Workflow pins
and Dependabot" section for the policy that generated projects inherit.

## Test Helper Layout

Reusable test support lives under `tests/helpers/`:

- `tests/helpers/rendering.py` renders Copier projects and exposes generated
  project command helpers.
- `tests/helpers/generated_files.py` centralizes generated text, TOML, and YAML
  parsing with pytest failure messages.
- `tests/helpers/tooling_contracts/` contains generated Makefile, Cargo,
  documentation, CI, release, and coverage-action contract assertions.
- `tests/conftest.py` provides the session-scoped `act_ready` fixture, which
  skips act-dependent tests unless `RUN_ACT_VALIDATION=1` is set and at least
  one container runtime is reachable.
- `tests/test_github_actions_integration.py` renders a project, initializes it
  as a Git repository, runs the generated act-validation workflow through
  `act`, and asserts black-box Rust test evidence from JSON event logs.
- `tests/test_parent_ci.py` asserts that parent main CI keeps act validation
  separate and that `.github/workflows/act-validation.yml` carries act
  pinning and installation, the Docker runtime check, and `make test WITH_ACT=1`.

Container-aware support for optional `act` tests lives in `tests/utilities.py`.
Direct helper edge-case tests live in `tests/test_helpers.py`; rendered project
tests should use the shared helper APIs instead of reimplementing file parsing
or workflow schema checks.
