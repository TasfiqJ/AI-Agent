"""Checkpoint system — snapshot files before write, restore on revert.

Before every file_write, the current file contents are saved to a checkpoint directory.
If the user rejects changes, all files can be restored from checkpoints.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages file checkpoints for a guardian run."""

    def __init__(self, run_id: str, checkpoint_dir: Path) -> None:
        self.run_id = run_id
        self.base_dir = checkpoint_dir / run_id
        self._step = 0
        self._checkpoints: list[dict[str, Any]] = []

    def checkpoint(self, file_path: Path) -> Path | None:
        """Save a snapshot of a file before modification.

        Returns the checkpoint path, or None if the file doesn't exist yet.
        """
        self._step += 1
        step_dir = self.base_dir / f"step-{self._step:03d}"
        step_dir.mkdir(parents=True, exist_ok=True)

        if not file_path.exists():
            # New file — no checkpoint needed, but record it
            self._checkpoints.append(
                {
                    "step": self._step,
                    "original_path": str(file_path),
                    "checkpoint_path": None,
                    "was_new": True,
                }
            )
            logger.info("Checkpoint step %d: new file %s", self._step, file_path)
            return None

        # Copy the existing file to the checkpoint directory
        relative = file_path.name
        checkpoint_path = step_dir / f"{relative}.bak"
        shutil.copy2(file_path, checkpoint_path)

        self._checkpoints.append(
            {
                "step": self._step,
                "original_path": str(file_path),
                "checkpoint_path": str(checkpoint_path),
                "was_new": False,
            }
        )
        logger.info(
            "Checkpoint step %d: %s → %s",
            self._step,
            file_path,
            checkpoint_path,
        )
        return checkpoint_path

    def revert_all(self) -> list[str]:
        """Revert all changes by restoring from checkpoints.

        Returns list of reverted file paths.
        """
        reverted: list[str] = []

        # Process in reverse order (most recent first)
        for cp in reversed(self._checkpoints):
            original = Path(cp["original_path"])

            if cp["was_new"]:
                # Remove the newly created file
                if original.exists():
                    original.unlink()
                    reverted.append(f"Removed: {original}")
                    logger.info("Reverted: removed new file %s", original)
            else:
                # Restore from checkpoint
                checkpoint = Path(cp["checkpoint_path"])
                if checkpoint.exists():
                    shutil.copy2(checkpoint, original)
                    reverted.append(f"Restored: {original}")
                    logger.info("Reverted: restored %s from checkpoint", original)

        return reverted

    def get_checkpoints(self) -> list[dict[str, Any]]:
        """Return list of all checkpoints."""
        return list(self._checkpoints)

    def cleanup(self) -> None:
        """Remove checkpoint directory after successful run."""
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)
            logger.info("Cleaned up checkpoints for run %s", self.run_id)
