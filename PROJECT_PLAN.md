# 3dPrintPilot Project Plan

Created: 2026-06-13

## Project Goal

3dPrintPilot will be a local-first web application for discovering 3D printers on the LAN, storing printer capabilities, importing model information from files or supported 3D model websites, and checking model compatibility against available printers and materials.

The app should support multiple local users even when deployed only on a trusted LAN. It should also include an AI layer that uses Ollama first and escalates to OpenAI only when the local result is low quality, ambiguous, or missing important evidence.

## Recommended Stack

- Backend: Python, FastAPI, Pydantic, SQLAlchemy or SQLModel, Alembic
- Frontend: React, TypeScript, Vite
- Database: PostgreSQL
- Local AI: Ollama
- Paid AI fallback: OpenAI Responses API
- 3D model analysis: `trimesh`, `numpy-stl`, and later 3MF-specific parsing
- Network discovery: `zeroconf`, socket probes, `httpx`
- Background jobs: start simple with in-process workers, then move to a separate worker process if needed
- Packaging later: Tauri if we want a desktop app feel

## Current Host Snapshot

Measured on 2026-06-13:

- GPU: NVIDIA GeForce RTX 3090
- VRAM: 24,576 MiB total, 3,154 MiB used during sampling
- GPU load during sampling: 26%
- GPU temperature during sampling: 43 C
- CPU: AMD Ryzen 9 9950X3D, 16 cores / 32 threads
- RAM: 123 GiB total, 70 GiB available during sampling
- Ollama models currently installed:
  - `electronics-helper:latest`, 18 GB
  - `qwen3-coder:30b`, 18 GB

This host can support a serious local model, but the RTX 3090 should still be treated as a constrained shared resource. The first implementation should default local LLM concurrency to 1, cap context size, cap output tokens, and queue GPU work.

## Application Shape

```text
React UI
  |
  v
FastAPI backend
  |
  |-- PostgreSQL
  |-- LAN printer discovery
  |-- printer API adapters
  |-- model file analyzer
  |-- compatibility rules engine
  |-- Ollama provider
  |-- OpenAI fallback provider
  |-- GPU/CPU resource monitor
  |-- background worker
```

The browser should not scan the network or hold provider keys. The FastAPI backend owns LAN scanning, API keys, model analysis, AI calls, compatibility checks, and usage accounting.

## Users And Access

Even for LAN-only use, add users from the beginning.

Initial roles:

- Owner: full system setup, user management, provider keys, pricing, budgets
- Admin: manage printers, materials, model imports, and compatibility rules
- User: upload/import models, run checks, view their own AI usage
- Viewer: read-only access to printers, models, and reports

Auth plan:

- Store users in Postgres.
- Store password hashes with bcrypt or argon2.
- Store sessions as random tokens hashed in the DB.
- Add force-password-change for admin-created temporary passwords.
- Add `is_active`, `disabled_at`, failed login counters, and last login timestamps.
- Add optional per-user OpenAI key later, but start with system-level key only.

CircuitShelf reference patterns worth reusing conceptually:

- `db/users.py`: local user/session model with password hashing and active-user checks.
- `backend/auth_dependencies.py`: FastAPI dependency layer for required user/admin access.
- `tools/db_user.py`: CLI-style bootstrap for first admin user.

## Database Design

Use `bigint generated always as identity` primary keys for ordinary app tables. Use UUIDs only where externally exposed IDs are useful. Index all foreign keys and common filters.

Core tables:

```text
users
user_sessions
user_roles or role enum
audit_events

printers
printer_endpoints
printer_capabilities
printer_material_profiles
printer_status_samples
network_scan_runs
network_scan_results

materials
model_sources
model_site_adapters
model_site_scan_runs
model_site_scan_results
models
model_files
model_geometry
compatibility_checks
compatibility_check_items

settings
secret_refs

ai_providers
ai_provider_keys
ai_models
ai_model_pricing
ai_requests
ai_responses
ai_usage_events
ai_quality_scores

resource_samples
local_gpu_work_queue
background_jobs
```

