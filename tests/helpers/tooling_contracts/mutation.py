"""Assert the rendered mutation-testing workflow contract.

The mutation job's pinned reusable-workflow SHA is asserted by shape, not by
exact value: Dependabot owns bumping it, so hard-coding a value here would make
the suite fail on every routine bump.
"""

from __future__ import annotations

import re
import shlex
from typing import NamedTuple

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

_SHELL_OPERATOR_CHARS = frozenset({"&", "|", ";"})
_QUOTE_CHARS = frozenset({"'", '"'})
# Operators that break the link between a command and the script's result: `||`
# runs what follows only when the command failed, `|` discards the command's
# exit status in favour of the last stage of the pipeline, and `&` detaches it.
_CONDITIONAL_TERMINATORS = frozenset({"||", "|", "&"})


class _ShellCommand(NamedTuple):
    """A shell command with the control operator that terminated it."""

    text: str
    terminator: str


def _is_comment_start(char: str, current: list[str]) -> bool:
    """Return whether an unquoted ``#`` here begins a trailing comment."""
    return char == "#" and (not current or current[-1].isspace())


def _consume_escape(line: str, index: int, current: list[str]) -> int:
    """Copy a backslash and the character it escapes; return the new index."""
    current.append(line[index])
    if index + 1 < len(line):
        index += 1
        current.append(line[index])
    return index


def _step_in_quotes(
    line: str, index: int, quote: str, current: list[str]
) -> tuple[int, str | None]:
    """Copy one quoted character; return the new index and quote state."""
    char = line[index]
    # Only double quotes honour backslash escapes; inside single quotes a
    # backslash is literal and so cannot hide the closing quote.
    if char == "\\" and quote == '"':
        return _consume_escape(line, index, current), quote
    current.append(char)
    return index, None if char == quote else quote


def _operator_end(line: str, index: int) -> int:
    """Return the index of the last character of a `&&` or `||` style operator."""
    paired = index + 1 < len(line) and line[index + 1] == line[index]
    return index + 1 if paired else index


def _split_shell_commands(line: str) -> list[_ShellCommand]:
    """Split a raw shell line into commands on its unquoted control operators."""
    # Splitting before `shlex` dequotes the line keeps a quoted operator, as in
    # `echo '&&' apt-get install clang`, inside its command rather than
    # separating one.
    commands: list[_ShellCommand] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote is not None:
            index, quote = _step_in_quotes(line, index, quote, current)
        elif char in _QUOTE_CHARS:
            quote = char
            current.append(char)
        elif char == "\\":
            index = _consume_escape(line, index, current)
        elif _is_comment_start(char, current):
            break
        elif char in _SHELL_OPERATOR_CHARS:
            end = _operator_end(line, index)
            commands.append(_ShellCommand("".join(current), line[index : end + 1]))
            current = []
            index = end
        else:
            current.append(char)
        index += 1
    commands.append(_ShellCommand("".join(current), ""))
    return commands


def _apt_install_packages(command: list[str]) -> list[str] | None:
    """Return non-flag args of ``[sudo] apt-get install ...``, else ``None``."""
    words = command[1:] if command[:1] == ["sudo"] else command
    if words[:2] != ["apt-get", "install"]:
        return None
    return [arg for arg in words[2:] if not arg.startswith("-")]


def _is_approved_prefix_command(tokens: list[str]) -> bool:
    """Return whether a command may precede the install in an operator chain."""
    # Deliberately narrow: only the preparation the template itself performs.
    # Anything else (`false`, `test ...`) could gate the install, so the
    # contract fails closed rather than trusting an unrecognized guard.
    words = tokens[1:] if tokens[:1] == ["sudo"] else tokens
    if not words or words[0] == "export":
        return True
    return words[:2] == ["apt-get", "update"]


def _install_runs_unconditionally(
    commands: list[_ShellCommand], tokenized: list[list[str]], index: int
) -> bool:
    """Return whether the install at ``index`` runs without a guard or fallback."""
    if commands[index].terminator in _CONDITIONAL_TERMINATORS:
        return False
    return all(
        commands[position].terminator not in _CONDITIONAL_TERMINATORS
        and _is_approved_prefix_command(tokenized[position])
        for position in range(index)
    )


def _tokenize_command(command: str) -> list[str]:
    """Tokenize one command, failing the contract on unparseable shell."""
    # Surface malformed shell instead of masking it as a valid install; a
    # setup-commands script that cannot be parsed is not runnable.
    try:
        return shlex.split(command)
    except ValueError as error:
        raise AssertionError(
            f"expected mutation job setup-commands to be parseable shell, got {command!r}"
        ) from error


def _extract_apt_install_packages(setup_commands: str) -> list[str]:
    """Return the packages installed by a setup-commands ``apt-get install``."""
    # Join backslash continuations so each command sits on one logical line.
    joined = setup_commands.replace("\\\n", " ")
    for line in joined.splitlines():
        # Split on operators before dequoting, so quoted text cannot forge a
        # command boundary; comments are dropped by the same quote-aware scan.
        commands = _split_shell_commands(line)
        tokenized = [_tokenize_command(command.text) for command in commands]
        for index, tokens in enumerate(tokenized):
            # Only a real `[sudo] apt-get install` counts, and only when the
            # whole operator chain reaches it: echoed text, a `false &&` guard,
            # a `|| true` fallback, a `| true` pipeline, and a backgrounded `&`
            # are all rejected.
            packages = _apt_install_packages(tokens)
            if packages is not None and _install_runs_unconditionally(
                commands, tokenized, index
            ):
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
