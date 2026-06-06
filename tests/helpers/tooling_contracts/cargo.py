"""Assert rendered Cargo contracts for generated Rust projects."""

from __future__ import annotations

from typing import Any

from tests.helpers.rendering import APP


def _assert_cargo_package_contracts(
    package: dict[str, Any], metadata: dict[str, Any], flavour: str
) -> None:
    """Assert generated Cargo package metadata contracts."""
    assert package.get("description") == "ToolingExample package used by template tests.", (
        "expected generated Cargo.toml to include package description"
    )
    assert package.get("repository") == "https://github.com/example/tooling_example", (
        "expected generated Cargo.toml to include repository URL"
    )
    assert package.get("homepage") == "https://example.com/tooling_example", (
        "expected generated Cargo.toml to include homepage URL"
    )
    assert package.get("keywords") == ["rust", "template"], (
        "expected generated Cargo.toml to include package keywords"
    )
    assert package.get("categories") == ["development-tools"], (
        "expected generated Cargo.toml to include package categories"
    )
    assert package.get("license") == "ISC", (
        "expected generated Cargo.toml to include ISC licence"
    )

    if flavour == APP:
        binstall = metadata.get("binstall")
        assert isinstance(binstall, dict), (
            "expected app flavour Cargo.toml to include binstall metadata"
        )
        assert (
            binstall.get("pkg-url")
            == "https://github.com/example/tooling_example/releases/download/"
            "v{ version }/tooling_example-{ target }{ binary-ext }"
        ), "expected app flavour binstall metadata to include package URL"
        assert binstall.get("pkg-fmt") == "bin", (
            "expected app flavour binstall metadata to describe binary artifacts"
        )
        assert binstall.get("disabled-strategies") == ["quick-install", "compile"], (
            "expected app flavour binstall metadata to disable unsupported strategies"
        )
    else:
        assert "binstall" not in metadata, (
            "expected lib flavour Cargo.toml to omit binstall metadata"
        )


def _assert_cargo_config_contracts(
    cargo_config: str, dev_target: str, rust_toolchain: str
) -> None:
    """Assert generated Cargo config and toolchain contracts."""
    assert 'codegen-backend = "cranelift"' in cargo_config, (
        "expected generated cargo config to enable Cranelift"
    )
    if "linux" in dev_target:
        assert f"[target.{dev_target}]" in cargo_config, (
            "expected generated cargo config to include Linux target settings"
        )
        assert 'link-arg=-fuse-ld=mold' in cargo_config, (
            "expected generated cargo config to use mold linker for Linux"
        )
    else:
        assert f"[target.{dev_target}]" not in cargo_config, (
            "expected generated cargo config to avoid mold target blocks "
            "for non-Linux targets"
        )
        assert 'link-arg=-fuse-ld=mold' not in cargo_config, (
            "expected generated cargo config to avoid mold for non-Linux targets"
        )

    assert "rustc-codegen-cranelift-preview" in rust_toolchain, (
        "expected generated rust-toolchain to include Cranelift component"
    )
    assert "llvm-tools-preview" in rust_toolchain, (
        "expected generated rust-toolchain to include llvm tools component"
    )
