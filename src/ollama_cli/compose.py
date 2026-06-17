#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

# ============================================================
#  Global configurations
# ============================================================
SERVICE = os.environ.get("OLLAMA_COMPOSE_SERVICE", "ollama")
PROJECT_NAME = os.environ.get("OLLAMA_PROJECT_NAME", "ai-tools-ollama")
DEBUG_ENABLED = os.environ.get("OLLAMA_DEBUG", "").lower() in {"1", "true", "yes", "on"}


# ============================================================
#  Docker Compose wrapper helpers
# ============================================================
def resolve_compose_dir() -> Path:
    """Resolve the docker-compose.yaml directory.
    
    Tries multiple locations in order:
    1. OLLAMA_COMPOSE_DIR environment variable
    2. Hardcoded path (for macOS development)
    3. Relative to package source
    4. Relative to executable location
    5. Current working directory (fallback)
    """
    env_dir = os.environ.get("OLLAMA_COMPOSE_DIR")
    if env_dir:
        return Path(env_dir).resolve()

    hardcoded = Path(
        "/Users/Shared/CLOUD/Projekte/CLIs/ollama-cli/DOCKER/ollama-wrapper"
    )
    if hardcoded.exists() and (hardcoded / "docker-compose.yaml").is_file():
        return hardcoded

    try:
        source_dir = Path(__file__).resolve().parents[2] / "DOCKER" / "ollama-wrapper"
        if source_dir.exists() and (source_dir / "docker-compose.yaml").is_file():
            return source_dir
    except Exception:
        pass

    try:
        bin_relative = Path(sys.argv[0]).resolve().parent / "DOCKER" / "ollama-wrapper"
        if bin_relative.exists() and (bin_relative / "docker-compose.yaml").is_file():
            return bin_relative
    except Exception:
        pass

    return Path.cwd()


COMPOSE_DIR = resolve_compose_dir()
COMPOSE_FILE = COMPOSE_DIR / "docker-compose.yaml"
COMPOSE_BASE_CMD = ["docker", "compose", "-p", PROJECT_NAME, "-f", str(COMPOSE_FILE)]


def ensure_compose_file() -> None:
    """Ensure docker-compose.yaml exists."""
    if not COMPOSE_FILE.is_file():
        print(
            f"ERROR: docker-compose.yaml not found at: {COMPOSE_FILE}", file=sys.stderr
        )
        print(
            "Hint: set OLLAMA_COMPOSE_DIR to the folder containing docker-compose.yaml",
            file=sys.stderr,
        )
        sys.exit(2)


def is_tty() -> bool:
    """Check if running in a TTY."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def run_cmd(
    cmd: list[str],
    *,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command with optional output capture."""
    if DEBUG_ENABLED:
        print(
            f"DEBUG: run_cmd: {' '.join(cmd)} capture_output={capture_output}",
            file=sys.stderr,
        )
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def exec_cmd(cmd: list[str]) -> None:
    """Replace current process with command using execvp."""
    if DEBUG_ENABLED:
        print(f"DEBUG: exec_cmd: {' '.join(cmd)}", file=sys.stderr)
    os.execvp(cmd[0], cmd)


def compose_build_cmd(*args: str) -> list[str]:
    """Build a docker compose command."""
    return [*COMPOSE_BASE_CMD, *args]


def compose_exec_cmd(command: list[str]) -> list[str]:
    """Build a docker compose exec command."""
    cmd = [*COMPOSE_BASE_CMD, "exec"]
    if not is_tty():
        cmd.append("-T")
    cmd.append(SERVICE)
    cmd.extend(command)
    return cmd


def compose_exec(
    command: list[str],
    *,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Execute a command inside the compose container."""
    return run_cmd(
        compose_exec_cmd(command), check=check, capture_output=capture_output
    )


def compose_exec_or_exec(command: list[str]) -> None:
    """Execute a command in container or replace process."""
    exec_cmd(compose_exec_cmd(command))


def ensure_service_exists() -> None:
    """Ensure the service exists in docker-compose.yaml."""
    ensure_compose_file()
    result = run_cmd(
        compose_build_cmd("config", "--services"),
        capture_output=True,
        check=True,
    )
    services = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    if SERVICE not in services:
        print(
            f"ERROR: service '{SERVICE}' not found in compose file: {COMPOSE_FILE}",
            file=sys.stderr,
        )
        print("Available services:", file=sys.stderr)
        for service in sorted(services):
            print(service, file=sys.stderr)
        sys.exit(2)


def is_service_running() -> bool:
    """Check if the service is currently running."""
    ensure_compose_file()
    result = run_cmd(
        compose_build_cmd("ps", "-q", SERVICE),
        capture_output=True,
        check=True,
    )
    return bool(result.stdout.strip())


def ensure_service_running() -> None:
    """Ensure the service is running, start if necessary."""
    ensure_service_exists()
    if not is_service_running():
        run_cmd(compose_build_cmd("up", "-d", SERVICE), check=True)


def run_ollama(args: list[str]) -> None:
    """Run ollama command with arguments in the container."""
    ensure_service_running()
    compose_exec_or_exec(["ollama", *args])
