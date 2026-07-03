"""Provide shared helpers for container-aware test execution."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

SAFE_ENV_KEYS = (
    "ACT_SOCKET_DEBUG",
    "HOME",
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "PATH",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TMP",
    "TMPDIR",
    "USER",
    "XDG_RUNTIME_DIR",
)


def _debug(message: str) -> None:
    """Print socket diagnostics when ACT_SOCKET_DEBUG is enabled."""
    if os.environ.get("ACT_SOCKET_DEBUG") == "1":
        print(f"act socket debug: {message}", file=sys.stderr)


def _resolved_socket_from_docker_host(
    docker_host: str, allowed_dirs: tuple[Path, ...]
) -> Path | None:
    """Return resolved socket path from a Docker host URL or None."""
    parsed = urlparse(docker_host)
    if parsed.scheme != "unix" or parsed.netloc or not parsed.path:
        _debug(f"rejected DOCKER_HOST with unsupported shape: {docker_host!r}")
        return None
    try:
        socket_path = Path(parsed.path).expanduser().resolve()
    except OSError as error:
        _debug(f"failed to resolve DOCKER_HOST path {parsed.path!r}: {error}")
        return None
    if not any(socket_path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs):
        _debug(f"rejected socket outside allowed roots: {socket_path}")
        return None
    _debug(f"accepted socket path: {socket_path}")
    return socket_path


def _user_podman_socket() -> Path:
    """Return the current user's Podman socket path."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    runtime_path = (
        Path(runtime_dir) if runtime_dir else Path(f"/run/user/{os.getuid()}")
    )
    return runtime_path.expanduser().resolve() / "podman" / "podman.sock"


def local_socket_dirs() -> tuple[Path, ...]:
    """Return socket roots accepted for runtime availability probes."""
    return (
        Path("/run").resolve(),
        Path("/var/run").resolve(),
        Path(f"/run/user/{os.getuid()}/podman").resolve(),
    )


def user_runtime_socket_dirs() -> tuple[Path, ...]:
    """Return user runtime roots accepted for act socket forwarding."""
    return (_user_podman_socket().parent.parent,)


def docker_environment() -> dict[str, str]:
    """Return a sanitized environment for Docker-compatible subprocesses."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key in SAFE_ENV_KEYS and value
    }
    docker_host = os.environ.get("DOCKER_HOST")
    if docker_host is not None:
        socket_path = _resolved_socket_from_docker_host(
            docker_host, local_socket_dirs()
        )
        if socket_path is None:
            env.pop("DOCKER_HOST", None)
            _debug("dropped invalid DOCKER_HOST from sanitized environment")
        else:
            env["DOCKER_HOST"] = f"unix://{socket_path}"
            _debug("preserved sanitized DOCKER_HOST")
        return env
    if "DOCKER_HOST" not in env:
        podman_socket = _user_podman_socket()
        if podman_socket.exists():
            env["DOCKER_HOST"] = f"unix://{podman_socket}"
            _debug("using user Podman socket fallback")
    return env


def container_daemon_socket(env: Mapping[str, str] | None = None) -> str | None:
    """Return a validated ``act`` container daemon socket value."""
    should_fallback = env is None
    env = os.environ if env is None else env
    docker_host = env.get("DOCKER_HOST")
    if docker_host is None:
        if should_fallback:
            return f"unix://{_user_podman_socket()}"
        return None
    socket_path = _resolved_socket_from_docker_host(
        docker_host, user_runtime_socket_dirs()
    )
    if socket_path is None:
        return None
    return f"unix://{socket_path}"
