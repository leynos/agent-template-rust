"""Assert the rendered mutation-testing workflow contract.

The mutation job's pinned reusable-workflow SHA is asserted by shape, not by
exact value: Dependabot owns bumping it, so hard-coding a value here would make
the suite fail on every routine bump.
"""

from __future__ import annotations

import re
import shlex

from tests.helpers.generated_files import (
    parse_yaml_mapping,
    require_mapping,
    require_sequence,
)

_MUTATION_JOB_PERMISSIONS = {"contents": "read", "id-token": "write"}
_MUTATION_SETUP_PACKAGES = ("clang", "lld", "mold")
_MUTATION_REUSABLE_WORKFLOW = (
    "leynos/shared-actions/.github/workflows/mutation-cargo.yml"
)
_MUTATION_CRON = "15 9 * * *"
_MUTATION_CONCURRENCY_GROUP = "mutation-testing-${{ github.ref }}"

_SHELL_COMMAND_SEPARATORS = frozenset({"&&", "||", ";", "|", "&"})


def _split_shell_commands(tokens: list[str]) -> list[list[str]]:
    """Split a shell token stream into commands on shell control operators."""
    commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _SHELL_COMMAND_SEPARATORS:
            commands.append(current)
            current = []
        else:
            current.append(token)
    commands.append(current)
    return commands


def _apt_install_packages(command: list[str]) -> list[str] | None:
    """Return non-flag args of ``[sudo] apt-get install ...``, else ``None``."""
    words = command[1:] if command[:1] == ["sudo"] else command
    if words[:2] != ["apt-get", "install"]:
        return None
    return [arg for arg in words[2:] if not arg.startswith("-")]


def _extract_apt_install_packages(setup_commands: str) -> list[str]:
    """Return the packages installed by a setup-commands ``apt-get install``."""
    # Join backslash continuations so each command sits on one logical line.
    joined = setup_commands.replace("\\\n", " ")
    for line in joined.splitlines():
        # Surface malformed shell instead of masking it as a valid install; a
        # setup-commands script that cannot be parsed is not runnable.
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError as error:
            raise AssertionError(
                "expected mutation job setup-commands to be parseable shell, "
                f"got {line!r}"
            ) from error
        # Only a real `[sudo] apt-get install` command counts; embedded text
        # such as an echo argument must never be treated as an install.
        for command in _split_shell_commands(tokens):
            packages = _apt_install_packages(command)
            if packages is not None:
                return packages
    return []


def _assert_mutation_workflow_contracts(mutation_workflow: str) -> None:
    """Assert generated mutation-testing workflow contracts."""
    parsed = parse_yaml_mapping(mutation_workflow, "mutation-testing workflow")
    assert parsed.get("permissions") == {}, (
        "expected mutation-testing workflow root permissions to grant no scopes"
    )
    triggers = require_mapping(parsed, "on", "mutation-testing workflow")
    assert set(triggers) == {"schedule", "workflow_dispatch"}, (
        "expected mutation-testing workflow to trigger only on schedule and "
        "workflow_dispatch, rejecting push or pull-request runs"
    )
    schedule = require_sequence(triggers, "schedule", "mutation-testing workflow on")
    assert schedule == [{"cron": _MUTATION_CRON}], (
        "expected mutation-testing workflow on.schedule to be exactly one cron "
        f"entry {_MUTATION_CRON!r}"
    )
    assert "workflow_dispatch" in triggers, (
        "expected mutation-testing workflow to support manual workflow_dispatch"
    )
    concurrency = require_mapping(parsed, "concurrency", "mutation-testing workflow")
    assert concurrency.get("group") == _MUTATION_CONCURRENCY_GROUP, (
        "expected mutation-testing workflow concurrency group "
        f"{_MUTATION_CONCURRENCY_GROUP!r}"
    )
    assert concurrency.get("cancel-in-progress") is False, (
        "expected mutation-testing workflow to queue runs "
        "(concurrency.cancel-in-progress: false)"
    )
    jobs = require_mapping(parsed, "jobs", "mutation-testing workflow")
    mutation = require_mapping(jobs, "mutation", "mutation-testing workflow jobs")
    mutation_uses = str(mutation.get("uses", ""))
    pinned_prefix = f"{_MUTATION_REUSABLE_WORKFLOW}@"
    assert mutation_uses.startswith(pinned_prefix), (
        "expected mutation job to call the shared mutation-cargo reusable workflow"
    )
    # The specific SHA is owned by Dependabot and deliberately not hard-coded, so
    # the contract survives dependency bumps while requiring an immutable pin.
    assert re.fullmatch(r"[0-9a-f]{40}", mutation_uses[len(pinned_prefix) :]), (
        "expected mutation job to pin the reusable workflow to a full commit SHA"
    )
    permissions = require_mapping(mutation, "permissions", "mutation job")
    assert permissions == _MUTATION_JOB_PERMISSIONS, (
        "expected mutation job permissions to stay scoped to "
        "contents: read and id-token: write"
    )
    inputs = require_mapping(mutation, "with", "mutation job")
    assert inputs.get("extra-args") == "--all-features", (
        "expected mutation job to mirror the CI --all-features test baseline"
    )
    setup_commands = inputs.get("setup-commands")
    assert isinstance(setup_commands, str), (
        "expected mutation job setup-commands to be a string"
    )
    installed_packages = _extract_apt_install_packages(setup_commands)
    assert installed_packages, (
        "expected mutation job setup-commands to install packages via apt-get"
    )
    for package in _MUTATION_SETUP_PACKAGES:
        assert package in installed_packages, (
            f"expected mutation job setup-commands apt-get install to include {package}"
        )