Important indexes:

- Every foreign key column.
- `users(username)` unique.
- `user_sessions(token_hash)`.
- `printers(owner_user_id)`, `printers(is_active)`.
- `printer_endpoints(printer_id)`, `printer_endpoints(host, port)`.
- `network_scan_results(scan_run_id)`, `network_scan_results(host)`.
- `model_site_adapters(site_key)`.
- `model_site_scan_runs(requested_by_user_id, created_at)`.
- `model_site_scan_results(scan_run_id)`, `model_site_scan_results(source_url)`.
- `model_site_scan_results(site_key, external_model_id)`.
- `models(created_by_user_id)`, `models(source_url)`.
- `compatibility_checks(model_id)`, `compatibility_checks(requested_by_user_id)`.
- `ai_usage_events(user_id, created_at)`.
- `ai_usage_events(provider, model_name, created_at)`.
- `ai_usage_events(task_type, created_at)`.
- `resource_samples(sampled_at)`.
- `local_gpu_work_queue(status_id, resource_class, priority, created_at)`.

Postgres operational notes:

- Use connection pooling if this becomes multi-user or runs behind a process manager.
- Keep transactions short around scans and AI logs.
- Use JSONB for provider-specific raw payloads, but keep reportable fields as normal columns.
- Use migrations from the start.

## Printer Discovery

Discovery should be backend-only.

Initial methods:

- mDNS/zeroconf service discovery.
- Known HTTP/API port probes.
- Optional CIDR scan configured by admin.

Targets to support first:

- OctoPrint: common HTTP API patterns.
- Klipper/Moonraker: common `7125` API.
- PrusaLink: local HTTP/API.
- Duet: local HTTP/API.
- Bambu: later, because LAN/auth behavior is more complex.

Discovery result should never blindly add a printer. It should create a scan result and let an admin confirm, name, and configure credentials.

Detailed LAN port, protocol, MQTT, and safe probing rules are captured in
`docs/printer-protocol-discovery.md`. The key rule is that open ports are not
printer proof: MQTT requires a CONNACK, and HTTP(S) requires known printer
markers or API responses.

## Model Import And Compatibility

Start with actual uploaded files because website metadata is inconsistent.

MVP import paths:

- Upload STL.
- Upload 3MF.
- Paste model URL and store it as source metadata.
- Later, add supported website import adapters where allowed.

Compatibility checks:

- Model bounding box vs build volume.
- Material vs printer/hotend/nozzle/enclosure capability.
- Nozzle size vs model detail and filament type.
- Bed/nozzle temperature requirements.
- Enclosure requirement.
- Abrasive filament warning.
- Flexible filament warning.
- Multi-material or color requirement.
- File type support.
- Printer online/offline/status if an API is configured.

The first compatibility engine should be deterministic rules. AI can explain ambiguous findings, enrich missing metadata, or summarize the report, but it should not be the only source of truth.

## Website Discovery And Import

The product goal is not just uploading one file at a time. 3dPrintPilot should
also help a user find printable files from supported 3D model sites and quickly
answer: "Which of my detected printers can print this?"

Use a supported-site adapter model instead of a general unrestricted scraper.
Each adapter should declare:

- site key and display name
- allowed discovery method: public API, RSS/feed, sitemap, or page metadata fetch
- robots/terms notes checked by an admin or developer
- rate limit and retry policy
- crawl depth limit
- maximum pages/results per run
- maximum runtime per run
- allowed domains and same-site policy
- supported URL patterns
- metadata fields it can extract reliably
- whether direct file download is allowed or only source linking is allowed

Initial site-import workflow:

1. User enters a supported site URL, search URL, collection URL, or model page URL.
2. Backend creates a `model_site_scan_run`.
3. Site adapter fetches allowed metadata with rate limiting.
4. Store each candidate as a `model_site_scan_result` with source URL, title,
   author, license, tags, description excerpt, images, download metadata when
   allowed, and raw adapter payload.
