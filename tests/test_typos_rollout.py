"""Tests for shared-base ``typos.toml`` generation and consumption."""

from __future__ import annotations

import importlib.util
import io
import email.message
import fcntl
import json
import os
import pathlib
import re
import shutil
import string
import subprocess  # noqa: S404 - runs the pinned, trusted typos binary via uv.
import sys
import tomllib
import typing as typ
import urllib.error

import pytest
from hypothesis import given
from hypothesis import strategies as st

if typ.TYPE_CHECKING:
    import types

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
SCRIPT_PATH = SCRIPTS_ROOT / "generate_typos_config.py"
COMMITTED_CONFIG = REPOSITORY_ROOT / "typos.toml"


class FakeHttpResponse(io.BytesIO):
    """Provide the response surface consumed by the rollout HTTP reader."""

    status = 200

    def __init__(self, content: bytes, headers: dict[str, str]) -> None:
        super().__init__(content)
        self.headers = headers

    def __enter__(self) -> FakeHttpResponse:
        return self

    def __exit__(self, *unused: object) -> None:
        self.close()


@pytest.fixture(name="generator", scope="module")
def generator_fixture() -> types.ModuleType:
    """Load the standalone generator with its neighbouring module visible."""
    sys.path.insert(0, str(SCRIPTS_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "generate_typos_config",
            SCRIPT_PATH,
        )
        assert spec is not None, "could not create generator module specification"
        assert spec.loader is not None, "generator module specification has no loader"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS_ROOT))
    return module


def dictionary_text(*, stem: str = "organ", accepted: str = "oxendict") -> str:
    """Return a minimal valid shared or local dictionary document."""
    return (
        "schema = 1\n\n[oxford]\n"
        f'stems = ["{stem}"]\n\n'
        f'[words]\naccepted = ["{accepted}"]\n\n'
        "[words.corrections]\n\n[patterns]\nignore = []\n\n"
        '[files]\nexclude = [".git"]\n'
    )


def prepare_repository(
    tmp_path: pathlib.Path,
    *,
    base_stem: str = "organ",
    local_stem: str = "custom",
) -> tuple[pathlib.Path, pathlib.Path]:
    """Create a repository root and local shared source for generation tests."""
    repository = tmp_path / "repository"
    repository.mkdir()
    source = tmp_path / "shared.toml"
    source.write_text(dictionary_text(stem=base_stem), encoding="utf-8")
    (repository / "typos.local.toml").write_text(
        dictionary_text(stem=local_stem, accepted="localword"),
        encoding="utf-8",
    )
    return repository, source


def test_main_refreshes_base_and_merges_local_overlay(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
) -> None:
    """Generation starts from the shared base and retains narrow local policy."""
    repository, source = prepare_repository(tmp_path)

    result = generator.main(repository=repository, source=source)
    rendered = (repository / "typos.toml").read_text(encoding="utf-8")
    parsed = tomllib.loads(rendered)
    words = parsed["default"]["extend-words"]

    assert result.status == "refreshed"
    assert words["organise"] == "organize"
    assert words["customise"] == "customize"
    assert words["localword"] == "localword"


@given(stem=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=16))
def test_oxford_mapping_property_covers_every_suffix_pair(
    generator: types.ModuleType,
    stem: str,
) -> None:
    """Every safe stem expands to correction and identity entries."""
    mappings = generator.rollout.generate_word_mappings(
        generator.rollout.Dictionary(stems=(stem,))
    )

    for plain_british, oxford in generator.rollout.SUFFIX_PAIRS:
        assert mappings[f"{stem}{plain_british}"] == f"{stem}{oxford}"
        assert mappings[f"{stem}{oxford}"] == f"{stem}{oxford}"


def test_main_does_not_replace_newer_valid_local_cache(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
) -> None:
    """An older shared copy cannot overwrite a newer untracked local cache."""
    repository, source = prepare_repository(tmp_path)
    generator.main(repository=repository, source=source)
    cache = repository / ".typos-oxendict-base.toml"
    cache.write_text(dictionary_text(stem="newer"), encoding="utf-8")
    os.utime(source, ns=(1_000_000_000, 1_000_000_000))
    os.utime(cache, ns=(2_000_000_000, 2_000_000_000))

    result = generator.main(repository=repository, source=source)

    assert result.status == "current"
    assert '"newerise" = "newerize"' in generator.render_config(repository)


