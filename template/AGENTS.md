# Assistant Instructions

Follow these guidelines when modifying files within this template.

- Run `cargo fmt`, `cargo clippy -- -D warnings`, and `cargo test` before committing.
- Clippy warnings MUST be disallowed.
- Where a function is too long, extract meaningfully named helper functions adhering to separation of concerns and CQRS.
- Where a function has too many parameters, group related parameters in meaningfully named structs.
- Where a function is returning a large error consider using `Arc` to reduce the amount of data returned.

## Code Style and Structure

* **Code is for humans.** Write your code with clarity and empathy—assume a tired teammate will need to debug it at 3 a.m.
* **Comment *why*, not *what*.** Explain assumptions, edge cases, trade-offs, or complexity. Don't echo the obvious.
* **Clarity over cleverness.** Be concise, but favour explicit over terse or obscure idioms. Prefer code that's easy to follow.
* **Use functions and composition.** Avoid repetition by extracting reusable logic. Prefer generators or comprehensions, and declarative code to imperative repetition when readable.
* Functions must be small, clear in purpose, single responsibility, and obey command/query segregation.
* Commit messages should be descriptive, explaining what was changed and why.
* **Name things precisely.** Use clear, descriptive variable and function names. For booleans, prefer names with `is`, `has`, or `should`.
* **Structure logically.** Each file should encapsulate a coherent module. Group related code (e.g., models + utilities + fixtures) close together.
* **Group by feature, not layer.** Colocate views, logic, fixtures, and helpers related to a domain concept rather than splitting by type.

## Documentation Maintenance

* **Reference:** Use the markdown files within the `docs/` directory as a knowledge base and source of truth for project requirements, dependency choices, and architectural decisions.
* **Update:** When new decisions are made, requirements change, libraries are added/removed, or architectural patterns evolve, **proactively update** the relevant file(s) in the `docs/` directory to reflect the latest state. Ensure the documentation remains accurate and current.

## Rust Specific Guidance
This repository is written in Rust and uses Cargo for building and dependency management. Contributors should follow these best practices when working on the project:

* Write unit and behavioural tests for new functionality. Run both before and after making any change.
* Document public APIs using Rustdoc comments (`///`) so documentation can be generated with cargo doc.
* Prefer immutable data and avoid unnecessary `mut` bindings.
* Handle errors with the `Result` type instead of panicking where feasible.
* Use explicit version ranges in `Cargo.toml` and keep dependencies up-to-date.
* Avoid `unsafe` code unless absolutely necessary and document any usage clearly.

## Markdown Guidance

* Validate Markdown files using `markdownlint`.
* Validate Markdown Mermaid diagrams using `nixie`.

**These practices will help maintain a high-quality codebase and make collaboration easier**
