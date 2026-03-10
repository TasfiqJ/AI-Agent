# Security Model

## Threat Model

test-guardian executes LLM-generated code. This creates several attack surfaces.

### 1. Prompt Injection
**Threat:** Malicious content in target repos could manipulate the LLM into generating harmful code.
**Mitigation:**
- All test execution happens in a Docker sandbox with `--network=none`
- Command allowlist prevents execution of anything except test runners
- Blocked patterns: `rm -rf`, `curl`, `wget`, `pip install`
- File writes go through unified diff + human approval

### 2. Data Exfiltration
**Threat:** Generated tests could attempt to send repo contents to external servers.
**Mitigation:**
- Docker sandbox network is disabled by default (`--network=none`)
- Repo is mounted read-only in the sandbox
- No environment variables are passed to the sandbox container

### 3. Resource Exhaustion
**Threat:** Generated code could consume excessive CPU/memory.
**Mitigation:**
- Sandbox timeout: 120 seconds (configurable)
- Memory limit: 512MB per container
- CPU limit: 1 core per container
- Tool budget: max 50 calls per run

### 4. Uncontrolled File Modification
**Threat:** The agent could modify files it shouldn't.
**Mitigation:**
- Three permission modes: plan (read-only), default (approve each write), trust (auto-approve)
- Checkpoint system snapshots every file before modification
- `test-guardian revert` restores all files from checkpoints
- File writes use unified diff format — no blind overwrite

## Permission Modes

| Mode | Read | Write | Execute |
|------|------|-------|---------|
| Plan | Auto | Blocked | Blocked |
| Default | Auto | Approval required | Allowlisted only |
| Trust | Auto | Auto | Allowlisted only |

## Command Allowlist
```
pytest, npm test, npx vitest, go test, ruff check, mypy, eslint
```

## Reporting Security Issues
If you find a security vulnerability, please open an issue on GitHub.
