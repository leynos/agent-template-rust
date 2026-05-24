# Developers Guide

This guide documents the tooling needed to work on the template itself. It is
separate from the generated-project guide because this parent repository runs
pytest-copier tests that render temporary Rust projects.

## Parent Template Tests

Run the public parent gate:

```sh
make test
```

The target uses `uvx --with pytest-copier --with pyyaml pytest tests/`, so
Python test dependencies must be added to that invocation before tests import
them. Keep long runs logged through `tee` into `/tmp`, following the example
in `AGENTS.md`.

The tests render both library and application projects, run generated public
gates such as `make all`, validate generated Makefiles with `mbake`, and parse
generated `Cargo.toml` files as TOML.

## Required Tooling

The parent tests expect these tools to be available when validating generated
projects:

- `uv` for isolated Python test dependency execution.
- `pytest-copier` for rendering Copier templates in tests.
- PyYAML for parsing rendered GitHub Actions workflows in tests.
- `syrupy` for generated structured file snapshots in tests.
- Rust and Cargo through `rustup`.
- cargo-nextest for generated fast test execution in CI, while generated
  Makefiles still fall back to `cargo test` for contributors.
- `mbake` for generated Makefile validation.
- Whitaker for generated lint gates.
- `clang`, `lld`, and `mold` for generated linker and coverage behaviour.

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
