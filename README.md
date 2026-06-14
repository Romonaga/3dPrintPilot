# 3dPrintPilot

Local-first 3D printer compatibility dashboard with LAN printer discovery, deterministic compatibility checks, Ollama-first AI assistance, and OpenAI fallback cost accounting.

## Current Shape

- Backend: Python, FastAPI
- Frontend: React, TypeScript, Vite
- Database target: PostgreSQL with Alembic migrations
- Reusable accounting package: `local_ai_accounting`

## Development

Backend:

```bash
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8001
```

Frontend:

```bash
cd frontend
npm run dev
```

Current dev URLs:

- Frontend: http://localhost:5173/
- Backend: http://localhost:8001/
- Backend health: http://localhost:8001/api/health

Port 8000 was already in use on this machine, so the initial backend dev port is 8001.

## Tests

Backend and reusable Python packages:

```bash
uv run --all-extras pytest -q
```

Frontend:

```bash
cd frontend
npm test
npm run build
```

## Database

Set `PRINTPILOT_DATABASE_URL` for the local Postgres database, then run:

```bash
uv run alembic upgrade head
```

The first migration creates users, sessions, AI usage events, and AI cost reconciliation runs. AI usage stores both `estimated_cost_usd` and `final_cost_usd`.

