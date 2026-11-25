# ADR-007: Run the spelling builder under Python 3.14

- Status: Accepted (2026-11-25): the `typos-config-builder` invocation passes
  `--python 3.14`.
- Date: 2026-11-25
- Deciders: Agent template maintainers
- Amends: [ADR-006](adr-0006-shared-typos-config-builder-gate.md)

## Context and problem statement

`typos-config-builder` declares `requires-python >= 3.14`. A runner that exports
`UV_PYTHON` for a project test matrix, or that defaults to an older
interpreter, hands `uv tool run` a Python the builder cannot use, and the
spelling gate fails on that lane.

## Decision

The `TYPOS_CONFIG_BUILDER` command in the repository `Makefile` and in the
generated project `Makefile` passes `--python 3.14`. The mechanism, the pin,
and the scope rules in ADR-006 are unchanged. The concordat
`spelling-config-baseline` rule requires the option.
