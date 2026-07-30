"""Validate the mutation-testing workflow contract helpers."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.helpers.tooling_contracts.mutation import (
    _MUTATION_CRON,
    _assert_mutation_workflow_contracts,
    _extract_apt_install_packages,
)


def test_extract_apt_install_packages_returns_non_flag_arguments() -> None:
    """Return install arguments across backslash continuations, dropping flags."""
    setup_commands = (
        "export DEBIAN_FRONTEND=noninteractive\n"
        "sudo apt-get update \\\n"
        "  && sudo apt-get install --yes --no-install-recommends clang lld mold\n"
    )

    assert _extract_apt_install_packages(setup_commands) == ["clang", "lld", "mold"], (
        "expected only the non-flag install arguments to be returned"
    )


def test_extract_apt_install_packages_ignores_commented_installs() -> None:
    """Skip commented-out install commands so they cannot satisfy the contract."""
    setup_commands = "# sudo apt-get install --yes clang lld mold\necho skip\n"

    assert _extract_apt_install_packages(setup_commands) == [], (
        "expected a commented-out apt-get install to be ignored"
    )


def test_extract_apt_install_packages_rejects_malformed_shell() -> None:
    """Surface malformed setup-commands shell instead of masking it as valid."""
    setup_commands = 'sudo apt-get install --yes "clang\n'

    with pytest.raises(AssertionError, match="parseable shell"):
        _extract_apt_install_packages(setup_commands)


def test_extract_apt_install_packages_ignores_echoed_marker() -> None:
    """Ignore an echo whose argument merely contains the install marker text."""
    setup_commands = 'echo "run apt-get install clang lld mold first"\n'

    assert _extract_apt_install_packages(setup_commands) == [], (
        "expected embedded marker text in an echo argument not to count as an "
        "install command"
    )


def test_extract_apt_install_packages_ignores_quoted_operator() -> None:
    """Treat a quoted operator as an argument, not a command separator."""
    setup_commands = "echo '&&' apt-get install clang lld mold\n"

    assert _extract_apt_install_packages(setup_commands) == [], (
        "expected a quoted '&&' to stay part of the echo command rather than "
        "separating a forged apt-get install"
    )


@pytest.mark.parametrize(
    "setup_commands",
    [
        "false && sudo apt-get install --yes clang lld mold || true\n",
        "false && sudo apt-get install --yes clang lld mold\n",
        "sudo apt-get install --yes clang lld mold || true\n",
        "sudo apt-get install --yes clang lld mold | true\n",
        "sudo apt-get install --yes clang lld mold &\n",
    ],
    ids=["guarded-and-fallback", "guarded", "fallback", "piped", "backgrounded"],
)
def test_extract_apt_install_packages_ignores_conditional_installs(
    setup_commands: str,
) -> None:
    """Ignore an install a guard may skip or whose failure is masked."""
    assert _extract_apt_install_packages(setup_commands) == [], (
        "expected an install reachable only through a guard, or whose exit "
        "status a fallback, pipeline, or background operator hides, not to "
        "satisfy the contract"
    )


# Shell-safe package tokens: a leading alphanumeric (so they never look like a
# flag) followed by characters valid in a Debian package name. Flag tokens
# always begin with ``--`` so the parser drops them.
_apt_package_tokens: st.SearchStrategy[str] = st.builds(
    lambda head, tail: head + tail,
    st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789+.-", max_size=11),
)
_apt_flag_tokens: st.SearchStrategy[str] = st.builds(
    lambda word: "--" + word,
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=12),
)
_apt_install_tokens: st.SearchStrategy[list[tuple[str, bool]]] = st.lists(
    st.one_of(
        st.tuples(_apt_package_tokens, st.just(False)),
        st.tuples(_apt_flag_tokens, st.just(True)),
    ),
    min_size=1,
    max_size=6,
)


@given(
    tagged=_apt_install_tokens,
    use_sudo=st.booleans(),
    indent=st.text(alphabet=" \t", max_size=3),
)
def test_extract_apt_install_packages_recovers_non_flag_arguments(
    tagged: list[tuple[str, bool]], use_sudo: bool, indent: str
) -> None:
    """Return exactly the non-flag install arguments, in order, dropping flags."""
    tokens = [token for token, _ in tagged]
    expected = [token for token, is_flag in tagged if not is_flag]
    prefix = "sudo " if use_sudo else ""
    setup_commands = (
        "export DEBIAN_FRONTEND=noninteractive\n"
        f"{indent}{prefix}apt-get install {' '.join(tokens)}\n"
    )

    assert _extract_apt_install_packages(setup_commands) == expected, (
        "expected every non-flag install argument, in order, and no flags"
    )


@given(
    packages=st.lists(_apt_package_tokens, min_size=1, max_size=5),
    indent=st.text(alphabet=" \t", max_size=3),
)
def test_extract_apt_install_packages_skips_commented_installs(
    packages: list[str], indent: str
) -> None:
    """A commented apt-get install line never contributes packages."""
    setup_commands = (
        f"{indent}# sudo apt-get install --yes {' '.join(packages)}\necho noop\n"
    )

    assert _extract_apt_install_packages(setup_commands) == [], (
        "expected a commented install line to contribute no packages"
    )


@given(packages=st.lists(_apt_package_tokens, min_size=1, max_size=4))
def test_extract_apt_install_packages_follows_line_continuations(
    packages: list[str],
) -> None:
    """Recover packages split onto a backslash-continued line."""
    setup_commands = f"sudo apt-get install --yes \\\n  {' '.join(packages)}\n"

    assert _extract_apt_install_packages(setup_commands) == packages, (
        "expected packages on a backslash-continued line to be recovered"
    )


def _mutation_workflow_with_schedule(schedule_block: str) -> str:
    """Build a mutation-testing workflow whose ``on`` reaches the schedule check."""
    return f'permissions: {{}}\n"on":\n{schedule_block}  workflow_dispatch:\n'


def test_assert_mutation_workflow_contracts_rejects_extra_schedule_entry() -> None:
    """Reject a second schedule entry beyond the single sanctioned cron."""
    workflow = _mutation_workflow_with_schedule(
        f'  schedule:\n    - cron: "{_MUTATION_CRON}"\n    - cron: "0 0 * * *"\n'
    )

    with pytest.raises(AssertionError, match="schedule to be exactly one cron entry"):
        _assert_mutation_workflow_contracts(workflow)


def test_assert_mutation_workflow_contracts_rejects_extra_schedule_key() -> None:
    """Reject an extra key smuggled into the single schedule entry."""
    workflow = _mutation_workflow_with_schedule(
        f'  schedule:\n    - cron: "{_MUTATION_CRON}"\n      branches: ["main"]\n'
    )

    with pytest.raises(AssertionError, match="schedule to be exactly one cron entry"):
        _assert_mutation_workflow_contracts(workflow)
