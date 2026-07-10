# Agent Instructions

## Repository Purpose

This repository is a Copier template for generating Rust projects. It is not
itself the generated Rust project. Files under `template/` are copied or
rendered into downstream projects, and files under `tests/` validate the
template output through `pytest-copier`.

When changing generated Rust project behaviour, update the template files and
the parent repository tests that prove the rendered output. Prefer assertions
against the generated project's public commands, such as `make all`, over
testing private implementation details in the parent repository.

## Copier Test Dependencies

Template tests use `pytest` and `pytest-copier`. Install or run them through
`uv` so the parent repository does not need a manually managed virtual
environment.

See `docs/users-guide.md` for generated-project features and
`docs/developers-guide.md` for parent-template tooling requirements.

The repository Makefile exposes the expected entrypoint:

```sh
make test
```

Markdown spelling is enforced separately with the pinned `typos` release:

```sh
make spelling
```

The tracked `typos.toml` is generated from the estate-wide shared dictionary
and `typos.local.toml`. Add only narrow product-name, upstream-term, or fixture
exceptions to the local overlay, then regenerate with
`uv run scripts/generate_typos_config.py`.

That target currently runs:

```sh
uvx --with pytest-copier pytest tests/
```

If tests import additional pytest plugins or assertion helpers, add them to
the `uvx --with ...` invocation or to the documented dependency list before
using them in tests. Do not rely on packages installed in an ambient shell
environment.

When debugging generated projects manually, render with Copier into a temporary
directory, then run the generated project's public gates from that rendered
directory. Keep build output in the rendered project or Cargo's default shared
cache; do not configure an isolated Cargo cache.

## Validation

Run parent-template tests after changing `copier.yaml`, `template/`, or
`tests/`:

```sh
make test
```

For long test runs, capture output with `tee` into `/tmp`, for example:

```sh
make test 2>&1 | tee /tmp/test-agent-template-rust-$(git branch --show-current).out
```

Review the log before committing if the terminal output is truncated.

Run `make spelling` after changing Markdown or Markdown templates.
