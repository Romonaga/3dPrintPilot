# 3dPrintPilot

Local-first 3D printer compatibility dashboard with LAN printer discovery, deterministic compatibility checks, Ollama-first AI assistance, and OpenAI fallback cost accounting.

## Current Shape

- Backend: Python, FastAPI
- Frontend: React, TypeScript, Vite
- Database target: PostgreSQL with Alembic migrations
- Reusable accounting package: `local_ai_accounting`

## Development

Copy the example environment file when local settings need to be explicit:

```bash
cp Documentation/examples/printpilot.env.example .env
```

Start local Postgres:

```bash
docker compose up -d postgres
uv run alembic upgrade head
```

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

## User Service

The repository includes a systemd user service setup for running the local
backend and frontend together without root:

```bash
cd frontend
npm install
cd ..
scripts/install-user-service.sh
```

The installer writes `3dprintpilot.service` to `~/.config/systemd/user/`,
reloads the user systemd manager, enables the service, and starts or restarts
it. It records the current `uv` and `npm` executable paths in the rendered
unit, so rerun the installer if Node or `uv` move.

Useful commands:

```bash
systemctl --user status 3dprintpilot.service
journalctl --user -u 3dprintpilot.service -f
systemctl --user restart 3dprintpilot.service
systemctl --user disable --now 3dprintpilot.service
```

Optional runtime settings can be placed in
`~/.config/3dprintpilot/3dprintpilot.env`:

```bash
PRINTPILOT_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/printpilot
PRINTPILOT_BACKEND_HOST=0.0.0.0
PRINTPILOT_BACKEND_PORT=8001
PRINTPILOT_FRONTEND_HOST=0.0.0.0
PRINTPILOT_FRONTEND_PORT=5173
```

The service starts when the user logs in. To allow it to start before login,
enable linger for the user:

```bash
loginctl enable-linger "$USER"
```

Runtime check:

```bash
scripts/check-runtime.sh
```

The service uses strict configured ports. If a port is already occupied, update
`PRINTPILOT_BACKEND_PORT` or `PRINTPILOT_FRONTEND_PORT` in the service env file
and rerun `scripts/install-user-service.sh`.

If Postgres is intentionally unavailable during a frontend/backend smoke test:

```bash
PRINTPILOT_SKIP_DB_CHECK=1 scripts/check-runtime.sh
```

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
