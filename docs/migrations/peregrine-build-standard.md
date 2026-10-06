# Peregrine build-standard migration

This migration ports reusable tooling from
[Peregrine PR #11](https://github.com/leynos/peregrine-web/pull/11), at
`7a68360fb0ad3e8dfad1d6a22df62a19e41bc486`, and the reusable enhancements on
Peregrine's main branch at `bb12b23c55e757c68f7d23e65aea834aa4b2ce6a`. The
template remains a Copier project; parent pytest tests validate rendered public
commands instead of shipping Peregrine's application test harness.

## Adopt the build routes

1. Update with Copier and review the rendered conflicts. Preserve application
   code, package metadata, and the existing `enable_polonius` answer.
2. Commit the four `scripts/` entrypoints and `tools/mold/` pins. Preserve the
   executable mode on shell scripts. Keep the configured target and the
   `uses_mold` helper in agreement; only native x86_64 GNU Linux selects mold.
3. Install rustup and system clang/lld prerequisites. Run
   `make install-build-tools`, then `make check-build-tools`. The installer
   validates the archive checksum before extraction and installs the nightly
   components, including rust-analyzer.
4. Use development Make gates for Cranelift, the parallel frontend, and
   selected borrow checker. Use `make release` and `make package` for LLVM
   production artefacts, and `make coverage` for LLVM instrumentation with lld.
   Direct Cargo release/package commands inherit development defaults.
5. Remove encoded Rust flags, cross-target Make options, and development linker
   or backend overrides. Whitaker clears these independently for its driver,
   then checks the repository with its Cargo defaults and `DYLINT_RUSTFLAGS`.
6. Install mdtablefix 0.6.0 or later. `make check-fmt` now checks Rust and
   Markdown; `make fmt` rewrites both and applies markdownlint-cli2 fixes.
7. Keep full Act validation manual. Hosted CI measures coverage; Act runs the
   ordinary test suite with nesting disabled. Use
   `make whitaker-driver-integration` for cold and warm Dylint checks.
8. Run `make check-fmt`, `make lint`, `make typecheck`, and `make test`, then
   `make spelling`. Check `make -j all` still executes gates sequentially.

## Other reusable enhancements

- Daily Dependabot checks group minor and patch updates separately for Cargo
  and GitHub Actions; major updates remain individual.
- Shared documentation standards and the optional rstest-bdd v0.6.0 guide are
  refreshed from Peregrine's versioned imports: agent-helper-scripts at
  `179bbe8832d906bc0974aae0853cc8cee1ef0b75` and rstest-bdd at
  `72fb22635670e456545ca368805ba4c1c9d7bd69`. Adding the guide does not add
  rstest-bdd to every generated crate.
- CodeScene keeps the template's existing guarded, serialized publisher. The
  Peregrine-specific environment name, package dependencies, compiler
  experiments, HTTP architecture, and project ADRs do not belong in generic
  generated projects.
- Existing dependency-injection examples retain the template's tested API and
  assertion diagnostics rather than replacing them with unverified examples.

The parent tests assert action paths with full SHA refs, leaving routine
Dependabot SHA updates free to proceed. The existing narrow setup-rust
passthrough capability boundary remains explicit.
