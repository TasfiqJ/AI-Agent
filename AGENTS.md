# AGENTS.md

## Project
test-guardian — agentic CLI for automated API test generation.

## Build
```bash
pnpm install          # Install all JS/TS dependencies
pip install -e agent/  # Install Python agent in editable mode
```

## Test
```bash
pnpm test                        # All TypeScript tests
cd agent && pytest               # All Python tests
cd agent && pytest -x -v         # Python tests, stop on first failure
```

## Lint
```bash
cd packages/cli && pnpm lint     # ESLint
cd agent && ruff check .         # Python lint
cd agent && mypy src/            # Python type check
```

## Style
- Python: ruff format, 88 char line length, type hints required on all public functions
- TypeScript: prettier, strict tsconfig, no implicit any
- Commits: conventional commits (feat:, fix:, refactor:, test:, docs:)
- PRs: one logical change per PR, tests required

## Architecture Rules
- LLM outputs must be Pydantic-validated before driving any action
- File writes use unified diff (no blind overwrite)
- Command execution only through Docker sandbox with allowlist
- Checkpoint files before modifying them
- Trace log every tool call and LLM response
