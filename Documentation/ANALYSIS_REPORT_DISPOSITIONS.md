# Analysis Report Dispositions

This note records the current-state disposition of the Verlyn analysis reports reviewed during changes 3dp-13 through 3dp-15. Verlyn remains the source of work truth for tickets, execution order, review evidence, and delivery state.

## Reports Reviewed

- `reports:review_overview`
- `reports:source_coverage_overview`
- `reports:test_intelligence_overview`
- `reports:code_smell_overview`
- `review_sheets:3dprintpilot`
- `review_sheets:3dprintpilot-frontend`
- `reports:security_audit_overview`
- `reports:risk_register`

## Dispositions

| Finding area | Disposition | Current evidence |
|---|---|---|
| Route-level authentication gaps | Fixed | Domain routes use `require_roles`; `tests/test_auth.py` now covers anonymous and low-privilege access across printer scan, site scan, resource, settings, AI reconciliation, model read, and backup-export boundaries. |
| Site scanning SSRF risk | Fixed with residual constraints | Site scanning is adapter-bound, enforces policy limits, and records requested user context. Residual risk is limited to trusted-LAN operation and public metadata fetches; keep future downloader work behind explicit adapter allow-lists. |
| HTTPS probe verification disabled | Fixed | 3dp-13 restored normal certificate verification for HTTP/HTTPS probing. The remaining `verify=False` path is scoped to Bambu MQTT-over-TLS LAN discovery, is read-only, and is documented inline as device-discovery behavior. |
| LAN printer scan single-worker failure | Fixed | 3dp-13 made scan collection tolerate individual worker failures and added regression coverage for partial results. |
| Database pool bounds | Fixed | 3dp-13 added explicit non-SQLite pool size, overflow, timeout, recycle, and pre-ping settings with runtime-foundation coverage. |
| Frontend API timeout/cancellation | Fixed | 3dp-14 added `apiFetch` timeout handling, signal support, printer/site scan longer timeouts, and direct tests. |
| OpenAI reconciliation date handling | Fixed | 3dp-14 added strict `YYYY-MM-DD` validation and UTC ISO conversion coverage before posting reconciliation ranges. |
| Frontend API adapter direct coverage | Fixed | 3dp-14 added direct adapter tests for AI usage, printers, compatibility, settings, site scanning, and operations backup behavior. |
| App shell/navigation coverage | Fixed | 3dp-15 adds direct `AppShell` coverage for active navigation, user context, theme toggle, route changes, logout, and child rendering. |
| Broad direct AI review coverage | Deferred | Current tests cover accounting status, reconciliation validation, and adapter behavior. Full provider-contract replay tests should be added when real provider integrations or recorded fixtures are introduced. |
| Coupling and monolith smells | Deferred | The app has been split into domain modules and lazy-loaded pages. Further decomposition should be handled only when a domain change needs it, to avoid unrelated refactors. |
| Packaging and restore import | Deferred | Tauri packaging and restore import remain product decisions called out in operations guidance; backup export is covered and provider secrets remain redacted. |

## Residual Risks

- LAN operation assumes a trusted local network. Do not expose the service beyond a trusted LAN without a separate hardening pass for TLS termination, firewalling, CORS, session duration, and audit logging.
- Bambu MQTT discovery still allows an unverified LAN TLS handshake because many devices expose local certificates that are not publicly trusted. Keep that exception read-only and isolated to discovery.
- Analysis reports are snapshots. Re-run Verlyn analysis after major feature batches instead of treating this document as a live report.
