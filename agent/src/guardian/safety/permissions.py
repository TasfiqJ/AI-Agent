"""Permission modes and command allowlists.

Three modes: plan (read-only), default (approve each write), trust (auto-approve).
"""

from __future__ import annotations

import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_COMMANDS = [
    "pytest",
    "python -m pytest",
    "npm test",
    "npx vitest",
    "npx jest",
    "go test",
    "ruff check",
    "mypy",
    "eslint",
]

BLOCKED_PATTERNS = [
    r"rm\s+-rf",
    r"curl\s+",
    r"wget\s+",
    r"pip\s+install",
    r"npm\s+install",
    r"sudo\s+",
    r"chmod\s+",
    r"chown\s+",
]


class PermissionMode(str, Enum):
    PLAN = "plan"
    DEFAULT = "default"
    TRUST = "trust"


class PermissionManager:
    """Enforces permission modes and command allowlists."""

    def __init__(
        self,
        mode: PermissionMode = PermissionMode.DEFAULT,
        allowed_commands: list[str] | None = None,
        blocked_patterns: list[str] | None = None,
    ) -> None:
        self.mode = mode
        self.allowed_commands = allowed_commands or DEFAULT_ALLOWED_COMMANDS
        self.blocked_patterns = blocked_patterns or BLOCKED_PATTERNS

    def can_read(self) -> bool:
        """All modes allow reading."""
        return True

    def can_write(self) -> bool:
        """Plan mode blocks writes. Default requires approval. Trust auto-allows."""
        return self.mode != PermissionMode.PLAN

    def requires_approval(self) -> bool:
        """Default mode requires approval for writes."""
        return self.mode == PermissionMode.DEFAULT

    def is_command_allowed(self, command: str) -> bool:
        """Check if a command is in the allowlist and not blocked."""
        # Check blocked patterns first
        for pattern in self.blocked_patterns:
            if re.search(pattern, command):
                logger.warning("Command blocked by pattern %s: %s", pattern, command)
                return False

        # Check allowlist
        for allowed in self.allowed_commands:
            if command.strip().startswith(allowed):
                return True

        logger.warning("Command not in allowlist: %s", command)
        return False
