#![deny(missing_docs, warnings)]
#![forbid(unsafe_code)]
//! Supported generated-project code.

/// Return a stable value without ambient process state.
pub const fn supported_value() -> u8 {
    42
}

fn main() {
    assert_eq!(
        supported_value(),
        42,
        "supported generated-project code should compile"
    );
}
