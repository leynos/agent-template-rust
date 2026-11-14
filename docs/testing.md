# Testing

This project uses [pytest](https://pytest.org) with the
[pytest-copier](https://github.com/copier-org/pytest-copier) plugin to verify
the Copier template renders correctly.

Run the tests after making changes to the template:

```bash
pip install -r requirements.txt
pytest
```

The tests build the rendered project and validate the generated Makefile with
`mbake`. They also run `cargo clippy` so lint warnings are treated as errors.

## Generated Quality Gate Flow

Figure: The generated `make all` quality gate verifies formatting, linting, and
tests. The main generated CI workflow also runs the audit and coverage targets;
the separate Act validation workflow runs the parent template tests with
`WITH_ACT=1` so rendered workflow checks do not slow the main CI path.

```mermaid
flowchart LR
    Dev[Developer runs make all] --> All[all]
    All --> CheckFmt[check-fmt]
    All --> Lint[lint]
    All --> Test[test]
    All --> WorkflowContracts[test-workflow-contracts]

    CheckFmt --> CargoFmt[cargo fmt --check]
    Lint --> YamlLint[lint-yaml]
    Lint --> ActionLint[lint-actions]
    Lint --> ShellLint[lint-shell]
    Lint --> RustDoc[cargo doc --no-deps]
    Lint --> Clippy[cargo clippy]
    Lint --> Whitaker[whitaker --all]
    Test --> NextestOrCargo[cargo nextest run or cargo test]
    Test --> DocTests[cargo test --doc]

    subgraph Main_CI[Generated .github/workflows/ci.yml]
        CI[build-test job]
        CI --> CIFormat[make check-fmt]
        CI --> MarkdownLint[markdownlint-cli2]
        CI --> CIAudit[make audit]
        CI --> CILint[make lint]
        CI --> Coverage[generate-coverage action]
        Coverage --> Lcov[lcov.info]
        Lcov --> Ratchet[coverage ratchet]
    end

    subgraph Main_Coverage[Generated .github/workflows/coverage-main.yml]
        Publisher[coverage-upload job on main]
        Publisher --> Baseline[ratchet baseline]
        Publisher --> CodeScene[upload CodeScene coverage]
    end

    subgraph Audit_Target[make audit]
        CIAudit --> Metadata[cargo metadata via python3]
        Metadata --> CargoAudit[cargo audit]
        CargoAudit --> Ignores[CARGO_AUDIT_IGNORES to --ignore flags]
    end

    subgraph Act_Validation[Generated .github/workflows/act-validation.yml]
        ActWorkflow[act-validation job]
        ActWorkflow --> InstallAct[install act]
        InstallAct --> DockerInfo[docker info]
        DockerInfo --> ActTests[make test WITH_ACT=1]
    end
```
