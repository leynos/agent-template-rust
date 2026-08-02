"""Validate direct helper-module error handling and edge cases."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests import utilities
from tests.helpers.generated_files import (
    parse_toml_file,
    parse_yaml_mapping,
    read_generated_text,
    require_mapping,
    require_optional_mapping,
    require_sequence,
)
from tests.helpers.rendering import read_generated_file
from tests.helpers.subprocess_env import (
    MAKE_RESOLUTION_VARIABLES,
    generated_project_env,
)
from tests.helpers.tooling_contracts import assert_ci_coverage_action_contract
from tests.helpers.tooling_contracts.workflows import (
    _disables_credential_persistence,
    _is_pinned_action,
    _step_mappings,
)
from tests.test_github_actions_integration import xfail_known_act_runtime_limitations
from tests.utilities import (
    _resolved_socket_from_docker_host,
    _user_podman_socket,
    container_daemon_socket,
    docker_environment,
)


def _json_collections(
    children: st.SearchStrategy[Any],
) -> st.SearchStrategy[Any]:
    """Extend a recursive JSON strategy with bounded list and dict collections."""
    return st.lists(children, max_size=4) | st.dictionaries(
        st.text(), children, max_size=4
    )


json_value = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    _json_collections,
    max_leaves=12,
)


environment_value: st.SearchStrategy[str] = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=12,
)

generated_project_overrides: st.SearchStrategy[dict[str, str]] = st.dictionaries(
    st.sampled_from(("PATH", "CARGO", "WHITAKER", "OVERRIDE_VARIABLE")),
    environment_value,
    max_size=4,
)


def test_generated_project_env_strips_resolution_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove inherited Make controls without changing the parent environment."""
    inherited_controls = {
        variable: f"inherited-{variable.lower()}"
        for variable in MAKE_RESOLUTION_VARIABLES
    }
    for variable, value in inherited_controls.items():
        monkeypatch.setenv(variable, value)
    monkeypatch.setenv("ORDINARY_VARIABLE", "preserved")
    monkeypatch.setenv("PATH", "inherited-path")
    monkeypatch.setenv("CARGO", "inherited-cargo")

    overrides = {
        "PATH": "controlled-path",
        "CARGO": "cargo",
        "WHITAKER": "explicit-whitaker",
    }
    env = generated_project_env(overrides)

    expected_absent = MAKE_RESOLUTION_VARIABLES - {"WHITAKER"}
    assert all(variable not in env for variable in expected_absent), (
        "expected inherited resolution controls to be absent; "
        f"variables={sorted(expected_absent)}, overrides={overrides}, env={env}"
    )
    assert env.get("ORDINARY_VARIABLE") == "preserved", (
        "expected ORDINARY_VARIABLE='preserved'; "
        f"actual={env.get('ORDINARY_VARIABLE')!r}, overrides={overrides}"
    )
    assert env.get("PATH") == "controlled-path", (
        "expected PATH='controlled-path'; "
        f"actual={env.get('PATH')!r}, overrides={overrides}"
    )
    assert env.get("CARGO") == "cargo", (
        f"expected CARGO='cargo'; actual={env.get('CARGO')!r}, overrides={overrides}"
    )
    assert env.get("WHITAKER") == "explicit-whitaker", (
        "expected WHITAKER='explicit-whitaker'; "
        f"actual={env.get('WHITAKER')!r}, overrides={overrides}"
    )
    assert os.environ.get("PATH") == "inherited-path", (
        "expected parent PATH='inherited-path' to remain unchanged; "
        f"actual={os.environ.get('PATH')!r}, overrides={overrides}"
    )
    assert all(
        os.environ[variable] == value for variable, value in inherited_controls.items()
    ), (
        "expected inherited resolution controls to remain unchanged in os.environ; "
        f"expected={inherited_controls}, overrides={overrides}"
    )
    assert os.environ.get("CARGO") == "inherited-cargo", (
        "expected parent CARGO='inherited-cargo' to remain unchanged; "
        f"actual={os.environ.get('CARGO')!r}, overrides={overrides}"
    )


