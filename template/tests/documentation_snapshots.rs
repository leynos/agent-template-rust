//! Semantic documentation snapshot tests.

use serde_json::Value;

fn parse_markdown_semantics(markdown: &str) -> Result<Value, Box<dyn std::error::Error>> {
    let tree = markdown::to_mdast(markdown, &markdown::ParseOptions::gfm())
        .map_err(|message| std::io::Error::other(message.to_string()))?;
    let mut value = serde_json::to_value(tree)?;
    normalise_node(&mut value);
    Ok(value)
}

fn normalise_node(value: &mut Value) {
    match value {
        Value::Object(object) => {
            let node_type = object
                .get("type")
                .and_then(Value::as_str)
                .map(str::to_owned);
            object.remove("position");
            object.remove("line");
            object.remove("column");
            object.remove("offset");

            if node_type.as_deref() == Some("text")
                && let Some(Value::String(text)) = object.get_mut("value")
            {
                *text = normalise_soft_text(text);
            }

            for child in object.values_mut() {
                normalise_node(child);
            }
        }
        Value::Array(children) => {
            for child in children {
                normalise_node(child);
            }
        }
        _ => {}
    }
}

fn normalise_soft_text(value: &str) -> String {
    value.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn parse_markdown_semantics_or_panic(markdown: &str) -> Value {
    match parse_markdown_semantics(markdown) {
        Ok(value) => value,
        Err(error) => panic!("failed to parse Markdown semantics: {error}"),
    }
}

#[test]
fn markdown_semantics_ignore_formatting_noise() {
    let compact = "\
# Documentation

The generated project links to [docs](docs/contents.md) and explains
the workflow in one paragraph.

| Path | Purpose |
| - | - |
| `docs/contents.md` | Index |

- [x] Keep snapshots semantic
";
    let reflowed = "\
# Documentation

The generated project links to [docs](docs/contents.md) and explains the
workflow in one paragraph.

| Path                 | Purpose |
| -------------------- | ------- |
| `docs/contents.md`   | Index   |

- [x] Keep snapshots semantic
";

    assert_eq!(
        parse_markdown_semantics_or_panic(compact),
        parse_markdown_semantics_or_panic(reflowed)
    );
}

#[test]
fn generated_documentation_matches_semantic_snapshots() {
    let repository_layout = include_str!("../docs/repository-layout.md");
    let repository_layout_snapshot = if repository_layout.contains(".github/workflows/release.yml")
    {
        "docs_repository_layout_app"
    } else {
        "docs_repository_layout_lib"
    };

    insta::assert_json_snapshot!(
        "docs_contents",
        parse_markdown_semantics_or_panic(include_str!("../docs/contents.md"))
    );
    insta::assert_json_snapshot!(
        repository_layout_snapshot,
        parse_markdown_semantics_or_panic(repository_layout)
    );
}
