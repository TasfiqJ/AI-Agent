# test-guardian

An agentic CLI that joins a repo, detects API endpoints, generates test suites, runs them in a Docker sandbox, iterates to green, and produces reviewable diffs with human approval.

## Quick Start

```bash
# Install dependencies
pnpm install
pip install -e agent/

# Initialize for a target repo
test-guardian init ./demo/flask-todo-api

# Generate a plan (read-only)
test-guardian plan

# Execute: Plan → Act → Verify
test-guardian run
```

## How It Works

```
PLAN (read-only)  →  ACT (permissioned)  →  VERIFY (sandboxed)
  Analyze repo         Generate tests          Run in Docker
  Detect endpoints     Apply diffs             Parse results
  Build plan           Checkpoint files        Fix failures
                                               Iterate (max 3x)
```

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| CLI | TypeScript + React Ink | Terminal UI, diff review, approval gates |
| Agent | Python + FastAPI | Agentic loop, LLM orchestration, tool execution |
| Sandbox | Docker | Isolated test execution, network=none |
| Code Intel | tree-sitter | AST parsing, endpoint detection |
| LLM | Ollama (default) | Zero-cost local inference |

## Safety Model

- **Sandboxed execution** — Docker containers with `--network=none`, 120s timeout, 512MB RAM
- **Permission modes** — Plan (read-only), Default (approve each write), Trust (auto-approve)
- **Checkpoint/revert** — Every file snapshotted before modification
- **Command allowlist** — Only `pytest`, `npm test`, `vitest`, `go test`, `ruff`, `mypy`, `eslint`
- **Tool budget** — Max 50 tool calls per run

## Project Structure

```
test-guardian/
├── packages/cli/       # TypeScript + React Ink CLI
├── packages/shared/    # Shared types
├── agent/              # Python agent backend
├── sandbox/            # Docker sandbox images
├── demo/               # Demo repos for evaluation
├── eval/               # Evaluation harness
├── CLAUDE.md           # Claude Code project guidance
├── AGENTS.md           # Agent instruction file
└── SECURITY.md         # Threat model
```

## Development

```bash
# TypeScript
pnpm test              # Run all TS tests
pnpm lint              # Lint all packages
pnpm typecheck         # Type check all packages

# Python
cd agent && pytest     # Run Python tests
cd agent && ruff check . && mypy src/  # Lint + typecheck
```