def test_main_replaces_cache_from_different_authority(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
) -> None:
    """Switching the explicit source replaces an unrelated newer cache."""
    repository, first_source = prepare_repository(tmp_path)
    second_source = tmp_path / "second.toml"
    second_source.write_text(dictionary_text(stem="second"), encoding="utf-8")
    os.utime(first_source, ns=(3_000_000_000, 3_000_000_000))
    os.utime(second_source, ns=(1_000_000_000, 1_000_000_000))
    generator.main(repository=repository, source=first_source)

    result = generator.main(repository=repository, source=second_source)

    assert result.status == "refreshed"
    assert '"secondise" = "secondize"' in generator.render_config(repository)


def test_offline_generation_requires_then_reuses_valid_cache(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
) -> None:
    """Offline mode is safe after population and explicit before population."""
    repository, source = prepare_repository(tmp_path)

    with pytest.raises(FileNotFoundError, match="no cached shared dictionary"):
        generator.main(repository=repository, source=source, offline=True)

    generator.main(repository=repository, source=source)
    result = generator.main(repository=repository, source=source, offline=True)

    assert result.status == "offline-cache"


def test_oversized_local_dictionary_is_rejected_without_cache_mutation(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
) -> None:
    """Local sources over the fixed input limit never reach the cache."""
    repository, source = prepare_repository(tmp_path)
    source.write_bytes(b"x" * (generator.rollout.MAX_DICTIONARY_BYTES + 1))

    with pytest.raises(
        generator.rollout.DictionaryTooLargeError,
        match="dictionary declares",
    ):
        generator.main(repository=repository, source=source)

    assert not (repository / ".typos-oxendict-base.toml").exists()
    assert not (repository / ".typos-oxendict-base.json").exists()


@pytest.mark.parametrize(
    ("headers", "content", "message"),
    [
        ({"Content-Length": "1048577"}, b"", "dictionary declares"),
        ({}, b"x" * 1_048_577, "dictionary exceeds"),
    ],
    ids=["declared-size", "streamed-size"],
)
def test_oversized_http_dictionary_is_rejected_without_cache_mutation(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    headers: dict[str, str],
    content: bytes,
    message: str,
) -> None:
    """HTTP sources are bounded with and without Content-Length."""
    repository, _ = prepare_repository(tmp_path)
    response = FakeHttpResponse(content, headers)
    monkeypatch.setattr(
        generator.rollout.urllib.request,
        "urlopen",
        lambda *args, **kwargs: response,
    )

    with pytest.raises(generator.rollout.DictionaryTooLargeError, match=message):
        generator.main(repository=repository, source="https://example.invalid/base")

    assert not (repository / ".typos-oxendict-base.toml").exists()
    assert not (repository / ".typos-oxendict-base.json").exists()


