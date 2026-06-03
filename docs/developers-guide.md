# Developers Guide

This guide documents the tooling needed to work on the template itself. It is
separate from the generated-project guide because this parent repository runs
pytest-copier tests that render temporary Rust projects.

## Parent Template Tests

Run the public parent gate:

```sh
make test
```

The target uses
`uvx --with pytest-copier --with pyyaml --with syrupy --with make-parser --with hypothesis pytest tests/`,
so Python test dependencies must be added to that invocation before tests
import them. Keep long runs logged through `tee` into `/tmp`, following the
example in `AGENTS.md`.

The tests render both library and application projects, run generated public
gates such as `make all`, validate generated Makefiles with `mbake`, and parse
generated `Cargo.toml` files as TOML.

Generated audit coverage is tested without network access by replacing Cargo
with a fake executable. The regression verifies that `make rust-audit` derives
the workspace root from `cargo metadata`, ignores manifests outside workspace
metadata, and invokes `cargo audit` once from the workspace root.

Optional GitHub Actions validation runs rendered workflows through `act`. It is
disabled by default and only runs when `WITH_ACT=1` is present:

```sh
make test WITH_ACT=1
```

The parent Makefile maps `WITH_ACT=1` to `RUN_ACT_VALIDATION=1` for pytest.
Those checks require `act` and either Docker or Podman. They prepare rendered
projects as temporary Git repositories, run the generated pull-request
workflow, and assert black-box evidence for the shared coverage action and Rust
test execution. Parent CI runs this act-enabled test mode.

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

GitHub Actions in both parent and generated workflows are SHA-pinned. When an
action revision changes, update the rendered workflow assertions that lock the
pin.

## Test Helper Layout

Reusable test support lives under `tests/helpers/`:

- `tests/helpers/rendering.py` renders Copier projects and exposes generated
  project command helpers.
- `tests/helpers/generated_files.py` centralizes generated text, TOML, and YAML
  parsing with pytest failure messages.
- `tests/helpers/tooling_contracts.py` contains generated Makefile, Cargo,
  documentation, CI, release, and coverage-action contract assertions.

Container-aware support for optional `act` tests lives in `tests/utilities.py`.
Direct helper edge-case tests live in `tests/test_helpers.py`; rendered project
tests should use the shared helper APIs instead of reimplementing file parsing
or workflow schema checks.
