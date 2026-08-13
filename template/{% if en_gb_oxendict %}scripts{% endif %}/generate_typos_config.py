#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Generate ``typos.toml`` from the shared en-GB-oxendict dictionary.

The shared dictionary is refreshed into an untracked repository-local cache
only when the authoritative copy is newer. A valid cache remains usable when
the network is unavailable, and ``typos.local.toml`` supplies the narrow
repository-specific policy that must not weaken the estate-wide base.
"""

from pathlib import Path

import typos_rollout as rollout

DEFAULT_BASE_URL = (
    "https://raw.githubusercontent.com/leynos/agent-helper-scripts/"
    "refs/heads/main/data/typos-oxendict-base.toml"
)
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def dictionary_from_cache(repository: Path = REPOSITORY_ROOT) -> rollout.Dictionary:
    """Load cached shared policy merged with the repository overlay.

    Parameters
    ----------
    repository : Path
        Repository containing the refreshed cache and optional
        ``typos.local.toml`` overlay.

    Returns
    -------
    rollout.Dictionary
        Validated shared policy, with local additions merged when present.

    Raises
    ------
    OSError
        A dictionary file cannot be read.
    TypeError
        A dictionary value has the wrong TOML shape.
    ValueError
        Dictionary policy is invalid or the overlay conflicts with the base.
    tomllib.TOMLDecodeError
        A dictionary file is not valid TOML.
    """
    dictionary = rollout.load_dictionary(repository / ".typos-oxendict-base.toml")
    local_overlay = repository / "typos.local.toml"
    if local_overlay.exists():
        dictionary = rollout.merge_dictionaries(
            dictionary,
            rollout.load_dictionary(local_overlay),
        )
    return dictionary


def render_config(repository: Path = REPOSITORY_ROOT) -> str:
    """Render deterministic configuration from the populated local cache.

    Parameters
    ----------
    repository : Path
        Repository containing the refreshed cache and optional local overlay.

    Returns
    -------
    str
        Validated ``typos.toml`` content generated from the merged policy.

    Raises
    ------
    OSError
        A dictionary file cannot be read.
    TypeError
        A dictionary value has the wrong TOML shape.
    ValueError
        Dictionary policy or generated word mappings conflict.
    tomllib.TOMLDecodeError
        Input or rendered output is not valid TOML.
    """
    return rollout.render_typos_config(dictionary_from_cache(repository))


def main(
    output: Path | None = None,
    *,
    repository: Path = REPOSITORY_ROOT,
    source: str | Path = DEFAULT_BASE_URL,
    offline: bool = False,
) -> rollout.RefreshResult:
    """Refresh shared policy and write the merged generated configuration.

    Parameters
    ----------
    output : Path | None
        Generated configuration destination. Defaults to ``typos.toml`` in
        ``repository``.
    repository : Path
        Repository that owns the cache, metadata, overlay, and output.
    source : str | Path
        Authoritative local dictionary path or HTTPS URL.
    offline : bool
        Reuse a valid cache without consulting ``source`` when true.

    Returns
    -------
    rollout.RefreshResult
        Refresh status and the validated cache used to generate the output.

    Raises
    ------
    FileNotFoundError
        Offline mode has no valid cache or a local source is absent.
    OSError
        Refresh, locking, or output filesystem operations fail.
    TypeError
        A dictionary value has the wrong TOML shape.
    ValueError
        A source, dictionary, merge, or generated mapping is invalid.
    tomllib.TOMLDecodeError
        Input or generated output is not valid TOML.
    urllib.error.HTTPError
        A remote refresh fails and no valid cache is available.
    urllib.error.URLError
        A network refresh fails and no valid cache is available.
    """
    result = rollout.refresh_base(
        source,
        repository / ".typos-oxendict-base.toml",
        metadata=repository / ".typos-oxendict-base.json",
        offline=offline,
    )
    destination = output if output is not None else repository / "typos.toml"
    rollout.write_config(destination, dictionary_from_cache(repository))
    return result


if __name__ == "__main__":
    refresh = main()
    print(f"{refresh.status}: {REPOSITORY_ROOT / 'typos.toml'}")
