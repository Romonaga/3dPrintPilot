# 3dPrintPilot Engineering Guide

## Architecture

- Keep code separated by domain. Do not grow large monolithic modules.
- Backend code lives under `backend/domains/<domain_name>/`.
- Frontend code lives under `frontend/src/domains/<domain-name>/`.
- Shared frontend shell code lives under `frontend/src/app/`, `frontend/src/components/`, and `frontend/src/hooks/`.
- Reusable cross-app Python libraries live at the repo root as standalone packages, for example `local_ai_accounting/`.

## Backend

- Use Python package and file names in `snake_case`.
- Keep request and response schemas separate:
  - `schemas/request.py`
  - `schemas/response.py`
- Keep routes thin. Put business logic in `service.py` or focused helper modules.
- Keep database access behind store/repository classes rather than inline SQL inside routes.
- Route files should expose an `APIRouter`, not construct the whole app.
- Add tests for critical paths before or alongside implementation.

## Site Scanning

- Keep website discovery in `backend/domains/site_scanning/`.
- Use adapter classes for each supported site; do not add one-off scraper logic to routes.
- Enforce crawl depth, page count, runtime, domain, and concurrency limits in shared scanner code before adapter code can enqueue more work.
- Persist scan status, stop reason, counts, timing, limits, candidates, and rejection reasons so reports and charts can be built later.
- Prefer metadata-only capture until a site adapter is explicitly reviewed for allowed API/feed/page/download behavior.

## Frontend

- Use React, TypeScript, and Vite.
- Keep `App.tsx` as orchestration only: shell composition, lazy loading, and route/page selection.
- Use lazy loading for feature pages where practical.
- Keep components focused and reusable. Avoid large page files with all markup inline.
- Use hooks for stateful feature logic and data fetching.
- Keep domain-specific components inside their domain folder.
- Keep common UI primitives in `frontend/src/components/`.
- Do not use visible app text to explain implementation details.

## Testing

- Treat critical-path code as test-first or test-alongside.
- Prioritize tests for:
  - AI cost estimation and final reconciliation
  - auth/session behavior
  - printer discovery confirmation flows
  - compatibility rule decisions
  - GPU/resource queue admission
  - settings and secret masking
- Prefer small unit tests for deterministic logic and focused API tests for route behavior.

## Cost Accounting

- Every AI usage record must support estimated and final cost fields.
- OpenAI cost verification/reconciliation is required, not optional.
- Shared cost-reconciliation logic should be reusable by CircuitShelf and future apps.
