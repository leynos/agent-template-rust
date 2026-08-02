//! Compile-time lint and documentation UI contracts.

use std::{
    io,
    path::Path,
    process::{Command, Output},
};

struct UiCase {
    command: &'static str,
    target: &'static str,
    target_args: &'static [&'static str],
    expected: &'static str,
}

const CLIPPY_CASES: &[UiCase] = &[
    UiCase {
        command: "clippy",
        target: "clippy_missing_assert_message",
        target_args: &["--bin", "clippy_missing_assert_message"],
        expected: include_str!("ui/expected/clippy_missing_assert_message.stderr"),
    },
    UiCase {
        command: "clippy",
        target: "clippy_disallowed_methods",
        target_args: &["--bin", "clippy_disallowed_methods"],
        expected: include_str!("ui/expected/clippy_disallowed_methods.stderr"),
    },
];

const RUSTDOC_CASES: &[UiCase] = &[
    UiCase {
        command: "doc",
        target: "rustdoc_missing_crate_level_docs",
        target_args: &["--bin", "rustdoc_missing_crate_level_docs"],
        expected: include_str!("ui/expected/rustdoc_missing_crate_level_docs.stderr"),
    },
    UiCase {
        command: "doc",
        target: "rustdoc_broken_intra_doc_links",
        target_args: &["--bin", "rustdoc_broken_intra_doc_links"],
        expected: include_str!("ui/expected/rustdoc_broken_intra_doc_links.stderr"),
    },
    UiCase {
        command: "doc",
        target: "rustdoc_private_intra_doc_links",
        target_args: &["--lib", "--features", "private-intra-doc-links"],
        expected: include_str!("ui/expected/rustdoc_private_intra_doc_links.stderr"),
    },
    UiCase {
        command: "doc",
        target: "rustdoc_bare_urls",
        target_args: &["--bin", "rustdoc_bare_urls"],
        expected: include_str!("ui/expected/rustdoc_bare_urls.stderr"),
    },
    UiCase {
        command: "doc",
        target: "rustdoc_invalid_html_tags",
        target_args: &["--bin", "rustdoc_invalid_html_tags"],
        expected: include_str!("ui/expected/rustdoc_invalid_html_tags.stderr"),
    },
    UiCase {
        command: "doc",
        target: "rustdoc_invalid_codeblock_attributes",
        target_args: &["--bin", "rustdoc_invalid_codeblock_attributes"],
        expected: include_str!("ui/expected/rustdoc_invalid_codeblock_attributes.stderr"),
    },
    UiCase {
        command: "doc",
        target: "rustdoc_unescaped_backticks",
        target_args: &["--bin", "rustdoc_unescaped_backticks"],
        expected: include_str!("ui/expected/rustdoc_unescaped_backticks.stderr"),
    },
];

#[test]
fn compile_time_ui_contracts() -> io::Result<()> {
    let cases = trybuild::TestCases::new();
    cases.pass("tests/ui/pass/*.rs");
    cases.compile_fail("tests/ui/compile_fail/*.rs");

    for case in CLIPPY_CASES.iter().chain(RUSTDOC_CASES) {
        run_cargo_ui_case(case)?;
    }

    Ok(())
}

fn run_cargo_ui_case(case: &UiCase) -> io::Result<()> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let fixture_manifest = root.join("tests/ui/cases/Cargo.toml");
    let output = Command::new("cargo")
        .current_dir(root)
        .env("CLIPPY_CONF_DIR", root)
        .arg(case.command)
        .arg("--manifest-path")
        .arg(fixture_manifest)
        .args(case.target_args)
        .args(["--no-deps", "--color=never"])
        .output()?;

    assert_expected_failure(case, &output);
    Ok(())
}

fn assert_expected_failure(case: &UiCase, output: &Output) {
    let diagnostic = format!(
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(
        !output.status.success(),
        "UI case {} should fail, but succeeded:\n{diagnostic}",
        case.target
    );
    for expected in case.expected.lines().filter(|line| !line.is_empty()) {
        assert!(
            diagnostic.contains(expected),
            "UI case {} should contain reviewed diagnostic {expected:?}:\n{diagnostic}",
            case.target
        );
    }
}
