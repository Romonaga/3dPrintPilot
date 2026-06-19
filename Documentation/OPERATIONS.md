# 3dPrintPilot Operations

## Backup Export

Admins can export operational data from Settings > Operations > Export Backup, or by calling:

```bash
curl -H "Authorization: Bearer <token>" http://<host>:8000/api/operations/backup.json
```

The export includes printers, network scans, site scan adapters/runs/results, model metadata, compatibility checks, AI usage accounting, resource samples, and background jobs.

Provider secrets are intentionally redacted. The export includes only provider, secret name, last four characters, and timestamps so a restore operator knows which secrets must be reconfigured.

## Restore Guidance

Restore into a matching application schema version. Recreate the database from migrations, import table data in dependency order, then manually re-enter provider secrets in Settings. Confirm LAN binding, CORS, and firewall rules before exposing the service beyond a trusted LAN.

## LAN And Security Defaults

The app is intended for trusted local-network use. Default OpenAI fallback is disabled, provider secrets stay encrypted at rest, printer discovery uses bounded probes, site scanning is adapter-bound, and authenticated admin routes are required for provider secrets and backup export.

## Packaging Decision

Tauri desktop packaging is deferred. The web app workflows are usable and covered by tests, but packaging should wait until restore import, installer signing, and OS-specific secret storage requirements are designed.