5. Extract likely print requirements:
   - file formats: STL, 3MF, STEP, G-code, etc.
   - dimensions when published
   - material hints
   - nozzle hints
   - layer height / support / infill notes
   - multi-material or color requirements
   - printer-specific notes from the model page
6. If the site allows file download, enqueue file analysis for real geometry.
   If not, keep the result as metadata-only until the user manually uploads the
   file or opens the source site.
7. Run compatibility against confirmed LAN printers:
   - geometry-backed checks when a file is available
   - metadata-backed checks when only page data is available
   - mark confidence clearly for each result
8. Show results as Compatible, Maybe, Not Compatible, or Needs File, with the
   evidence that drove the decision.

Crawler limits should be enforced by the shared crawl runner before adapter code
can enqueue more work. Default limits should be conservative:

- default depth: 1 from the user-provided URL
- maximum configurable depth: 3 unless the admin explicitly raises it
- default result/page limit: 50 per scan run
- default runtime limit: 5 minutes per scan run
- same-domain only unless the adapter explicitly allows known CDN/API hosts
- no recursive crawling from arbitrary external links
- per-host request delay and concurrency of 1 by default
- stop early when enough printable candidates have been found

Each queued URL should store its `depth`, `parent_url`, `normalized_url`, and
reason for inclusion. This makes scan behavior auditable and prevents accidental
deep crawls.

AI should be used as an enrichment layer for website imports, not as the first
source of truth. Deterministic parsing and file geometry win when available.
Ollama can classify page descriptions and extract candidate print requirements.
OpenAI can be used only when the local confidence score is low and the user's
settings/budget allow fallback.

Important safety and quality rules:

- Respect site terms, robots.txt, and rate limits.
- Prefer official APIs or feeds when available.
- Enforce crawl depth, page count, runtime, domain, and concurrency limits.
- Do not bypass authentication, paywalls, anti-bot systems, or download gates.
- Store license and attribution metadata so users know how a model can be used.
- Keep source URL and extraction evidence with every compatibility decision.
- Clearly label metadata-only compatibility as lower confidence than geometry-backed compatibility.
- Let admins enable or disable each site adapter.

## AI Architecture

Use a provider abstraction:

```text
AI task request
  |
  v
Prompt builder with strict output schema
  |
  v
Ollama provider
  |
  v
Quality scorer
  |
  | if score is low or escalation requested
  v
OpenAI provider
  |
  v
Normalize response, log usage, store quality score
```

Initial AI tasks:

- Explain compatibility report.
- Extract model/material requirements from model descriptions.
- Triage website metadata quality.
- Suggest printer profile fixes.
- Summarize why a model failed compatibility.

Do not start with full fine-tuning. Start with:

- Ollama Modelfile for 3D-printing behavior.
- A small local knowledge base of printer/material rules.
- RAG over saved printer docs and imported model metadata.
- Structured JSON outputs for all compatibility-relevant AI tasks.

Later, if we collect enough labeled examples, add fine-tuning or a stronger local specialized model.

## Ollama Usage Tracking

Track local AI usage even when cost is zero.

For each local AI call, store:

- provider: `ollama`
- model name
- task type
- user ID
- input token estimate
- output token estimate
- context type and context ID
- latency
- success/error
- quality score
- whether OpenAI escalation was requested
- GPU queue wait time
- GPU pressure snapshot

Ollama does not have OpenAI-style billing, so token counts can start as estimates. The important part is tracking load, frequency, user, task type, latency, and whether the local model was good enough.

## OpenAI Fallback And Accounting

Use OpenAI only when:

- Ollama result score is below the configured threshold.
- Required facts are missing.
- The local response fails schema validation.
- The user/admin explicitly requests paid escalation.

Use the OpenAI Responses API. The API response includes usage fields such as input tokens, cached input tokens, output tokens, reasoning tokens, and total tokens. Store those raw fields and calculate per-call estimated cost immediately.

Cost estimate:

