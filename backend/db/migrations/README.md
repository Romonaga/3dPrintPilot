Alembic migrations for 3dPrintPilot.

Start local Postgres with:

```bash
docker compose up -d postgres
```

Run migrations with:

```bash
uv run alembic upgrade head
```

Inspect the current database revision with:

```bash
uv run alembic current
```
