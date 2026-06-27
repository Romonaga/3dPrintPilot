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
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8002
```

Frontend:

```bash
cd frontend
npm run dev
```

Current dev URLs:

- Frontend: http://localhost:8001/
- Local DNS frontend: http://3dprintpilot.local/
- Direct local DNS frontend: http://3dprintpilot.local:8001/
- Backend: http://localhost:8002/
- Backend health: http://localhost:8002/api/health

Port 8001 is reserved for the browser-facing web endpoint; the backend API runs
on port 8002 by default and is proxied by the frontend dev server.
For no-port browser access, map `3dprintpilot.local` to the host LAN IP in
`/etc/hosts`, then install the local port-80 proxy:

```bash
scripts/install-web-proxy.sh
```

The proxy uses `systemd-socket-proxyd` to forward `http://3dprintpilot.local/`
to the frontend on `127.0.0.1:8001`.

## System Service

The repository includes a systemd system service setup for running the local
backend and frontend together when the server boots. Install it from the account
that should run 3dPrintPilot; the installer uses `sudo` only for the systemd
unit installation and service control steps.

```bash
cd frontend
npm install
cd ..
scripts/install-system-service.sh
```

The installer writes `3dprintpilot.service` to `/etc/systemd/system/`, reloads
the systemd manager, enables the service for `multi-user.target`, and starts or
restarts it. It records the current `uv` and `npm` executable paths plus the
invoking user in the rendered unit, so rerun the installer if Node, `uv`, or the
service user should change.

Useful commands:

```bash
systemctl status 3dprintpilot.service
journalctl -u 3dprintpilot.service -f
sudo systemctl restart 3dprintpilot.service
sudo systemctl disable --now 3dprintpilot.service
```

Optional runtime settings can be placed in
`/etc/3dprintpilot/3dprintpilot.env`. For migration convenience, the rendered
unit also reads the installing user's
`~/.config/3dprintpilot/3dprintpilot.env` when it exists:

```bash
PRINTPILOT_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/printpilot
PRINTPILOT_BACKEND_HOST=0.0.0.0
PRINTPILOT_BACKEND_PORT=8002
PRINTPILOT_FRONTEND_HOST=0.0.0.0
PRINTPILOT_FRONTEND_PORT=8001
```

The service starts at server boot and does not require a user login session.

Runtime check:

```bash
scripts/check-runtime.sh
```

To include the no-port DNS endpoint in the smoke check:

```bash
PRINTPILOT_PUBLIC_URL=http://3dprintpilot.local PRINTPILOT_SKIP_DB_CHECK=1 scripts/check-runtime.sh
```

The service uses strict configured ports. If a port is already occupied, update
`PRINTPILOT_BACKEND_PORT` or `PRINTPILOT_FRONTEND_PORT` in the service env file
and rerun `scripts/install-system-service.sh`.

If Postgres is intentionally unavailable during a frontend/backend smoke test:

```bash
PRINTPILOT_SKIP_DB_CHECK=1 scripts/check-runtime.sh
```

## Authentication

On a fresh install with no users, create the first owner in the UI or with:

```bash
uv run scripts/bootstrap-owner.py --username owner
```

The command prompts for the password without echo. After the first user exists,
API routes that read or mutate provider secrets, AI budget data, printer
inventory, site scans, and compatibility checks require a bearer session token.
Owners include admin access; admins include user and viewer access.

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
