"""Assert the generated CodeScene publisher's token, guard and queue shape.

The generated ``coverage-main.yml`` is the only CodeScene caller. Its upload
is ``upload-codescene-coverage``, a composite action whose nested steps
inherit the calling step's ``env``, so the token is bound in no ``env`` at
all. A check step publishes only whether the token exists, the upload's guard
reads that output beside the main-ref guard, and the upload takes the token
directly as its ``access-token`` input.

The positive half matters as much as the prohibition: deleting the token
keeps every ``env`` clean while the upload skips forever, so the token's
sites are held to exactly the check's command and the upload's input.
"""

from __future__ import annotations

import collections.abc as cabc
from typing import Any

#: The check step's one command. GitHub evaluates the expression before it
#: sends the command to the runner, so the shell receives only ``true`` or
#: ``false``.
CHECK_COMMAND = (
    'echo "available=${{ secrets.CS_ACCESS_TOKEN != \'\' }}" >> "$GITHUB_OUTPUT"'
)
CHECK_ID = "codescene_token"
AVAILABLE_CONJUNCT = f"steps.{CHECK_ID}.outputs.available == 'true'"
MAIN_REF_CONJUNCT = "github.ref == 'refs/heads/main'"
UPLOAD_CREDENTIAL_INPUT = "${{ secrets.CS_ACCESS_TOKEN }}"
PUBLISHER_GROUP = "coverage-main-${{ github.ref }}"
#: Expression contexts are case-insensitive, so every search folds case.
CREDENTIAL_NAME = "cs_access_token"


def _located_strings(value: object, path: str) -> cabc.Iterator[tuple[str, str]]:
    """Yield every string in a parsed YAML value with the path that reached it.

    Parameters
    ----------
    value : object
        A parsed workflow fragment.
    path : str
        The path taken to reach it.

    Yields
    ------
    tuple[str, str]
        The path and the string found there; a mapping key is reported at the
        path of the entry it names.

    Examples
    --------
    >>> list(_located_strings({"env": {"T": "x"}}, "job"))
    [('job.env', 'env'), ('job.env.T', 'T'), ('job.env.T', 'x')]
    """
    match value:
        case str():
            yield path, value
        case dict():
            for key, item in value.items():
                child = f"{path}.{key}" if path else str(key)
                if isinstance(key, str):
                    yield child, key
                yield from _located_strings(item, child)
        case list():
            for index, item in enumerate(value):
                yield from _located_strings(item, f"{path}[{index}]")
        case _:
            return


def credential_sites(workflow: dict[str, Any]) -> list[str]:
    """Return the path of every string naming the token, sorted and unique.

    Parameters
    ----------
    workflow : dict[str, Any]
        A parsed workflow.

    Returns
    -------
    list[str]
        Each path once, such as ``jobs.up.steps[1].with.access-token``.

    Examples
    --------
    >>> credential_sites({"jobs": {"up": {"env": {"T": "${{ secrets.cs_access_token }}"}}}})
    ['jobs.up.env.T']
    """
    return sorted(
        {
            path
            for path, text in _located_strings(workflow, "")
            if CREDENTIAL_NAME in text.casefold()
        }
    )


def _is_upload(step: dict[str, Any]) -> bool:
    """Return whether a step calls the CodeScene uploader."""
    return "upload-codescene-coverage" in str(step.get("uses", ""))


