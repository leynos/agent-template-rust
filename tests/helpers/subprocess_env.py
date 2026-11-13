"""Build hermetic subprocess environments for generated-project commands.

``generated_project_env`` copies the parent environment, removes Make,
Whitaker and build-tool preflight control variables, and applies explicit
overrides before passing the result to subprocess calls. For example::

    subprocess.run(["make", "lint"], env=generated_project_env({"PATH": path}))
"""

from __future__ import annotations

import os
from collections.abc import Mapping

MAKE_RESOLUTION_VARIABLES: frozenset[str] = frozenset(
    {
        "WHITAKER",
        "CHECK_BUILD_TOOLS",
        "CHECK_RUST_TOOLCHAIN",
        "CHECK_COVERAGE_TOOLS",
        "GNUMAKEFLAGS",
        "MAKEFLAGS",
        "MFLAGS",
        "MAKELEVEL",
    }
)

# A non-interactive Bash sources ``BASH_ENV`` and a POSIX shell sources ``ENV``
# before running anything. A harness that exports either one would otherwise run
# its startup script inside every generated-project recipe, with the recipe's
# restricted ``PATH``: the script fails with a command-not-found of its own, and
# ``make`` reports the failure against whichever target happened to be running.
# Both are therefore stripped so a stubbed ``PATH`` reaches the recipe alone.
SHELL_STARTUP_VARIABLES: frozenset[str] = frozenset({"BASH_ENV", "ENV"})


def generated_project_env(overrides: Mapping[str, str]) -> dict[str, str]:
    """Return an environment for hermetic generated-project make invocations.

    The returned copy strips make and Whitaker resolution controls, and the
    shell startup files that would otherwise run inside each recipe, from the
    parent process before applying caller-provided overrides.

    Parameters
    ----------
    overrides : Mapping[str, str]
        Environment variables to set or replace after stripping resolution
        variables.

    Returns
    -------
    dict[str, str]
        A hermetic copy of the environment suitable for subprocess calls.
    """
    env = os.environ.copy()
    for variable in MAKE_RESOLUTION_VARIABLES | SHELL_STARTUP_VARIABLES:
        env.pop(variable, None)
    env.update(overrides)
    return env
