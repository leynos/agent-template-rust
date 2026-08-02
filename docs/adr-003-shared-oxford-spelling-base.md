# ADR-003: Generate spelling policy from a shared base

## Status

Accepted.

## Context

Generated projects need the same en-GB-oxendict policy as the wider `leynos`
estate. The `typos` `en-gb` locale enforces British `-our` and `-yse` forms but
prefers plain-British `-ise` over Oxford `-ize`. Copying curated overrides into
each generated project would cause drift, while making every exception global
would hide repository-specific mistakes.

## Decision

Generated projects refresh the tracked shared dictionary published by
`leynos/agent-helper-scripts` into ignored `.typos-oxendict-base.toml`, using
`.typos-oxendict-base.json` for source identity and freshness validators. The
generator merges that base with tracked `typos.local.toml` and writes a
deterministic, tracked `typos.toml`.

The refresh bounds dictionary inputs, validates data before atomic replacement,
serializes cache and metadata writers with a cross-process lock, keeps a valid
cache when its authority is not newer, reports bounded stale-cache diagnostics,
and supports explicit offline reuse.

The template repository always uses this mechanism through `make spelling`.
Generated repositories include it when the `en_gb_oxendict` Copier option is
enabled (the default): their Makefile pins `typos`, exposes `make spellcheck`,
includes that gate in `make all` and `make markdownlint`, and runs it through
Continuous Integration (CI). Disabled renders omit the files, wiring, and
documentation entirely.

## Consequences

- Generic Oxford stems are curated once for the estate.
- Generated projects retain reviewable, reproducible configuration and work
  offline after their cache is populated.
- Product names, upstream quotations, and deliberate fixtures remain narrow
  local exceptions.
- A fresh checkout needs network access to collect the shared base before its
  first spelling run.
- Concurrent generator processes serialize refreshes; a crashed writer may
  leave an empty lock file, which is harmless and remains ignored.