@given(
    parent_value=environment_value,
    overrides=generated_project_overrides,
)
@settings(
    max_examples=20,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_generated_project_env_properties(
    monkeypatch: pytest.MonkeyPatch,
    parent_value: str,
    overrides: dict[str, str],
) -> None:
    """Preserve subprocess environment invariants for arbitrary overrides."""
    inherited_controls = {
        variable: f"control-{variable.lower()}-{parent_value}"
        for variable in MAKE_RESOLUTION_VARIABLES
    }
    for variable, value in inherited_controls.items():
        monkeypatch.setenv(variable, value)
    ordinary_value = f"ordinary-{parent_value}"
    parent_path = f"parent-path-{parent_value}"
    parent_cargo = f"parent-cargo-{parent_value}"
    monkeypatch.setenv("ORDINARY_VARIABLE", ordinary_value)
    monkeypatch.setenv("PATH", parent_path)
    monkeypatch.setenv("CARGO", parent_cargo)

    env = generated_project_env(overrides)

    for variable in MAKE_RESOLUTION_VARIABLES:
        if variable in overrides:
            assert env.get(variable) == overrides[variable], (
                f"expected override {variable}={overrides[variable]!r}; "
                f"actual={env.get(variable)!r}, overrides={overrides}"
            )
        else:
            assert variable not in env, (
                f"expected inherited control {variable} to be absent; "
                f"actual={env.get(variable)!r}, overrides={overrides}"
            )
    for variable, value in overrides.items():
        assert env.get(variable) == value, (
            f"expected override {variable}={value!r}; "
            f"actual={env.get(variable)!r}, overrides={overrides}"
        )
    if "CARGO" not in overrides:
        assert env.get("CARGO") == parent_cargo, (
            f"expected inherited CARGO={parent_cargo!r}; "
            f"actual={env.get('CARGO')!r}, overrides={overrides}"
        )
    assert env.get("ORDINARY_VARIABLE") == ordinary_value, (
        f"expected ORDINARY_VARIABLE={ordinary_value!r}; "
        f"actual={env.get('ORDINARY_VARIABLE')!r}, overrides={overrides}"
    )
    assert os.environ.get("PATH") == parent_path, (
        f"expected parent PATH={parent_path!r} to remain unchanged; "
        f"actual={os.environ.get('PATH')!r}, overrides={overrides}"
    )
    assert all(
        os.environ[variable] == value for variable, value in inherited_controls.items()
    ), (
        "expected inherited controls to remain unchanged in os.environ; "
        f"expected={inherited_controls}, overrides={overrides}"
    )

    monkeypatch.setenv("ORDINARY_VARIABLE", "parent-after")
    env["ORDINARY_VARIABLE"] = "child-after"

    assert os.environ.get("ORDINARY_VARIABLE") == "parent-after", (
        "expected parent ORDINARY_VARIABLE='parent-after'; "
        f"actual={os.environ.get('ORDINARY_VARIABLE')!r}, overrides={overrides}"
    )
    assert env.get("ORDINARY_VARIABLE") == "child-after", (
        "expected child ORDINARY_VARIABLE='child-after'; "
        f"actual={env.get('ORDINARY_VARIABLE')!r}, overrides={overrides}"
    )


def test_generated_project_env_returns_independent_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the generated subprocess environment independent of its parent."""
    monkeypatch.setenv("ORDINARY_VARIABLE", "before")

    env = generated_project_env({})
    monkeypatch.setenv("ORDINARY_VARIABLE", "after")
    env["ORDINARY_VARIABLE"] = "changed"

    assert env["ORDINARY_VARIABLE"] == "changed"
    assert os.environ["ORDINARY_VARIABLE"] == "after"


def test_read_generated_text_converts_os_errors(tmp_path: Path) -> None:
    """Convert generated-file read errors into pytest failures."""
    missing_path = tmp_path / "nonexistent_generated.txt"

    with pytest.raises(pytest.fail.Exception, match="could not read generated file"):
        read_generated_text(missing_path)


def test_parse_toml_file_reports_decode_errors(tmp_path: Path) -> None:
    """Convert generated TOML decode errors into pytest failures."""
    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text("[package\nname = 'broken'\n", encoding="utf-8")

    with pytest.raises(pytest.fail.Exception, match="could not parse generated TOML"):
        parse_toml_file(cargo_toml)


def test_parse_yaml_mapping_reports_invalid_yaml() -> None:
    """Convert generated YAML parser errors into pytest failures."""
    with pytest.raises(pytest.fail.Exception, match="could not parse generated CI"):
        parse_yaml_mapping("jobs: [unterminated", "CI")


def test_parse_yaml_mapping_requires_mapping_root() -> None:
    """Reject generated YAML documents that do not parse to mappings."""
    with pytest.raises(
        pytest.fail.Exception,
        match="expected generated CI workflow to parse as a mapping",
    ):
        parse_yaml_mapping("- lint\n- test\n", "CI workflow")


def test_generated_file_schema_helpers_require_expected_shapes() -> None:
    """Fail with schema-path context for wrong nested value shapes."""
    mapping: dict[str, Any] = {
        "jobs": {"build-test": {}},
        "steps": [{"name": "Check"}],
    }

    assert require_mapping(mapping, "jobs", "CI workflow") == {"build-test": {}}, (
        "expected require_mapping(mapping, 'jobs', 'CI workflow') to return jobs"
    )
    assert require_optional_mapping(mapping, "missing", "CI workflow") == {}, (
        "expected absent optional mappings to become empty mappings"
    )
    assert require_sequence(mapping, "steps", "CI build-test job") == [
        {"name": "Check"}
    ], "expected require_sequence to return the steps list"

    with pytest.raises(
        pytest.fail.Exception,
        match="expected CI workflow to include mapping key 'jobs'",
    ):
        require_mapping({"jobs": []}, "jobs", "CI workflow")

    with pytest.raises(
        pytest.fail.Exception,
        match="expected CI workflow key 'metadata' to be a mapping when present",
    ):
        require_optional_mapping({"metadata": []}, "metadata", "CI workflow")

    with pytest.raises(
        pytest.fail.Exception,
        match="expected CI build-test job to include sequence key 'steps'",
    ):
        require_sequence({"steps": {}}, "steps", "CI build-test job")


@given(key=st.text(min_size=1), value=json_value)
def test_require_mapping_property(key: str, value: object) -> None:
    """Round-trip mappings and reject non-mappings for required mapping keys."""
    mapping = {key: value}

    if isinstance(value, dict):
        assert require_mapping(mapping, key, "generated schema") == value
    else:
        with pytest.raises(pytest.fail.Exception):
            require_mapping(mapping, key, "generated schema")


@given(key=st.text(min_size=1), value=json_value)
def test_require_optional_mapping_property(key: str, value: object) -> None:
    """Return optional mappings, default missing keys, and reject wrong shapes."""
    assert require_optional_mapping({}, key, "generated schema") == {}
    mapping = {key: value}

    if isinstance(value, dict):
        assert require_optional_mapping(mapping, key, "generated schema") == value
    else:
        with pytest.raises(pytest.fail.Exception):
            require_optional_mapping(mapping, key, "generated schema")


@given(key=st.text(min_size=1), value=json_value)
def test_require_sequence_property(key: str, value: object) -> None:
    """Round-trip lists and reject non-lists for required sequence keys."""
    mapping = {key: value}

    if isinstance(value, list):
        assert require_sequence(mapping, key, "generated schema") == value
    else:
        with pytest.raises(pytest.fail.Exception):
            require_sequence(mapping, key, "generated schema")


_HEX_ALPHABET = "0123456789abcdef"
_action_paths = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/-._",
    min_size=1,
    max_size=30,
)
_full_shas = st.text(alphabet=_HEX_ALPHABET, min_size=40, max_size=40)


# Focused strategies for refs that are never a 40-character lowercase-hex SHA,
# composed into ``_non_sha_refs`` below.
_too_short_hex_refs: st.SearchStrategy[str] = st.text(
    alphabet=_HEX_ALPHABET, min_size=0, max_size=39
)
_too_long_hex_refs: st.SearchStrategy[str] = st.text(
    alphabet=_HEX_ALPHABET, min_size=41, max_size=64
)
_branch_refs: st.SearchStrategy[str] = st.sampled_from(
    ("main", "master", "rolling", "HEAD", "v1.2.3")
)


@st.composite
def _uppercased_hex_refs(draw: st.DrawFn) -> str:
    """Draw a 40-character hex ref carrying at least one uppercase digit."""
    hexes = draw(st.text(alphabet=_HEX_ALPHABET, min_size=40, max_size=40))
    position = draw(st.integers(min_value=0, max_value=39))
    existing = hexes[position]
    # Uppercasing a hex digit is a no-op, so fall back to a hex letter to keep
    # the ref out of the lowercase-hex SHA shape.
    flipped = (
        existing.upper() if existing.isalpha() else draw(st.sampled_from("ABCDEF"))
    )
    return f"{hexes[:position]}{flipped}{hexes[position + 1 :]}"


_non_sha_refs: st.SearchStrategy[str] = st.one_of(
    _too_short_hex_refs,
    _too_long_hex_refs,
    _uppercased_hex_refs(),
    _branch_refs,
)


@given(path=_action_paths, sha=_full_shas)
def test_is_pinned_action_accepts_full_sha(path: str, sha: str) -> None:
    """A path pinned to a 40-hex SHA matches only that exact action path."""
    assert _is_pinned_action(f"{path}@{sha}", path), (
        "expected a full 40-hex SHA pin to match its exact action path"
    )
    assert not _is_pinned_action(f"{path}@{sha}", f"{path}-other"), (
        "expected a pinned ref to be rejected for a mismatched action path"
    )


@given(path=_action_paths, ref=_non_sha_refs)
def test_is_pinned_action_rejects_non_sha_refs(path: str, ref: str) -> None:
    """Refs that are not a full 40-hex commit SHA are never treated as pinned."""
    assert not _is_pinned_action(f"{path}@{ref}", path), (
        "expected a ref that is not a full 40-hex commit SHA to be unpinned"
    )


_json_steps = st.lists(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.text(),
        st.lists(json_value, max_size=3),
        st.dictionaries(st.text(max_size=5), json_value, max_size=3),
    ),
    max_size=6,
)


@given(steps=_json_steps)
def test_step_mappings_keeps_only_mappings_in_order(steps: list[object]) -> None:
    """``_step_mappings`` returns exactly the mapping entries, in original order."""
    result = _step_mappings(steps)

    assert result == [step for step in steps if isinstance(step, dict)], (
        "expected only mapping steps, preserved in their original order"
    )
    assert all(isinstance(step, dict) for step in result), (
        "expected every returned step to be a mapping"
    )


_persist_credential_values = st.sampled_from([True, False, None, 0, 1, "false", "true"])


def _with_persist_credentials(base: dict[str, Any], value: object) -> dict[str, Any]:
    """Add a ``persist-credentials`` entry to a generated ``with`` mapping."""
    return {**base, "persist-credentials": value}


_with_blocks = st.one_of(
    st.none(),
    st.text(),
    st.integers(),
    st.dictionaries(st.text(min_size=1, max_size=5), json_value, max_size=3),
    st.builds(
        _with_persist_credentials,
        st.dictionaries(st.text(min_size=1, max_size=5), json_value, max_size=2),
        _persist_credential_values,
    ),
)


@st.composite
def _checkout_like_steps(draw: st.DrawFn) -> dict[str, object]:
    """Draw checkout-like steps with and without a ``with`` block."""
    if draw(st.booleans()):
        return {"with": draw(_with_blocks)}
    return {}


@given(step=_checkout_like_steps())
def test_disables_credential_persistence_matches_spec(step: dict[str, object]) -> None:
    """Only a ``with`` mapping whose persist-credentials is exactly False qualifies."""
    with_block = step.get("with")
    expected = (
        isinstance(with_block, dict) and with_block.get("persist-credentials") is False
    )

    assert _disables_credential_persistence(step) is expected, (
        "expected the credential-persistence verdict to match the with-block spec"
    )


def test_read_generated_file_uses_shared_error_contract(tmp_path: Path) -> None:
    """Read rendered files through the shared generated-file helper contract."""
    generated = tmp_path / "docs" / "users-guide.md"
    generated.parent.mkdir()
    generated.write_text("generated docs\n", encoding="utf-8")
    project = cast("Any", tmp_path)

    assert read_generated_file(project, "docs/users-guide.md") == "generated docs\n", (
        "expected read_generated_file(project, 'docs/users-guide.md') to return text"
    )
    with pytest.raises(pytest.fail.Exception, match="could not read generated file"):
        read_generated_file(project, "missing.md")


def test_ci_coverage_action_contract_validates_edges() -> None:
    """Validate CI coverage action edge cases."""
    assert_ci_coverage_action_contract(
        _ci_workflow(
            persist_credentials="false",
            coverage_inputs=(
                "          output-path: lcov.info\n          format: lcov\n"
                "          with-ratchet: 'true'\n"
            ),
        )
    )

    with pytest.raises(
        AssertionError,
        match="expected CI coverage step to enable the coverage ratchet",
    ):
        assert_ci_coverage_action_contract(
            _ci_workflow(
                persist_credentials="false",
                coverage_inputs=(
                    "          output-path: lcov.info\n          format: lcov\n"
                ),
            )
        )

    with pytest.raises(
        AssertionError,
        match="expected CI checkout steps to disable credential persistence",
    ):
        assert_ci_coverage_action_contract(
            _ci_workflow(
                persist_credentials="true",
                coverage_inputs=(
                    "          output-path: lcov.info\n          format: lcov\n"
                ),
            )
        )

    with pytest.raises(AssertionError, match="expected CI coverage output path"):
        assert_ci_coverage_action_contract(
            _ci_workflow(
                persist_credentials="false",
                coverage_inputs=(
                    "          output-path: coverage.xml\n          format: lcov\n"
                ),
            )
        )

    with pytest.raises(
        AssertionError,
        match="expected CI coverage format to match the CodeScene upload",
    ):
        assert_ci_coverage_action_contract(
            _ci_workflow(
                persist_credentials="false",
                coverage_inputs=(
                    "          output-path: lcov.info\n          format: cobertura\n"
                ),
            )
        )


def test_act_runtime_limitations_xfail_node24_actions() -> None:
    """Xfail act logs that show unsupported node24 action metadata."""
    logs = (
        "act phase: workflow execution started\n"
        "Error: The runs.using key in action.yml must be one of: "
        "[composite docker node12 node16 node20], got node24\n"
    )

    with pytest.raises(pytest.xfail.Exception):
        xfail_known_act_runtime_limitations(logs)


@pytest.mark.parametrize(
    "docker_host",
    [
        "",
        "nonsense",
        "tcp://127.0.0.1:2375",
        "http://localhost",
        "unix://",
        "unix:///etc/docker.sock",
    ],
)
def test_resolved_socket_from_docker_host_rejects_malformed_or_disallowed(
    docker_host: str, tmp_path: Path
) -> None:
    """Reject malformed, remote, empty, or disallowed Docker socket URLs."""
    allowed_dir = tmp_path / "run"
    allowed_dir.mkdir()

    assert _resolved_socket_from_docker_host(docker_host, (allowed_dir,)) is None


def test_resolved_socket_from_docker_host_accepts_allowed_unix_path(
    tmp_path: Path,
) -> None:
    """Accept normalized unix socket paths under configured allowed roots."""
    allowed_dir = tmp_path / "run"
    allowed_dir.mkdir()
    socket_path = allowed_dir / "docker.sock"

    assert (
        _resolved_socket_from_docker_host(f"unix://{socket_path}", (allowed_dir,))
        == socket_path
    ), f"expected normalized socket path {socket_path}"


def test_docker_environment_preserves_valid_unix_socket(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Preserve a valid unix Docker socket in the act subprocess environment."""
    allowed_dir = tmp_path / "run"
    allowed_dir.mkdir()
    socket_path = allowed_dir / "docker.sock"
    docker_host = f"unix://{socket_path}"
    monkeypatch.setenv("DOCKER_HOST", docker_host)
    monkeypatch.setattr(utilities, "local_socket_dirs", lambda: (allowed_dir,))

    assert docker_environment()["DOCKER_HOST"] == docker_host


def test_docker_environment_removes_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Do not pass inherited credentials to act subprocesses."""
    allowed_dir = tmp_path / "run"
    allowed_dir.mkdir()
    socket_path = allowed_dir / "docker.sock"
    monkeypatch.setenv("DOCKER_HOST", f"unix://{socket_path}")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.setenv("SOME_API_KEY", "api-key")
    monkeypatch.setattr(utilities, "local_socket_dirs", lambda: (allowed_dir,))

    env = docker_environment()

    assert env["DOCKER_HOST"] == f"unix://{socket_path}"
    assert "GITHUB_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "SOME_API_KEY" not in env


def test_docker_environment_drops_invalid_docker_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not leak unsupported Docker socket URLs into act subprocesses."""
    monkeypatch.setenv("DOCKER_HOST", "tcp://127.0.0.1:2375")

    assert "DOCKER_HOST" not in docker_environment()


def test_docker_environment_falls_back_to_user_podman_socket_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Set the per-user Podman socket when Docker does not provide a host."""
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    podman_socket = runtime_dir / "podman" / "podman.sock"
    podman_socket.parent.mkdir()
    podman_socket.touch()
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))

    assert docker_environment()["DOCKER_HOST"] == f"unix://{podman_socket}"


def test_user_podman_socket_uses_xdg_runtime_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Prefer XDG_RUNTIME_DIR for the user Podman socket path."""
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))

    assert _user_podman_socket() == runtime_dir / "podman" / "podman.sock"


