# CLAUDE.md

This file is for Claude Code and any AI coding agent working on this repository.

## Project
test-guardian — an agentic CLI tool that generates API tests autonomously.

## Architecture
- `packages/cli/` — TypeScript + React Ink terminal UI
- `packages/shared/` — Shared TypeScript types
- `agent/` — Python backend (FastAPI + agentic loop)
- `sandbox/` — Docker images for isolated test execution
- `demo/` — Target repos for evaluation (Flask, FastAPI, Express)
- `eval/` — Evaluation harness

## Build & Test Commands
```bash
# Install all dependencies
pnpm install

# Run all tests
pnpm test

# TypeScript lint + typecheck
cd packages/cli && pnpm lint && pnpm typecheck

# Python lint + typecheck + test
cd agent && ruff check . && mypy src/ && pytest

# Build CLI
cd packages/cli && pnpm build

# Start Python backend
cd agent && uvicorn src.guardian.server:app --reload

# Build sandbox images
docker build -t test-guardian/python-sandbox sandbox/python/
docker build -t test-guardian/node-sandbox sandbox/node/

# Run evaluation
cd eval && python run_eval.py
```

## Coding Standards
- Python: ruff for linting, mypy for types, Pydantic for all data models
- TypeScript: strict mode, eslint, no `any` types
- Every LLM output that drives an action MUST be validated against a Pydantic schema
- File writes use unified diff format, never blind overwrite
- All commands run through sandbox with allowlist — never raw subprocess
- Tests required for: state machine transitions, tool correctness, permission enforcement

## Key Design Decisions
- No LangChain/LlamaIndex — custom agentic loop to prove we understand the primitives
- Ollama as default LLM (zero cost) with provider abstraction for Anthropic/OpenAI
- Docker sandbox with network=none by default — safety is non-negotiable
- Checkpoint before every file write — any change is revertible
- JSON Lines trace logging — every run is replayable
