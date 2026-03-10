# test-guardian Architecture

## Overview

test-guardian is an agentic CLI tool that generates API tests autonomously using a **Plan → Act → Verify** loop powered by local LLMs (Ollama).

## System Architecture

```
┌─────────────────────────────────────────────────┐
│                   CLI (React Ink)                │
│  Commands: init | plan | run | status | revert  │
│  Components: PlanView, LogStream, DiffReview,   │
│              ApprovalGate, TestResults           │
└──────────────────┬──────────────────────────────┘
                   │ HTTP + SSE
┌──────────────────▼──────────────────────────────┐
│              Python Agent Backend                │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ LLM      │  │ Agentic  │  │ Tool Registry │  │
│  │ Client   │──│ Loop     │──│ + Budget      │  │
│  │ (Ollama) │  │ (FSM)    │  │ Enforcement   │  │
│  └──────────┘  └────┬─────┘  └───────┬───────┘  │
│                     │                │           │
│  ┌──────────────────▼────────────────▼────────┐  │
│  │              Tool System                    │  │
│  │  file_ops | git_ops | code_intel | spec    │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌──────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ Safety       │  │ Trace      │  │ MCP      │  │
│  │ Checkpoints  │  │ Logger     │  │ Client/  │  │
│  │ Permissions  │  │ (JSONL)    │  │ Server   │  │
│  └──────────────┘  └────────────┘  └──────────┘  │
└──────────────────┬───────────────────────────────┘
                   │ Docker API
┌──────────────────▼──────────────────────────────┐
│              Docker Sandbox                      │
│  network=none | 512MB RAM | 120s timeout         │
│  python-sandbox (pytest) | node-sandbox (jest)   │
└─────────────────────────────────────────────────┘
```

## Key Modules

### Agent Loop (`guardian/loop.py`)
Deterministic state machine: IDLE → PLANNING → ACTING → VERIFYING → COMPLETE/FAILED/REVERTED.
Each iteration runs Plan → Act → Verify. Max 3 iterations by default.

### LLM Client (`guardian/llm/`)
- **OllamaClient**: Local inference via Ollama HTTP API (zero cost)
- **MockLLMClient**: For testing with pre-configured responses
- **Structured output**: Validates LLM JSON against Pydantic schemas with retry

### Tool System (`guardian/tools/`)
- **Registry**: JSON Schema-based discovery, budget enforcement (max 50 calls)
- **file_ops**: read, write, search (ripgrep + fallback), tree
- **git_ops**: status, diff, branch, commit
- **code_intel**: regex-based framework detection + endpoint extraction (Flask, FastAPI, Express)
- **spec_parser**: OpenAPI 3.x + Swagger 2.x parsing

### Safety (`guardian/safety/`)
- **Checkpoints**: Snapshot files before modification, restore on revert
- **Permissions**: plan (read-only), default (approve each write), trust (auto-approve)
- **Command allowlist**: Only pytest, npm test, vitest, go test, ruff, mypy, eslint

### Sandbox (`guardian/sandbox/`)
- **runner**: Docker container lifecycle with resource limits
- **result_parser**: Structured parsing of pytest/jest output

### MCP (`guardian/mcp/`)
- **Client**: Connect to external MCP servers (GitHub), discover tools
- **Server**: Expose generate_api_tests, run_test_suite, detect_api_framework

### Evaluation (`guardian/eval/`)
- **Harness**: Run against 3 demo repos, measure detection rate + accuracy
- **Target**: 80%+ endpoints detected, 100% framework accuracy

## Data Flow

1. CLI sends `POST /init` → backend detects framework + endpoints
2. CLI sends `POST /run` → backend starts SSE stream
3. **PLAN**: LLM reads repo, outputs AgentPlanSchema (endpoints, steps, test files)
4. **ACT**: LLM generates test code, checkpoint system snapshots files
5. **VERIFY**: Tests run in Docker sandbox, results parsed
6. If tests fail → iterate (back to ACT with feedback)
7. If tests pass → COMPLETE, CLI shows approval gate
8. User can apply, reject (revert), edit, or iterate

## Directory Structure

```
test-guardian/
├── packages/
│   ├── cli/          TypeScript CLI (React Ink)
│   └── shared/       Shared TypeScript types
├── agent/
│   └── src/guardian/  Python agent backend
│       ├── llm/       LLM client + prompts + schemas
│       ├── tools/     File, git, code intel, spec parser
│       ├── safety/    Checkpoints + permissions
│       ├── sandbox/   Docker sandbox runner + parser
│       ├── mcp/       MCP client + server
│       ├── eval/      Evaluation harness
│       ├── trace/     JSON Lines trace logger
│       ├── loop.py    Agentic state machine
│       └── server.py  FastAPI HTTP server
├── sandbox/
│   ├── python/        Python sandbox Dockerfile
│   └── node/          Node sandbox Dockerfile
├── demo/
│   ├── flask-todo-api/
│   ├── fastapi-notes/
│   └── express-users-api/
└── .github/workflows/  CI pipeline
```
