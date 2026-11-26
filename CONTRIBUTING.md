# Contributing to TravelAI

Thanks for your interest! Issues and PRs are welcome.

## Development setup

Follow the [Quick Start](README.md#-quick-start-docker-recommended) in the README — Docker Compose for the full stack, or backend + frontend separately for local dev.

## Running checks

```bash
# Syntax check (same as CI)
python -m compileall -q backend

# End-to-end test (with the backend running)
python backend/scripts/e2e_test.py

# Frontend type/build check
cd frontend && npm install && npm run build
```

## Guidelines

- **Open an issue first** for major changes so we can discuss the approach.
- Keep PRs focused — one feature or fix per PR.
- Keep frontend TypeScript interfaces aligned with backend Pydantic schemas.
- New workflow nodes belong in `backend/app/agent/nodes.py` and must be wired in `graph.py`.
- Never commit `.env`, databases, or vector store data — `.gitignore` covers them.

## Good first issues

Look for issues labeled `good first issue` — e.g. keyless live weather, semantic embeddings by default, more seed attractions, demo GIF.