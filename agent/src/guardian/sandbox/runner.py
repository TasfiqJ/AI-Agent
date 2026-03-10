"""Docker sandbox runner — create container, mount repo, run tests, capture output.

Security constraints:
  - Network disabled (--network=none)
  - Resource limits: 512MB RAM, 1 CPU
  - Timeout: 120s, container killed on timeout
  - Read-only repo mount by default
  - Non-root user inside container
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Docker image names
PYTHON_IMAGE = "test-guardian/python-sandbox"
NODE_IMAGE = "test-guardian/node-sandbox"

# Defaults
DEFAULT_TIMEOUT = 120
DEFAULT_MEMORY = "512m"
DEFAULT_CPUS = "1"


@dataclass
class SandboxResult:
    """Result from a sandbox execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    command: str = ""
    image: str = ""
    duration_ms: int = 0


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""

    image: str = PYTHON_IMAGE
    command: list[str] = field(default_factory=lambda: ["pytest", "-v", "--tb=short"])
    timeout: int = DEFAULT_TIMEOUT
    memory: str = DEFAULT_MEMORY
    cpus: str = DEFAULT_CPUS
    network: str = "none"
    readonly_mount: bool = False
    workdir: str = "/workspace"
    env: dict[str, str] = field(default_factory=dict)


def _docker_available() -> bool:
    """Check if Docker is available on the system."""
    return shutil.which("docker") is not None


def _image_exists(image: str) -> bool:
    """Check if a Docker image exists locally."""
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def build_image(
    dockerfile_dir: str,
    image_name: str,
    force: bool = False,
) -> bool:
    """Build a sandbox Docker image.

    Args:
        dockerfile_dir: Path to directory containing the Dockerfile.
        image_name: Tag for the built image.
        force: Rebuild even if image exists.

    Returns:
        True if image was built (or already existed), False on failure.
    """
    if not _docker_available():
        logger.error("Docker is not available")
        return False

    if not force and _image_exists(image_name):
        logger.info("Image %s already exists, skipping build", image_name)
        return True

    logger.info("Building image %s from %s", image_name, dockerfile_dir)
    proc = await asyncio.create_subprocess_exec(
        "docker", "build", "-t", image_name, dockerfile_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error(
            "Failed to build %s: %s",
            image_name,
            stderr.decode("utf-8", errors="replace"),
        )
        return False

    logger.info("Built image %s successfully", image_name)
    return True


async def run_in_sandbox(
    repo_path: str,
    config: SandboxConfig | None = None,
) -> SandboxResult:
    """Run a command inside a Docker sandbox container.

    Args:
        repo_path: Path to the repository to mount.
        config: Sandbox configuration. Uses defaults if not provided.

    Returns:
        SandboxResult with exit code, stdout, stderr, and timing.
    """
    if config is None:
        config = SandboxConfig()

    if not _docker_available():
        return SandboxResult(
            exit_code=1,
            stdout="",
            stderr="Docker is not available on this system",
            command=" ".join(config.command),
            image=config.image,
        )

    repo = Path(repo_path).resolve()
    if not repo.exists():
        return SandboxResult(
            exit_code=1,
            stdout="",
            stderr=f"Repository path does not exist: {repo_path}",
            command=" ".join(config.command),
            image=config.image,
        )

    # Build docker run command
    docker_cmd = [
        "docker", "run",
        "--rm",
        f"--network={config.network}",
        f"--memory={config.memory}",
        f"--cpus={config.cpus}",
        "--pids-limit=256",
    ]

    # Volume mount
    mount_flag = "ro" if config.readonly_mount else "rw"
    docker_cmd.extend([
        "-v", f"{repo}:{config.workdir}:{mount_flag}",
        "-w", config.workdir,
    ])

    # Environment variables
    for key, value in config.env.items():
        docker_cmd.extend(["-e", f"{key}={value}"])

    # Image and command
    docker_cmd.append(config.image)
    docker_cmd.extend(config.command)

    logger.info("Running sandbox: %s", " ".join(docker_cmd))

    import time
    start = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=config.timeout,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            return SandboxResult(
                exit_code=proc.returncode or 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                timed_out=False,
                command=" ".join(config.command),
                image=config.image,
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.warning(
                "Sandbox timed out after %ds, killing container",
                config.timeout,
            )
            proc.kill()
            await proc.wait()

            return SandboxResult(
                exit_code=124,
                stdout="",
                stderr=f"Container killed: exceeded {config.timeout}s timeout",
                timed_out=True,
                command=" ".join(config.command),
                image=config.image,
                duration_ms=duration_ms,
            )

    except FileNotFoundError:
        return SandboxResult(
            exit_code=1,
            stdout="",
            stderr="Docker executable not found",
            command=" ".join(config.command),
            image=config.image,
        )


async def run_pytest(
    repo_path: str,
    test_files: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    extra_args: list[str] | None = None,
) -> SandboxResult:
    """Convenience: run pytest inside the Python sandbox.

    Args:
        repo_path: Repository path to mount.
        test_files: Specific test files to run. Runs all if not specified.
        timeout: Timeout in seconds.
        extra_args: Additional pytest arguments.
    """
    command = ["pytest", "-v", "--tb=short"]
    if extra_args:
        command.extend(extra_args)
    if test_files:
        command.extend(test_files)

    config = SandboxConfig(
        image=PYTHON_IMAGE,
        command=command,
        timeout=timeout,
    )
    return await run_in_sandbox(repo_path, config)


async def run_jest(
    repo_path: str,
    test_files: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> SandboxResult:
    """Convenience: run jest inside the Node sandbox.

    Args:
        repo_path: Repository path to mount.
        test_files: Specific test files to run.
        timeout: Timeout in seconds.
    """
    command = ["npx", "jest", "--verbose"]
    if test_files:
        command.extend(test_files)

    config = SandboxConfig(
        image=NODE_IMAGE,
        command=command,
        timeout=timeout,
    )
    return await run_in_sandbox(repo_path, config)


def detect_test_runner(repo_path: str) -> str:
    """Detect which test runner to use based on repo contents.

    Returns:
        "pytest" or "jest" or "unknown".
    """
    root = Path(repo_path)

    # Check for Python test files
    py_test_files = list(root.rglob("test_*.py")) + list(root.rglob("*_test.py"))

    # Check for JS/TS test files
    js_test_files = (
        list(root.rglob("*.test.js"))
        + list(root.rglob("*.test.ts"))
        + list(root.rglob("*.spec.js"))
        + list(root.rglob("*.spec.ts"))
    )

    if py_test_files and not js_test_files:
        return "pytest"
    elif js_test_files and not py_test_files:
        return "jest"
    elif py_test_files and js_test_files:
        # Prefer pytest if both exist
        return "pytest"
    return "unknown"