```text
regular_input_tokens = input_tokens - cached_input_tokens

estimated_cost =
  regular_input_tokens * input_rate_per_1m / 1_000_000
+ cached_input_tokens * cached_input_rate_per_1m / 1_000_000
+ output_tokens * output_rate_per_1m / 1_000_000
+ tool_call_costs
```

OpenAI cost verification is a required product feature. The app can run in an
`estimated only` state until an OpenAI admin API key is configured, but the
settings and usage screens must clearly show that costs are not yet verified.
Once the admin key is configured, run scheduled reconciliation against OpenAI
organization cost/usage data and compare daily totals against local per-call
estimates.

Store both numbers:

- local estimated cost, calculated immediately from response usage and cached pricing
- verified OpenAI cost, fetched from OpenAI cost/usage reporting

If the numbers differ beyond a small tolerance, flag the day/model/task group as
`needs_review` instead of silently replacing local estimates.

## Reusable AI Cost Toolkit

Build the OpenAI cost estimation and verification code as a reusable internal
Python package instead of burying it inside 3dPrintPilot. The goal is for
3dPrintPilot, CircuitShelf, and future local apps to use the same code path for
OpenAI pricing, usage accounting, reconciliation, and CSV/report exports.

Proposed package name:

```text
local_ai_accounting
```

Initial module shape:

```text
local_ai_accounting/
  __init__.py
  models.py
  pricing.py
  openai_admin_client.py
  estimate.py
  reconcile.py
  reports.py
  storage.py
```

Responsibilities:

- Normalize OpenAI response usage into one app-independent usage event shape.
- Calculate local estimated cost from token counts and stored pricing.
- Fetch OpenAI organization costs with an admin API key.
- Fetch OpenAI organization usage with an admin API key.
- Reconcile local estimates against final OpenAI-reported costs.
- Return `estimated_cost`, `final_cost`, `cost_status`, discrepancy, and reconciliation metadata.
- Provide framework-neutral report/export helpers.

The shared package should not know about printers, models, electronics parts, or
any application-specific database schema. Each app should provide a small storage
adapter with methods like:

```text
list_estimated_events(start, end)
save_reconciliation_run(run)
update_event_final_cost(event_id, final_cost, status)
save_daily_rollup(rollup)
```

This lets CircuitShelf adopt the same cost verification logic without forcing
both apps to share the same tables. If both apps eventually converge on a common
schema, the adapter can become a reusable Postgres implementation.

Cost fields every adopting app should support:

```text
estimated_cost_usd
final_cost_usd
cost_status
cost_reconciled_at
cost_source
cost_discrepancy_usd
reconciliation_run_id
```

Recommended statuses:

- `estimated`: local estimate exists, no final OpenAI reconciliation yet
- `verified`: final cost matched local estimate within tolerance
- `adjusted`: final cost differs but was reconciled successfully
- `needs_review`: mismatch, missing API data, or allocation ambiguity
- `not_billable`: local Ollama or zero-cost task

Implementation note: OpenAI cost data is naturally reported in buckets and may
not map one-to-one to individual app calls. The toolkit should reconcile at the
most precise stable grouping available, then allocate final cost back to events
proportionally by estimated cost or token usage. Store the grouping method so
reports are honest about how final cost was assigned.

OpenAI references:

- Responses API: https://api.openai.com/v1/responses
- Organization costs API: https://api.openai.com/v1/organization/costs
- Organization completions usage API: https://api.openai.com/v1/organization/usage/completions
- Official pricing page: https://openai.com/api/pricing/

Pricing note from the current pricing page sampled on 2026-06-13:

- GPT-5.5: input $5.00 / 1M tokens, cached input $0.50 / 1M tokens, output $30.00 / 1M tokens.
- GPT-5.4: input $2.50 / 1M tokens, cached input $0.25 / 1M tokens, output $15.00 / 1M tokens.
- GPT-5.4 mini: input $0.75 / 1M tokens, cached input $0.075 / 1M tokens, output $4.50 / 1M tokens.
- Web search tool: $10.00 / 1K calls.

