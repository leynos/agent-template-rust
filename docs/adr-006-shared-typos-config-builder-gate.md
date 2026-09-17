# ADR-006: Run spelling through the shared typos-config-builder gate

- Status: Accepted
- Date: 2026-09-17
- Deciders: Agent template maintainers
- Supersedes: [ADR-003](adr-003-shared-oxford-spelling-base.md)

## Context

[ADR-003](adr-003-shared-oxford-spelling-base.md) decided the spelling policy:
a curated estate-wide en-GB-oxendict base merged with a narrow repository
overlay. That policy is unchanged. Its mechanism has not survived.

Each repository vendored a generator script, a cached copy of the shared
dictionary, a pinned `typos` version, and a tracked generated `typos.toml`.
Every dictionary change therefore had to be rolled out repository by
repository, and each consumer carried Python code that had nothing to do with
its own product. The cached base also went stale silently, so two repositories
could disagree about the estate policy while both looked current.

A shared tool, `typos-config-builder`, now owns the whole gate. It resolves the
live dictionary, renders the configuration, runs its own pinned Typos binary,
and applies the shared phrase corrections that Typos cannot express.

## Decision

Both the template repository and generated projects run one command:

```make
TYPOS_CONFIG_BUILDER_VERSION ?= v0.1.1
TYPOS_CONFIG_BUILDER = uv tool run --from \
	"git+https://github.com/leynos/typos-config-builder.git@$(TYPOS_CONFIG_BUILDER_VERSION)" \
	typos-config-builder

spelling:
	$(TYPOS_CONFIG_BUILDER) gate --repository .
```

The gate is pinned by release tag. Estate tags are never moved, so a tag
identifies one tree as precisely as a commit while remaining readable in a
Makefile and in a `copier update` diff.

The gate regenerates `typos.toml` from the live shared dictionary and the
tracked `typos.local.toml` overlay on every run. Because the authority is live,
`typos.toml` is generated output and is never drift checked in CI: a drift
check would fail every consumer on every estate dictionary edit.

The template repository gates with `--scope all` because it must also cover
`.jinja` payload files, which the default Markdown scope does not match.
Generated projects gate at the default Markdown scope.

The gate enumerates its inputs with `git ls-files`, so it reads tracked and
staged files only. A generated project must therefore be a Git repository with
its files staged before `make spelling`, `make markdownlint` or `make all` can
check anything.

Each repository retains only `typos.local.toml` for narrow product names,
upstream terms, and deliberate fixtures. The vendored generator, the rollout
module, the local `typos` pin, and the pre-generated template `typos.toml` are
removed. The builder keeps its own untracked dictionary cache at
`.typos-oxendict-base.toml` and `.typos-oxendict-base.json`, so both `.gitignore`
files retain those two entries and the generated `make clean` still removes them.

## Consequences

- Estate dictionary changes reach every consumer on its next gate run, with no
  per-repository rollout and no builder version bump.
- A spelling run reaches the network by default, so the shared dictionary is
  never stale; the builder falls back to its own cache when the authority is
  unreachable.
- `typos.toml` is generated on every run, so a freshly rendered project produces
  it on first gate run and commits it thereafter.
