# agent-template-rust

This repository provides a [Copier](https://copier.readthedocs.io/) template for
starting new Rust projects. Running Copier with this template generates a fresh
crate preconfigured with sensible defaults and continuous integration.

## How to use

1. Install Copier: `pip install copier`.
2. Run `copier copy gh:leynos/agent-template-rust <destination>`.
3. Fill in the prompts for project, crate and license information.
4. Change into the created directory and start coding.

## What you get

- **Cargo setup** using the 2024 edition and Clippy's pedantic lint level
  enabled【F:template/Cargo.toml†L1-L9】.
- **A simple entry point** that prints a greeting so the project builds
  immediately【F:template/src/main.rs†L1-L3】.
- **GitHub workflow** for running coverage with `cargo-tarpaulin` and reporting
  to Codecov【F:template/.github/workflows/coverage.yml†L1-L25】.
- **Markdownlint** configuration applying consistent line length rules
  【F:template/.markdownlint-cli2.jsonc†L1-L11】.
- **Codecov settings** requiring 80% patch coverage and a small project
  threshold【F:template/codecov.yml†L1-L8】.
- **ISC license template** ready for your details【F:template/LICENSE†L1-L9】.
- **Starter README** referencing Copier for regeneration【F:template/README.md†L1-L3】.

Use this template when you need a minimal scaffold for CLI tools or small
utilities. The included workflow ensures coverage metrics are collected and
linters run from the very first commit.