These rates must be stored in the DB with `fetched_at` and allow manual override because pricing can change.

## AI Settings Screen

Settings sections:

- Local AI
  - Ollama base URL
  - primary model
  - custom 3D-print model name
  - local concurrency
  - local context token cap
  - local output token cap
  - keep-alive setting
  - GPU queue timeout

- OpenAI
  - enable/disable OpenAI fallback
  - API key status, masked after save
  - optional admin API key status, masked after save
  - fallback model
  - reasoning effort
  - max output tokens
  - daily/monthly budget
  - warning threshold
  - hard stop threshold

- Pricing
  - refresh pricing button
  - current model rates
  - manual overrides
  - last fetched time
  - source URL

- Usage
  - local usage summary
  - OpenAI usage summary
  - OpenAI verified-vs-estimated cost comparison
  - reconciliation status and last successful sync time
  - warnings for unreconciled or mismatched billing periods
  - estimated spend by day/user/task/model
  - CSV export

- Hardware Controls
  - GPU telemetry
  - CPU/RAM telemetry
  - max local LLM queue depth
  - max concurrent GPU tasks
  - VRAM guard threshold
  - thermal guard threshold
  - recent OOM cooldown

Secrets:

- Never send raw provider keys back to the frontend.
- Store provider keys encrypted in Postgres or as OS-protected secret files with DB references.
- Prefer environment variables or root-owned secret files for system keys.
- Use the home `pwd.txt` only if an elevated provisioning action actually requires it; normal app runtime should not depend on sudo.

## GPU And CPU Resource Controls

The app should treat local AI and model analysis as schedulable work.

Controls to implement:

- Single local LLM concurrency by default.
- GPU work queue with resource classes:
  - `local_llm`
  - `model_geometry`
  - `slicer_preview` later
  - `vision_analysis` later
- Admission control based on:
  - GPU utilization
  - VRAM used percent
  - temperature
  - recent CUDA/OOM failures
  - queue wait time
- Per-task prompt caps:
  - max input characters
  - max retrieved chunks
  - max context tokens
  - max output tokens
- Backoff behavior:
  - moderate pressure: reduce admitted tasks
  - high pressure: reduce more aggressively
  - hard guard: allow only one task or block new work temporarily
  - OOM: cooldown before more GPU-heavy work

CircuitShelf patterns worth modeling:

- `backend/services/gpu_work_queue.py`: queue, resource classes, OOM cooldown, adaptive slot logic.
- `backend/services/ollama_chat_client.py`: local LLM request gate, Ollama `num_ctx`, `num_predict`, `keep_alive`, and queue timeout.
- `db/performance_store.py`: resource samples and recent work reporting.
- `backend/services/resource_sensors.py`: `nvidia-smi`, CPU, RAM, process telemetry.

For the RTX 3090, first defaults should be conservative:

- local LLM concurrency: 1
- local LLM queue timeout: 300 seconds
- VRAM moderate threshold: around 78%
- VRAM high threshold: around 84%
- VRAM hard threshold: around 88%
- thermal hard threshold: around 82 C
- keep at least several GiB of VRAM headroom for the OS, Ollama overhead, and transient allocations

## Background Worker

Start with one backend process and one optional worker process.

Worker jobs:

- network scans
- model file analysis
- website metadata fetch/import
- AI enrichment
- OpenAI reconciliation
- pricing refresh
- resource sampling

Use a Postgres-backed job table at first. If job volume grows, move to Redis/RQ, Dramatiq, Celery, or another queue.

## Security And LAN Boundaries

Local LAN does not mean no security.

Rules:

- Require login once any user exists.
- First run should require creating the owner/admin account.
- Restrict settings and provider keys to owner/admin.
- Audit changes to users, providers, printer credentials, and budgets.
- Keep printer API credentials encrypted or in OS-protected files.
- Never expose OpenAI keys or printer keys in API responses.
- Add CSRF protection if using cookies.
- Bind to LAN intentionally; default to localhost during development.

