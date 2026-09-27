# Import archive-based cargo-binstall support for rendered apps

This ExecPlan (execution plan) is a living document. The sections
`Constraints`, `Tolerances`, `Risks`, `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work
proceeds.

Status: DRAFT

## Purpose / big picture

Rendered `app` projects already contain a release workflow and
`[package.metadata.binstall]` metadata, but the current template advertises a
direct binary download using `pkg-fmt = "bin"`. The Dear Diary release work in
commits `91619cf07fa38997bd0f8e7991d1a07866d7aa31` and
`f263c326719914989bdd6abbf5fcd9ab4ea040cd` moved that project to a stronger
contract: release builds stage normal binary artefacts plus archive-based
`cargo-binstall` tarballs, checksum sidecars, structural tests, and finally a
pinned shared `stage-release-artefacts` action with
`.github/release-staging.toml` as the staging source of truth.

After this plan is implemented, a freshly rendered `app` project will publish
GitHub release assets whose names match its generated cargo-binstall metadata.
Someone can observe success by rendering an app project, running the generated
public gates, parsing the generated `Cargo.toml`, parsing the generated release
workflow, and verifying that Linux GNU targets stage
`<package>-<version>-<target>.tar.gz` archives for `cargo binstall` while other
targets keep their ordinary binary release assets.

## Constraints

This repository is a Copier template, not the generated Rust project. Changes
to generated app behaviour must be made in `template/` and proved through
parent tests under `tests/`.

The change applies to the `app` flavour only. The `lib` flavour must not render
`.github/workflows/release.yml`, `.github/release-staging.toml`, or app-only
`[package.metadata.binstall]` metadata.

Do not import Dear Diary-specific crate layout such as
`crates/dear-diary/Cargo.toml`. Rendered projects in this template place the
installable package manifest at `Cargo.toml`, and generated values must use the
Copier variables already defined in `copier.yaml`, especially
`package_name` and `repository_url`.

Do not add bespoke release packaging Python scripts to rendered projects unless
the shared action path proves unusable. Dear Diary commit
`f263c326719914989bdd6abbf5fcd9ab4ea040cd` retired
`scripts/release_packaging.py` in favour of the shared action, and this
template should import the final supported direction rather than the
intermediate helper unless a current-template constraint blocks it.

GitHub Actions references in generated workflows must stay SHA-pinned. If the
shared action revision is updated, rendered workflow contract assertions must
be updated in the same commit.

Use repository-native gates. Parent validation is `make test`, and long runs
must be captured with `tee` to `/tmp`, for example:

```sh
make test 2>&1 | tee /tmp/test-agent-template-rust-cargo-binstall-support.out
```

Commit after each implemented change and gate each commit.

## Tolerances

Escalate before implementation continues if using the shared
`stage-release-artefacts` action would require changing generated release asset
names in a way that breaks the existing app release workflow's ordinary binary
uploads.

Escalate if the shared action cannot support the rendered single-crate
manifest path `Cargo.toml` or the generated package naming scheme without
vendoring new release packaging code.

Escalate if parent `make test` failures remain after one focused fix attempt
and the failure is outside the release-template or rendered-contract surface.
Record the failing command and log path before asking for direction.

Escalate before adding new top-level Copier prompts. The current evidence
suggests the desired behaviour can be generated from existing answers, and new
prompts would widen the template's user-facing API.

Optional `act` validation is useful but not required for the first completed
implementation unless the user explicitly asks for container-backed workflow
execution. If it is attempted and fails before repository workflow steps run,
record it as environmental evidence rather than masking the failure.

## Risks

The shared action revision used by Dear Diary may drift from the current
`leynos/shared-actions` main branch and from the template's other
shared-actions references. Mitigation: pin new generated workflow calls to the
same verified current `leynos/shared-actions` revision used by this template,
`455d9ed03477c0026da96c2541ca26569a74acac`, unless a later audit deliberately
chooses a newer revision and updates all rendered workflow assertions in the
same change.

The current rendered app workflow includes Windows and macOS targets, while
the Dear Diary matrix covered Linux and FreeBSD. Mitigation: keep the broader
template matrix unless a target cannot be represented in
`.github/release-staging.toml`; disable binstall per target where the Cargo
metadata does not advertise that target.

The existing template metadata uses direct binary URLs with
`disabled-strategies = ["quick-install", "compile"]`. Moving to `pkg-fmt =
"tgz"` changes the install contract. Mitigation: add structural TOML tests
that assert the archive URL and format match the staged release archive names.

Rendered release workflow tests can become brittle if they assert raw
substrings only. Mitigation: parse generated YAML and TOML through existing
helpers such as `parse_yaml_mapping`, `parse_toml_file`, `require_mapping`,
and `require_sequence`, then use exact string assertions only for pinned action
references and shell snippets that have no structured representation.

## Progress

- [x] 2026-06-07: Confirmed the active branch is
  `cargo-binstall-support`, so this plan belongs at
  `docs/execplans/cargo-binstall-support.md`.
- [x] 2026-06-07: Reviewed repository guidance in `AGENTS.md` and loaded the
  required `execplans`, `leta`, and `grepai` skills for this planning task.
- [x] 2026-06-07: Inspected Dear Diary commit
  `91619cf07fa38997bd0f8e7991d1a07866d7aa31`; it adds binstall metadata,
  tag/version checks, archive staging, checksums, release docs, and Python
  helper tests.
- [x] 2026-06-07: Inspected Dear Diary commit
  `f263c326719914989bdd6abbf5fcd9ab4ea040cd`; it adds
  `.github/release-staging.toml`, switches release staging to the pinned
  shared `stage-release-artefacts` action, retires local packaging helpers,
  and adds workflow selftests.
- [x] 2026-06-07: Inspected the current app template release workflow,
  generated `Cargo.toml` metadata, generated Makefile, and parent rendered
  contract tests.
- [x] 2026-06-08: Audited `leynos/shared-actions` usage and confirmed the
  current shared-actions `main` revision is
  `455d9ed03477c0026da96c2541ca26569a74acac`; amended this plan so the
  planned `stage-release-artefacts` call uses that current pin instead of the
  older Dear Diary import SHA.
- [ ] Draft the initial implementation patch.
- [ ] Add or update parent tests so rendered app projects prove the release
  staging and cargo-binstall contracts.
- [ ] Run parent validation through `make test` with `tee` logging.
- [ ] Commit the gated implementation slice.

## Surprises & Discoveries

The current template already has app-only cargo-binstall metadata in
`template/Cargo.toml.jinja`; it uses `pkg-url =
"{{ repository_url }}/releases/download/v{ version }/{{ package_name }}-{ target }{ binary-ext }"`
and `pkg-fmt = "bin"`. The implementation is therefore a migration from a
direct binary contract to an archive contract, not a new feature from scratch.

The rendered app release workflow currently stages ordinary release binaries
manually in shell and names them `<package>-<target><ext>`. Dear Diary's final
shared-action configuration stages ordinary binary artefacts as
`<package>-<platform>-<arch><ext>` while producing binstall archives named
`<package>-<version>-<target>.tar.gz`. The template needs an explicit decision
on whether ordinary binary asset names should change to the Dear Diary pattern
or remain target-triple based.

The parent test suite already has the right testing shape for this change:
`tests/test_template/test_tooling_contracts.py` renders app and lib projects,
runs `make all`, validates the generated Makefile with `mbake`, parses
generated Cargo metadata, and delegates release workflow assertions to
`tests/helpers/tooling_contracts/workflows.py`.

GrepAI is available on this host, but this worktree is not currently indexed
as a `Projects` workspace project. Scoped file reads and exact searches are
therefore the practical fallback for the current checkout.

The current `leynos/shared-actions` inventory includes release-specific
actions named `rust-build-release`, `stage-release-artefacts`, and
`upload-release-assets`. The rendered app release workflow currently uses only
`setup-rust` from shared-actions and still hand-rolls build, staging, and
release upload behaviour. This plan's implementation should at minimum adopt
`stage-release-artefacts`, and should evaluate whether `rust-build-release`
and `upload-release-assets` can replace the remaining hand-written release
workflow steps without changing the generated app release contract beyond the
planned cargo-binstall archive migration.

## Decision Log

2026-06-07: Import the final Dear Diary direction from commit
`f263c326719914989bdd6abbf5fcd9ab4ea040cd`, not the intermediate bespoke
Python packaging helper from
`91619cf07fa38997bd0f8e7991d1a07866d7aa31`. Rationale: the later commit
replaces local packaging code with a shared action and configuration file,
which is the smaller, more reusable template surface.

2026-06-07: Keep the implementation app-only. Rationale: the template already
models release automation and binstall metadata as app-only, and library
projects do not publish an installable binary by default.

2026-06-07: Prefer structural rendered-output tests over parent-template
substring checks. Rationale: existing repo guidance and prior template memory
show rendered public commands and parsed TOML/YAML contracts catch meaningful
regressions while avoiding vacuous tests.

2026-06-07: Treat optional `act` selftests as a later validation layer unless
the user specifically approves the extra surface. Rationale: this parent repo
already has opt-in act validation for generated workflows, and importing Dear
Diary's full `_act_support.py` and selftest workflow would widen scope beyond
the core app-rendered binstall support.

2026-06-08: Use
`leynos/shared-actions/.github/actions/stage-release-artefacts@455d9ed03477c0026da96c2541ca26569a74acac`
for the planned staging action. Rationale: a live audit of
`https://github.com/leynos/shared-actions.git` showed that
`455d9ed03477c0026da96c2541ca26569a74acac` is current `main`, and the
template's existing shared-actions calls already use that same revision.

