"""Tests for permissions, checkpoints, and trace logger."""

import tempfile
from pathlib import Path

import pytest

from guardian.safety.checkpoints import CheckpointManager
from guardian.safety.permissions import PermissionManager, PermissionMode
from guardian.trace.logger import TraceLogger


# ── Permission Tests ──

def test_plan_mode_blocks_writes() -> None:
    pm = PermissionManager(mode=PermissionMode.PLAN)
    assert pm.can_read() is True
    assert pm.can_write() is False
    assert pm.requires_approval() is False


def test_default_mode_allows_writes_with_approval() -> None:
    pm = PermissionManager(mode=PermissionMode.DEFAULT)
    assert pm.can_read() is True
    assert pm.can_write() is True
    assert pm.requires_approval() is True


def test_trust_mode_auto_allows() -> None:
    pm = PermissionManager(mode=PermissionMode.TRUST)
    assert pm.can_read() is True
    assert pm.can_write() is True
    assert pm.requires_approval() is False


def test_command_allowlist() -> None:
    pm = PermissionManager()
    assert pm.is_command_allowed("pytest -v") is True
    assert pm.is_command_allowed("python -m pytest") is True
    assert pm.is_command_allowed("npm test") is True


def test_blocked_commands() -> None:
    pm = PermissionManager()
    assert pm.is_command_allowed("rm -rf /") is False
    assert pm.is_command_allowed("curl http://evil.com") is False
    assert pm.is_command_allowed("wget http://evil.com") is False
    assert pm.is_command_allowed("pip install malware") is False
    assert pm.is_command_allowed("sudo rm -rf") is False


def test_unknown_command_blocked() -> None:
    pm = PermissionManager()
    assert pm.is_command_allowed("cat /etc/passwd") is False
    assert pm.is_command_allowed("bash -c 'echo pwned'") is False


# ── Checkpoint Tests ──

def test_checkpoint_existing_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / "test.py"
        test_file.write_text("original content")

        cm = CheckpointManager("test-run", tmp_path / "checkpoints")
        cp_path = cm.checkpoint(test_file)

        assert cp_path is not None
        assert cp_path.exists()
        assert cp_path.read_text() == "original content"


def test_checkpoint_new_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        new_file = tmp_path / "new.py"  # Does not exist yet

        cm = CheckpointManager("test-run", tmp_path / "checkpoints")
        cp_path = cm.checkpoint(new_file)

        assert cp_path is None  # No checkpoint for new files
        checkpoints = cm.get_checkpoints()
        assert len(checkpoints) == 1
        assert checkpoints[0]["was_new"] is True


def test_revert_restores_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / "test.py"
        test_file.write_text("original content")

        cm = CheckpointManager("test-run", tmp_path / "checkpoints")
        cm.checkpoint(test_file)

        # Simulate modification
        test_file.write_text("modified content")
        assert test_file.read_text() == "modified content"

        # Revert
        reverted = cm.revert_all()
        assert len(reverted) == 1
        assert test_file.read_text() == "original content"


def test_revert_removes_new_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        new_file = tmp_path / "new.py"

        cm = CheckpointManager("test-run", tmp_path / "checkpoints")
        cm.checkpoint(new_file)

        # Simulate file creation
        new_file.write_text("new content")
        assert new_file.exists()

        # Revert should remove it
        reverted = cm.revert_all()
        assert len(reverted) == 1
        assert not new_file.exists()


# ── Trace Logger Tests ──

def test_trace_logger_creates_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tracer = TraceLogger("test-run", Path(tmp))
        tracer.log("test_event", {"key": "value"})

        assert tracer.file_path.exists()
        entries = tracer.read_entries()
        assert len(entries) == 1
        assert entries[0]["type"] == "test_event"
        assert entries[0]["data"]["key"] == "value"


def test_trace_logger_multiple_entries() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tracer = TraceLogger("test-run", Path(tmp))
        tracer.log_tool_call("file_read", {"path": "app.py"}, "contents")
        tracer.log_llm_request([{"role": "user", "content": "test"}], "system")
        tracer.log_llm_response("response text", "mock")
        tracer.log_decision("state_transition", "IDLE → PLANNING")
        tracer.log_error("something broke", {"detail": "info"})

        entries = tracer.read_entries()
        assert len(entries) == 5
        types = [e["type"] for e in entries]
        assert "tool_call" in types
        assert "llm_request" in types
        assert "llm_response" in types
        assert "decision" in types
        assert "error" in types


def test_trace_logger_steps_increment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tracer = TraceLogger("test-run", Path(tmp))
        tracer.log("a", {})
        tracer.log("b", {})
        tracer.log("c", {})

        entries = tracer.read_entries()
        steps = [e["step"] for e in entries]
        assert steps == [1, 2, 3]
