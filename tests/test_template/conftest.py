"""Shared fixtures for rendered template tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def cargo_metadata_for() -> Callable[[Path, list[Path]], str]:
    """Return a factory for minimal cargo metadata JSON."""

    def factory(workspace: Path, manifests: list[Path]) -> str:
        packages = ",".join(
            f'{{"id":"fixture {index}","manifest_path":"{manifest}"}}'
            for index, manifest in enumerate(manifests)
        )
        members = ",".join(
            f'"fixture {index}"' for index, _manifest in enumerate(manifests)
        )
        return (
            f'{{"workspace_root":"{workspace}",'
            f'"packages":[{packages}],"workspace_members":[{members}]}}'
        )

    return factory


@pytest.fixture
def write_fake_cargo() -> Callable[..., Path]:
    """Return a factory that writes a fake cargo binary.

    ``Callable[..., Path]`` is intentional because the factory accepts
    keyword-only status overrides in addition to the required path arguments.
    """

    def factory(
        bin_dir: Path,
        *,
        log_path: Path,
        metadata: str,
        audit_status: int = 0,
        metadata_status: int = 0,
    ) -> Path:
        bin_dir.mkdir(parents=True, exist_ok=True)
        cargo_path = bin_dir / "cargo"
        cargo_path.write_text(
            "#!/usr/bin/env sh\n"
            'if [ "$1" = metadata ]; then\n'
            f"printf '%s\\n' '{metadata}'\n"
            f"exit {metadata_status}\n"
            "fi\n"
            'if [ "$1" = nextest ] && [ "$2" = --version ]; then\n'
            "exit 1\n"
            "fi\n"
            f"printf '%s|%s\\n' \"$PWD\" \"$*\" >> '{log_path}'\n"
            f"exit {audit_status}\n",
            encoding="utf-8",
        )
        cargo_path.chmod(0o755)
        return cargo_path

    return factory