def test_http_failure_reports_bounded_stale_cache_diagnostic(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A degraded HTTP refresh identifies status and cache age without its URL."""
    repository, source = prepare_repository(tmp_path)
    generator.main(repository=repository, source=source)
    monkeypatch.setattr(
        generator.rollout.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError(
                "https://secret.invalid/dictionary",
                503,
                "unavailable",
                email.message.Message(),
                None,
            )
        ),
    )

    with caplog.at_level("WARNING", logger=generator.rollout.__name__):
        result = generator.main(
            repository=repository,
            source="https://example.invalid/base",
        )

    assert result.status == "stale-cache"
    record = caplog.records[-1]
    assert record.levelname == "WARNING"
    assert "operation=https-refresh" in record.message
    assert "category=http" in record.message
    assert "status=503" in record.message
    assert "cache_age_seconds=" in record.message
    assert "secret.invalid" not in record.message
    assert "example.invalid" not in record.message


def test_metadata_failure_cleans_up_and_retries_changed_source(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An interrupted metadata write leaves valid cache state for a clean retry."""
    repository, source = prepare_repository(tmp_path)
    cache = repository / ".typos-oxendict-base.toml"
    metadata = repository / ".typos-oxendict-base.json"
    original_write_metadata = generator.rollout._write_metadata

    def fail_metadata(*args: object, **kwargs: object) -> None:
        raise OSError("simulated metadata failure")

    monkeypatch.setattr(generator.rollout, "_write_metadata", fail_metadata)
    with pytest.raises(OSError, match="simulated metadata failure"):
        generator.main(repository=repository, source=source)

    assert generator.rollout.load_dictionary(cache)
    assert not metadata.exists()
    temporary_files = [
        path
        for path in repository.glob(f".{cache.name}.*")
        if path.name != f"{cache.name}.lock"
    ]
    assert temporary_files == []

    monkeypatch.setattr(generator.rollout, "_write_metadata", original_write_metadata)
    source.write_text(dictionary_text(stem="retried"), encoding="utf-8")
    result = generator.main(repository=repository, source=source)

    assert result.status == "refreshed"
    assert metadata.exists()
    assert '"retriedise" = "retriedize"' in generator.render_config(repository)


def test_cache_lock_serializes_generator_processes(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
) -> None:
    """A second process waits for the cache owner and then refreshes cleanly."""
    repository, source = prepare_repository(tmp_path)
    cache = repository / ".typos-oxendict-base.toml"
    lock_path = cache.with_name(f"{cache.name}.lock")
    lock_path.touch()
    child_code = (
        "import pathlib, sys; "
        "sys.path.insert(0, sys.argv[1]); "
        "import generate_typos_config as generator; "
        "generator.main(repository=pathlib.Path(sys.argv[2]), "
        "source=pathlib.Path(sys.argv[3]))"
    )

    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        process = subprocess.Popen(  # noqa: S603 - argv contains trusted test paths.
            [
                sys.executable,
                "-c",
                child_code,
                str(SCRIPTS_ROOT),
                str(repository),
                str(source),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=0.2)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    stdout, stderr = process.communicate(timeout=10)
    assert process.returncode == 0, f"stdout={stdout}\nstderr={stderr}"
    assert generator.rollout.load_dictionary(cache)
    assert (repository / ".typos-oxendict-base.json").exists()


def test_rendered_config_is_deterministic_valid_toml(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
) -> None:
    """Rendered output is stable, parseable and has one trailing newline."""
    repository, source = prepare_repository(tmp_path)
    generator.main(repository=repository, source=source)

    first = generator.render_config(repository)
    second = generator.render_config(repository)

    assert first == second
    assert tomllib.loads(first)["default"]["locale"] == "en-gb"
    assert first.endswith("\n")
    assert not first.endswith("\n\n")


def test_committed_config_matches_current_shared_dictionary(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
) -> None:
    """The committed generated file has not drifted from shared and local data."""
    output = tmp_path / "typos.toml"

    generator.main(output)

    assert COMMITTED_CONFIG.read_text(encoding="utf-8") == output.read_text(
        encoding="utf-8"
    )
    tomllib.loads(output.read_text(encoding="utf-8"))


def _pinned_typos_version() -> str:
    """Read the Makefile's single source of truth for the typos version."""
    makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r"^TYPOS_VERSION\s*\?=\s*(\S+)", makefile, re.MULTILINE)
    assert match is not None, "TYPOS_VERSION not found in Makefile"
    return match.group(1)


@pytest.mark.slow
def test_generated_config_loads_in_pinned_typos(
    generator: types.ModuleType,
    tmp_path: pathlib.Path,
) -> None:
    """The real pinned binary enforces Oxford and British sample spellings."""
    uv_executable = shutil.which("uv")
    if uv_executable is None:
        pytest.skip("uv is unavailable to run the pinned typos binary")
    repository, source = prepare_repository(tmp_path)
    config = repository / "typos.toml"
    generator.main(repository=repository, source=source)
    sample = repository / "sample.md"
    sample.write_text(
        "The team will organise color output.\n",
        encoding="utf-8",
    )

    result = subprocess.run(  # noqa: S603 - argv contains trusted paths and literals.
        [
            uv_executable,
            "tool",
            "run",
            f"typos@{_pinned_typos_version()}",
            "--config",
            str(config),
            "--format",
            "json",
            str(sample),
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    corrections = {
        entry["typo"]: entry.get("corrections", [])
        for line in result.stdout.splitlines()
        for entry in (json.loads(line),)
        if entry.get("type") == "typo"
    }

    assert corrections.get("organise") == ["organize"]
    assert corrections.get("color") == ["colour"]