def _publisher_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the mapping-shaped steps of the ``coverage-upload`` job."""
    job = workflow["jobs"]["coverage-upload"]
    return [step for step in job.get("steps", []) if isinstance(step, dict)]


def assert_check_step(workflow: dict[str, Any]) -> None:
    """Assert one exact, unconditional, unbound check precedes the upload."""
    steps = _publisher_steps(workflow)
    checks = [step for step in steps if step.get("id") == CHECK_ID]
    uploads = [step for step in steps if _is_upload(step)]
    assert len(checks) == 1, f"expected one {CHECK_ID!r} step, found {len(checks)}"
    assert len(uploads) == 1, f"expected one CodeScene upload, found {len(uploads)}"
    check = checks[0]
    assert str(check.get("run", "")).strip() == CHECK_COMMAND, check.get("run")
    assert "if" not in check, "expected the token check to run unconditionally"
    assert "env" not in check, "expected the token check to declare no env"
    assert steps.index(check) < steps.index(uploads[0]), (
        "expected the token check to run before the upload that reads it"
    )


def assert_upload_step(workflow: dict[str, Any]) -> None:
    """Assert the upload reads the check and the ref, and takes the token."""
    (upload,) = [step for step in _publisher_steps(workflow) if _is_upload(step)]
    condition = str(upload.get("if", ""))
    assert "||" not in condition, f"expected no disjunction in {condition!r}"
    conjuncts = [part.strip() for part in condition.split("&&")]
    for required in (AVAILABLE_CONJUNCT, MAIN_REF_CONJUNCT):
        assert required in conjuncts, f"expected {required!r} in {condition!r}"
    inputs = upload.get("with") or {}
    assert inputs.get("access-token") == UPLOAD_CREDENTIAL_INPUT, inputs
    assert inputs.get("mode") == "upload", inputs
    assert "installer-checksum" not in inputs, (
        "expected no installer-checksum; the uploader rejects a non-empty value"
    )


def assert_token_sites(workflow: dict[str, Any]) -> None:
    """Assert the token is named at the check's command and the input only."""
    steps = _publisher_steps(workflow)
    check_at = next(i for i, step in enumerate(steps) if step.get("id") == CHECK_ID)
    upload_at = next(i for i, step in enumerate(steps) if _is_upload(step))
    at = "jobs.coverage-upload.steps"
    expected = sorted([f"{at}[{check_at}].run", f"{at}[{upload_at}].with.access-token"])
    found = credential_sites(workflow)
    assert found == expected, f"expected the token only at {expected}, found {found}"


def assert_publisher_queue(workflow: dict[str, Any]) -> None:
    """Assert publisher runs share one group per ref and never cancel."""
    concurrency = workflow.get("concurrency") or {}
    assert concurrency.get("group") == PUBLISHER_GROUP, concurrency
    assert concurrency.get("cancel-in-progress") is False, concurrency


def assert_codescene_publisher_contract(workflow: dict[str, Any]) -> None:
    """Assert every part of the generated publisher's CodeScene shape.

    Parameters
    ----------
    workflow : dict[str, Any]
        The parsed generated ``coverage-main.yml``.

    Raises
    ------
    AssertionError
        Raised when any part of the shape is missing or widened.
    """
    assert_check_step(workflow)
    assert_upload_step(workflow)
    assert_token_sites(workflow)
    assert_publisher_queue(workflow)


def assert_ci_workflow_reaches_no_codescene(ci_workflow: str) -> None:
    """Assert the pull-request workflow names no CodeScene token, host or command.

    Read over the raw text, comments included, so a commented-out step that
    would teach the retired pattern is refused as well.

    Parameters
    ----------
    ci_workflow : str
        The rendered generated ``ci.yml``.

    Raises
    ------
    AssertionError
        Raised when the text names the token, the host or ``cs-coverage``.
    """
    reaching = [
        marker
        for marker in (CREDENTIAL_NAME, "codescene.io", "cs-coverage")
        if marker in ci_workflow.casefold()
    ]
    assert not reaching, (
        "expected the generated pull-request CI workflow to name no CodeScene "
        f"token, host or command, even in a comment; found {reaching}"
    )


def _coverage_step(workflow: dict[str, Any], job: str) -> dict[str, Any]:
    """Return the one shared ``generate-coverage`` step in ``job``."""
    steps = [
        step
        for step in workflow["jobs"][job].get("steps", [])
        if isinstance(step, dict)
        and "/.github/actions/generate-coverage@" in str(step.get("uses", ""))
    ]
    assert len(steps) == 1, f"expected one coverage step in {job}, found {len(steps)}"
    return steps[0]


def assert_lanes_share_the_ratchet(
    ci_workflow: dict[str, Any], publisher: dict[str, Any]
) -> None:
    """Assert the pull-request lane ratchets against the publisher's baseline.

    Both lanes call the same ``generate-coverage`` revision, so the baseline
    the publisher saves is one the pull-request lane can read, and only the
    publisher archives the report.

    Parameters
    ----------
    ci_workflow : dict[str, Any]
        The parsed generated ``ci.yml``.
    publisher : dict[str, Any]
        The parsed generated ``coverage-main.yml``.

    Raises
    ------
    AssertionError
        Raised when the lanes' revisions differ, the pull-request lane does
        not ratchet, or it publishes the artefact the publisher owns.
    """
    lane = _coverage_step(ci_workflow, "build-test")
    main = _coverage_step(publisher, "coverage-upload")
    assert lane["uses"] == main["uses"], (lane["uses"], main["uses"])
    inputs = lane.get("with") or {}
    assert inputs.get("with-ratchet") == "true", inputs
    assert inputs.get("publish-artefact") == "false", inputs
