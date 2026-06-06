"""Rendered audit target tests."""

from __future__ import annotations

from collections.abc import Callable
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pytest_copier.plugin import CopierFixture

from tests.helpers.rendering import render_project


def test_makefile_rust_audit_uses_workspace_metadata(
    tmp_path: Path,
    copier: CopierFixture,
    cargo_metadata_for: Callable[[Path, list[Path]], str],
    write_fake_cargo: Callable[..., Path],
) -> None:
    """Generated audit target audits the metadata workspace root once."""
    project = render_project(
        tmp_path,
        copier,
        project_name="AuditExample",
        package_name="audit_example",
    )
    for ignored in [
        project / "target" / "ignored" / "Cargo.toml",
        project / "node_modules" / "ignored" / "Cargo.toml",
        project / ".venv" / "ignored" / "Cargo.toml",
    ]:
        ignored.parent.mkdir(parents=True)
        ignored.write_text(
            '[package]\nname = "ignored"\nversion = "0.0.0"\n',
            encoding="utf-8",
        )
    log_path = project / "cargo-audit.log"
    fake_cargo = write_fake_cargo(
        project / "bin",
        log_path=log_path,
        metadata=cargo_metadata_for(project.path, [project / "Cargo.toml"]),
    )
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"

    result = subprocess.run(
        [make, "rust-audit", f"CARGO={fake_cargo}"],
        cwd=project.path,
        check=False,
        capture_output=True,
        text=True,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert f"Auditing Rust workspace {project.path}" in output, (
        "expected rust-audit to log the metadata-derived workspace root"
    )
    assert f"Workspace Rust manifest {project.path}/Cargo.toml" in output, (
        "expected rust-audit to log workspace member manifests"
    )
    log = log_path.read_text(encoding="utf-8")
    assert log == f"{project.path}|audit\n", (
        "expected cargo audit to run once from the workspace root"
    )
    assert "target/ignored" not in log, (
        "expected target manifests to be ignored when absent from metadata"
    )
    assert "node_modules/ignored" not in log, (
        "expected node_modules manifests to be ignored when absent from metadata"
    )
    assert ".venv/ignored" not in log, (
        "expected virtualenv manifests to be ignored when absent from metadata"
    )


def test_makefile_rust_audit_honours_documented_ignores(
    tmp_path: Path,
    copier: CopierFixture,
    cargo_metadata_for: Callable[[Path, list[Path]], str],
    write_fake_cargo: Callable[..., Path],
) -> None:
    """Generated audit target maps CARGO_AUDIT_IGNORES to cargo-audit flags."""
    project = render_project(
        tmp_path,
        copier,
        project_name="AuditIgnoresExample",
        package_name="audit_ignores_example",
    )
    log_path = project / "cargo-audit.log"
    fake_cargo = write_fake_cargo(
        project / "bin",
        log_path=log_path,
        metadata=cargo_metadata_for(project.path, [project / "Cargo.toml"]),
    )
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"

    result = subprocess.run(
        [make, "rust-audit", f"CARGO={fake_cargo}"],
        cwd=project.path,
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CARGO_AUDIT_IGNORES": "RUSTSEC-2017-0001 RUSTSEC-2024-9999",
        },
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert log_path.read_text(encoding="utf-8") == (
        f"{project.path}|audit --ignore RUSTSEC-2017-0001 "
        "--ignore RUSTSEC-2024-9999\n"
    ), "expected documented ignores to be passed as cargo-audit --ignore flags"


@pytest.mark.parametrize(
    ("audit_status", "metadata_status", "should_audit_run"),
    [
        (42, 0, True),
        (0, 23, False),
    ],
)
def test_makefile_rust_audit_propagates_failures(
    tmp_path: Path,
    copier: CopierFixture,
    cargo_metadata_for: Callable[[Path, list[Path]], str],
    write_fake_cargo: Callable[..., Path],
    audit_status: int,
    metadata_status: int,
    should_audit_run: bool,
) -> None:
    """Generated audit target propagates metadata and audit failures."""
    project = render_project(
        tmp_path,
        copier,
        project_name="AuditFailureExample",
        package_name="audit_failure_example",
    )
    log_path = project / "cargo-audit.log"
    fake_cargo = write_fake_cargo(
        project / "bin",
        log_path=log_path,
        metadata=cargo_metadata_for(project.path, [project / "Cargo.toml"]),
        audit_status=audit_status,
        metadata_status=metadata_status,
    )
    make = shutil.which("make")
    assert make is not None, "expected make to be available for generated tests"

    result = subprocess.run(
        [make, "rust-audit", f"CARGO={fake_cargo}"],
        cwd=project.path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0, (
        "expected rust-audit to propagate cargo failures: "
        f"stdout={result.stdout}, stderr={result.stderr}"
    )
    if should_audit_run:
        assert log_path.read_text(encoding="utf-8") == f"{project.path}|audit\n", (
            "expected cargo audit to run once when metadata succeeds"
        )
    else:
        assert not log_path.exists(), (
            "expected cargo audit not to run after metadata failure"
        )