## Implementation plan

Milestone A establishes failing rendered-contract coverage. Add app-only
assertions in the parent tests before changing the template. The likely home
is `tests/helpers/tooling_contracts/workflows.py` for generated release
workflow checks, plus `tests/helpers/tooling_contracts/cargo.py` if
Cargo-specific metadata assertions already live there. The test should render
an app project with a package name such as `tooling_example` and assert these
facts:

1. `Cargo.toml` contains `[package.metadata.binstall]` metadata using
   `pkg-fmt = "tgz"` or the equivalent override structure.
2. The cargo-binstall URL points at
   `<repository_url>/releases/download/v{ version }/<package_name>-{ version }-{ target }.tar.gz`.
3. The release workflow uses a pinned
   `leynos/shared-actions/.github/actions/stage-release-artefacts@...` step.
4. The release workflow passes `.github/release-staging.toml` as the config
   file and matrix target keys such as `linux-x86_64`.
5. The app render includes `.github/release-staging.toml`; the lib render does
   not.
6. The staging TOML has a common binary artefact rule, enables binstall by
   default for the manifest path `Cargo.toml`, and disables binstall for
   targets that are not advertised by generated Cargo metadata.

Run the targeted parent tests and confirm they fail for the expected missing
or old direct-binary contract before implementing:

```sh
uvx --with pytest-copier --with pyyaml --with syrupy --with make-parser --with hypothesis pytest tests/test_template/test_tooling_contracts.py -q 2>&1 | tee /tmp/test-tooling-contracts-agent-template-rust-cargo-binstall-support.out
```

Milestone B changes the generated app Cargo metadata. Update
`template/Cargo.toml.jinja` inside the existing `flavour == 'app'` block so
the rendered metadata advertises archive-based binstall support. The starting
point should follow the Dear Diary metadata shape while adapting the manifest
path and package name to a single-crate generated project:

```toml
[package.metadata.binstall]

[package.metadata.binstall.overrides.'cfg(all(target_os = "linux", any(target_arch = "x86_64", target_arch = "aarch64"), target_env = "gnu"))']
pkg-url = "{{ repository_url }}/releases/download/v{ version }/{{ package_name }}-{ version }-{ target }.tar.gz"
bin-dir = "{ bin }{ binary-ext }"
pkg-fmt = "tgz"
```

If Windows or macOS binstall support is required later, add explicit matching
overrides only when the release staging config and workflow produce matching
archives for those targets.

Milestone C changes generated app release staging. Add
`template/.github/{% if flavour == 'app' %}release-staging.toml{% endif %}.jinja`
or the repository's preferred equivalent conditional path. The rendered file
should use `{{ package_name }}` for `bin_name`, `artifacts` for `dist_dir`,
`sha256` checksum sidecars, and `Cargo.toml` for `common.binstall.manifest_path`.
Represent every target in the current app matrix with a stable key:
`linux-x86_64`, `linux-aarch64`, `windows-x86_64`, `macos-x86_64`,
`macos-aarch64`, and `freebsd-x86_64`. Enable binstall only where the
generated `Cargo.toml` metadata advertises a matching archive; initially that
means Linux GNU x86_64 and aarch64.

