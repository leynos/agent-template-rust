# ADR-005: Inject Process Environment Access

- Status: Accepted
- Date: 2026-08-02
- Deciders: Agent template maintainers

## Context and Decision

Triage: Accepted. The original decision was technically correct but obscured
its parallel choices in one overloaded sentence.

In generated Rust projects, process-global reads hide environment dependencies,
while in-process mutation makes parallel and property-based tests interfere.

We decided to inject `mockable::Env`, construct `mockable::DefaultEnv` only at
the production composition root, use `mockable::MockEnv` in tests, and allow
`assert_cmd` to configure only isolated child processes. We reject direct
`std::env` access in domain code, harness-process mutation, shared locks, and
serial-test attributes.

This decision provides explicit production signatures and deterministic tests
that remain safe under concurrency. It accepts a small adapter at each
composition root and dependency parameters on environment-aware behaviour.

## Consequences

- Clippy rejects direct process-environment reads, iteration, and mutation;
  sanctioned composition-root adapters require a narrow, reasoned expectation.
- Production code receives `mockable::Env`, composition roots construct
  `mockable::DefaultEnv`, and tests use `mockable::MockEnv` without changing
  the harness environment.
- Process-wide locks are prohibited because they serialize the suite without
  removing the ambient dependency; only `assert_cmd` child-process environment
  configuration is exempt.
