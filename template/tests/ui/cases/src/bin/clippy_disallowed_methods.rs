//! Disallowed-environment-method UI fixture.

fn main() {
    let _deployment_mode = std::env::var("DEPLOYMENT_MODE");
}
