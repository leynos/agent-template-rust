"""Provide shared helpers for container-aware test execution."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


def _resolved_socket_from_docker_host(
    docker_host: str, allowed_dirs: tuple[Path, ...]
) -> Path | None:
    """Return resolved socket path from a Docker host URL or None."""
    parsed = urlparse(docker_host)
    if parsed.scheme != "unix" or parsed.netloc or not parsed.path:
        return None
    try:
        socket_path = Path(parsed.path).expanduser().resolve()
    except OSError:
        return None
    if not any(socket_path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs):
        return None
    return socket_path


def _user_podman_socket() -> Path:
    """Return the current user's Podman socket path."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    runtime_path = Path(runtime_dir) if runtime_dir else Path(f"/run/user/{os.getuid()}")
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
    env = os.environ.copy()
    docker_host = env.get("DOCKER_HOST")
    if docker_host is not None:
        socket_path = _resolved_socket_from_docker_host(
            docker_host, local_socket_dirs()
        )
        if socket_path is None:
            env.pop("DOCKER_HOST", None)
        else:
            env["DOCKER_HOST"] = f"unix://{socket_path}"
        return env
    if "DOCKER_HOST" not in env:
        podman_socket = _user_podman_socket()
        if podman_socket.exists():
            env["DOCKER_HOST"] = f"unix://{podman_socket}"
    return env


def container_daemon_socket(env: dict[str, str] | None = None) -> str | None:
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
