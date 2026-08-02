//! Missing-assert-message UI fixture.

fn main() {
    let executable = std::env::args().next().unwrap_or_default();
    assert!(!executable.is_empty());
}
