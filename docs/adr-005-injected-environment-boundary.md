# ADR-005: Inject Process Environment Access

- Status: Accepted
- Date: 2026-08-02
- Deciders: Agent template maintainers

## Context and Decision

In the context of generated Rust projects whose behaviour depends on
environment variables, facing process-global reads that hide dependencies and
in-process mutation that makes parallel and property-based tests interfere, we
decided for injecting `mockable::Env`, constructing `mockable::DefaultEnv` only
at the production composition root, using `mockable::MockEnv` in tests, and
allowing `assert_cmd` to configure only isolated child processes, and against
direct `std::env` access in domain code, harness-process mutation, shared
locks, or serial-test attributes, to achieve explicit production signatures and
deterministic tests that remain safe under concurrency, accepting a small
adapter at each composition root and dependency parameters on environment-aware
behaviour.

## Consequences

- Clippy rejects direct process-environment reads, iteration, and mutation;
  sanctioned composition-root adapters require a narrow, reasoned expectation.
- Production code receives `mockable::Env`, composition roots construct
  `mockable::DefaultEnv`, and tests use `mockable::MockEnv` without changing
  the harness environment.
- Process-wide locks are prohibited because they serialize the suite without
  removing the ambient dependency; only `assert_cmd` child-process environment
  configuration is exempt.
