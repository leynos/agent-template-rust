# ADR-004: Make Polonius support optional

## Status

Accepted.

## Context

Polonius permits borrow-centric internal APIs that the stable non-lexical
lifetime analysis rejects, but its alpha analysis still requires a dated
nightly toolchain and `-Zpolonius=next`. Applications can usually accept that
binding, while reusable libraries often need wider compiler compatibility.
Cargo build flags are also replaced whenever tooling supplies `RUSTFLAGS`, so
an enabled project must preserve the Polonius flag across every such build
surface.

## Decision

In the context of generating Rust applications and libraries with different
compiler-compatibility needs, facing the tension between borrow-centric APIs
and Polonius's nightly-only status, we decided for an `enable_polonius` Copier
choice that defaults on for applications and off for libraries and propagates
the selected flag through Cargo, Make, coverage, Continuous Integration (CI),
and release builds, and against enabling Polonius universally, disabling it
universally, or waiting for stabilization before exposing it, to achieve an
explicit and consistently enforced per-project toolchain contract, accepting
that opted-in projects depend on a dated nightly and must keep every
`RUSTFLAGS` override synchronized.

## Progress and outcome

The template now renders the option, pinned toolchain, compiler flags, policy
guidance, CI and release configuration for the selected state. Parent-template
contract and compilation tests cover enabled and disabled applications and
libraries. The implementation and its validation are complete; future
generated projects retain an explicit opt-out or opt-in as their compatibility
requirements change.

## Risks

- A pinned nightly can become unavailable or acquire regressions and therefore
  requires deliberate upgrades.
- A new build path that overrides `RUSTFLAGS` can silently omit Polonius unless
  its rendered contract is extended and tested.
- Enabling borrow-centric APIs can make source builds fail under stable Rust or
  plain nightly without `-Zpolonius=next`.

## Consequences

- Generated applications adopt Polonius by default; generated libraries keep
  wider compiler compatibility by default.
- Opted-in projects document their nightly requirement and preserve the flag
  across supported build paths.
- Maintainers must treat the Copier answer, dated channel, and explicit flag
  propagation as one toolchain policy when updating generated projects.