def test_user_podman_socket_falls_back_to_run_user_uid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Derive a /run/user/$UID Podman socket path when XDG_RUNTIME_DIR is absent."""
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

    assert _user_podman_socket() == (
        Path("/run") / "user" / str(os.getuid()) / "podman" / "podman.sock"
    )


def test_container_daemon_socket_none_for_disallowed_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject disallowed Docker socket URLs for act container forwarding."""
    monkeypatch.setenv("DOCKER_HOST", "unix:///etc/docker.sock")

    assert container_daemon_socket() is None


def test_container_daemon_socket_uses_valid_docker_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Return a normalized unix URL for an allowed act daemon socket."""
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    socket_path = runtime_dir / "docker.sock"
    monkeypatch.setenv("DOCKER_HOST", f"unix://{socket_path}")
    monkeypatch.setattr(utilities, "user_runtime_socket_dirs", lambda: (runtime_dir,))

    assert container_daemon_socket() == f"unix://{socket_path}"


def test_container_daemon_socket_falls_back_to_user_podman_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Return the per-user Podman socket when DOCKER_HOST is unset."""
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))

    assert container_daemon_socket() == (
        f"unix://{runtime_dir / 'podman' / 'podman.sock'}"
    )


def test_parent_makefile_test_target_contract() -> None:
    """Validate the parent repository ``test`` target command contract."""
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert ".PHONY: help check-fmt fmt lint spelling typecheck test" in makefile, (
        "expected parent Makefile to mark all public gate targets phony"
    )
    assert "UV := $(shell command -v uvx 2>/dev/null)" in makefile, (
        "expected parent Makefile to resolve uvx before running tests"
    )
    assert "WITH_ACT ?= 0" in makefile, (
        "expected parent Makefile to default act validation off"
    )
    assert "RUN_ACT_VALIDATION=1" in makefile, (
        "expected parent Makefile to map WITH_ACT to act validation"
    )
    assert "uvx is required to run template tests" in makefile, (
        "expected parent Makefile test target to fail with a uvx installation message"
    )
    assert 'if [ -z "$(strip $(UV))" ]; then' in makefile, (
        "expected parent Makefile to check uvx inside the test recipe"
    )
    assert "$(error uvx is required" not in makefile, (
        "expected parent Makefile not to fail at parse time when uvx is missing"
    )
    assert ("$(ACT_TEST_ENV) $(UV) $(PYTEST_DEPS) pytest tests/") in makefile, (
        "expected parent Makefile test target to run pytest through $(UV) with "
        "the shared pytest dependency list"
    )
    assert "$(UV) --with ruff ruff format --check tests/" in makefile, (
        "expected parent Makefile check-fmt target to run ruff format checks"
    )
    assert "$(UV) --with ruff ruff check tests/" in makefile, (
        "expected parent Makefile lint target to run ruff lint checks"
    )
    assert "$(UV) --with mypy $(MYPY_DEPS) mypy tests/" in makefile, (
        "expected parent Makefile typecheck target to run mypy"
    )


def _ci_workflow(*, persist_credentials: str, coverage_inputs: str) -> str:
    """Return a minimal generated CI workflow for coverage-contract tests."""
    return f"""\
name: CI
jobs:
  build-test:
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: {persist_credentials}
      - name: Test and Measure Coverage
        uses: leynos/shared-actions/.github/actions/generate-coverage@0000000000000000000000000000000000000000
        with:
{coverage_inputs}"""