Milestone D updates
`template/.github/workflows/{% if flavour == 'app' %}release.yml{% endif %}.jinja`.
Add `key` values to each matrix row. Replace the shell `Prepare artifact` step
with:

```yaml
- name: Stage release artefacts
  id: stage
  uses: leynos/shared-actions/.github/actions/stage-release-artefacts@455d9ed03477c0026da96c2541ca26569a74acac
  with:
    config-file: .github/release-staging.toml
    target: ${{ matrix.key }}
```

Then change the upload-artifact path from the hard-coded
`artifacts/${{ matrix.os }}-${{ matrix.arch }}` to
`${{ steps.stage.outputs.artifact-dir }}`. Preserve existing release workflow
contracts that are not part of this migration: checkout must keep
`persist-credentials: false`, `cross` must remain installed from an immutable
revision, release builds must continue to use `+stable` with empty
`RUSTFLAGS`, and release uploads must remain SHA-pinned.

Milestone E updates generated documentation. At minimum, update
`docs/users-guide.md`, `template/docs/users-guide.md.jinja`,
`docs/developers-guide.md`, and `template/docs/developers-guide.md.jinja` if
their current text still describes direct binary binstall URLs or omits the
release staging config. The rendered user guide should explain that app
projects publish cargo-binstall archives for supported Linux GNU targets and
that unsupported targets fall back to source builds or normal release
binaries. The parent developer guide should mention that release staging is
controlled by `.github/release-staging.toml` and asserted by rendered
contract tests.

Milestone F validates the implementation. Run:

```sh
make test 2>&1 | tee /tmp/test-agent-template-rust-cargo-binstall-support.out
```

Review the log if terminal output is truncated. If this passes, optionally run
the rendered act validation only when the environment is ready and the user
wants the extra coverage:

```sh
make test WITH_ACT=1 2>&1 | tee /tmp/test-act-agent-template-rust-cargo-binstall-support.out
```

Milestone G commits the gated slice. Inspect `git diff --check`, `git status
--short`, and the relevant diff. Commit only the files changed for this plan
with a message such as:

```plaintext
Add archive-based cargo-binstall release staging to app template
```

## Acceptance criteria

A rendered app project contains archive-based cargo-binstall metadata in
`Cargo.toml`, and that metadata points to GitHub release archives named
`<package>-<version>-<target>.tar.gz`.

A rendered app project contains `.github/release-staging.toml`, and that file
stages ordinary release binaries, checksum sidecars, and Linux GNU binstall
archives from the generated single-crate `Cargo.toml`.

A rendered app release workflow delegates artefact staging to the pinned
shared `stage-release-artefacts` action, passes the matrix target key into the
staging config, and uploads the directory reported by the action.

A rendered lib project still omits app-only release workflow, release staging
config, and binstall metadata.

The parent `make test` gate passes, with output captured in `/tmp` and
reviewed if truncated.

## Outcomes & Retrospective

Not yet implemented. Record the final rendered behaviour, validation commands,
commit hash, and any follow-up work here after the implementation is complete.
