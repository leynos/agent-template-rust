"""Build hermetic subprocess environments for generated-project commands."""

from __future__ import annotations

import os
from collections.abc import Mapping

MAKE_RESOLUTION_VARIABLES = frozenset(
    {
        "WHITAKER",
        "GNUMAKEFLAGS",
        "MAKEFLAGS",
        "MFLAGS",
        "MAKELEVEL",
    }
)


def generated_project_env(overrides: Mapping[str, str]) -> dict[str, str]:
    """Return an environment for hermetic generated-project make invocations.

    The returned copy strips make and Whitaker resolution controls inherited
    from the parent process before applying caller-provided overrides.

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
    for variable in MAKE_RESOLUTION_VARIABLES:
        env.pop(variable, None)
    env.update(overrides)
    return env