## MVP Plan

### Phase 0: Repo And Project Foundation

- Create FastAPI backend skeleton.
- Create React/Vite frontend skeleton.
- Add Docker Compose or local config for Postgres.
- Add Alembic migrations.
- Add app config loading.
- Add basic logging.
- Add health endpoint.

### Phase 1: Users And Settings

- Create users, sessions, roles, and password policy tables.
- Add first-admin bootstrap command.
- Add login/logout/me endpoints.
- Add settings storage.
- Add masked secret storage for OpenAI and printer credentials.
- Add settings UI shell.

### Phase 2: Hardware And Worker Controls

- Add resource sampling endpoint.
- Add GPU/CPU/RAM status cards.
- Add local GPU work queue.
- Add Ollama status check.
- Add local LLM request gate.
- Add resource sample storage.
- Add queue and resource settings UI.

### Phase 3: Printer Inventory And Discovery

- Add printer tables.
- Add manual printer creation.
- Add mDNS discovery.
- Add HTTP probe discovery.
- Add scan results UI.
- Add admin confirmation flow for discovered printers.
- Add OctoPrint and Moonraker adapters first.

### Phase 4: Model Import And Geometry

- Add model upload.
- Add STL parsing.
- Add 3MF parsing.
- Store bounding box, volume, triangle count, units, and warnings.
- Add model list/detail UI.
- Add URL source metadata.

### Phase 5: Compatibility Engine

- Add deterministic compatibility rules.
- Add material profiles.
- Add printer capability editor.
- Add compatibility run endpoint.
- Add report UI with compatible / maybe / not compatible results.

### Phase 6: AI Provider Layer

- Add Ollama provider.
- Add structured AI task runner.
- Add local token estimates and AI usage logs.
- Add quality scorer.
- Add OpenAI provider using Responses API.
- Add reusable `local_ai_accounting` package for OpenAI estimate/final cost handling.
- Add OpenAI cost estimate using DB pricing through the shared package.
- Add OpenAI cost verification/reconciliation against organization cost/usage reporting through the shared package.
- Add budget enforcement.
- Add usage reports and CSV export.

### Phase 7: Website Imports

- Add per-site import adapter interface.
- Add `model_site_adapters`, `model_site_scan_runs`, and `model_site_scan_results` tables.
- Start with metadata-only URL capture for arbitrary URLs.
- Add one supported adapter end to end before adding more sites.
- Store source URL, license, attribution, extracted requirements, raw payload, and confidence.
- Add rate limits and admin enable/disable controls per adapter.
- Add crawl depth, page count, runtime, allowed-domain, and concurrency limits.
- Add compatibility results for metadata-only candidates with clear confidence labels.
- Add geometry-backed compatibility when downloadable files or user uploads are available.
- Add supported adapters only where terms/API behavior allows it.
- Use AI only to enrich or classify uncertain metadata, not as the sole compatibility source.

### Phase 8: Polish And Packaging

- Add tests for key stores, compatibility rules, printer adapters, AI usage, and GPU queue.
- Add admin backup/export.
- Add systemd service files.
- Add optional Tauri wrapper.

## First Implementation Checklist

1. Initialize backend and frontend project structure.
2. Add Postgres connection and migrations.
3. Add user/session/auth foundation.
4. Add settings and secret handling.
5. Add hardware status endpoint.
6. Add Ollama connectivity test endpoint.
7. Add printer schema and manual printer entry.
8. Add STL upload and geometry extraction.
9. Add first deterministic compatibility check.
10. Add AI usage schema before making any AI calls.

## Open Questions

- Should users be independent local accounts only, or should there be teams/workspaces later?
- Should OpenAI billing be system-wide only at first, or should users be allowed to bring their own key?
- Which printer brand/API should be first after manual printer profiles?
- Which 3D model website should be the first import target?
- Should the app bind to localhost only at first or immediately support LAN access?
