# Bambu LAN Roadmap

## Current Baseline

3DPrintPilot supports Bambu printers through the read-only LAN MQTT path:

- Discovery can identify Bambu LAN MQTT candidates on port 8883 without credentials.
- Saved Bambu MQTT printers can store a LAN access code encrypted in the existing secret store.
- Saved-card refresh can request read-only status and show job state, temperatures, AMS tray colors and materials, and error metadata.
- Control commands remain disabled. Raw gcode remains disabled.

The protocol details are community-derived. Bambu's public materials confirm LAN/Developer mode exists, but they do not publish a complete stable MQTT API contract. Treat model and firmware differences as expected until verified against the actual printers.

## Future Work Order

1. Camera discovery and preview

   - Detect model-specific camera transport after read-only MQTT is stable.
   - X/P/H-class printers may expose an RTSP-style stream; A/P-class printers may expose a TLS JPEG stream.
   - Store no camera credentials beyond the existing printer LAN secret.
   - Add explicit per-printer camera availability state before rendering previews.

2. File inventory

   - Read file lists only after confirming the local API shape for the target model.
   - Keep file browsing read-only at first.
   - Do not upload, delete, or start files from this phase.

3. Safe print controls

   - Add pause, resume, and stop only after read-only telemetry and file inventory are stable.
   - Require admin role and an explicit per-printer control enablement flag.
   - Log command intent and response metadata without logging LAN access codes.
   - Keep raw gcode disabled.

4. AMS actions

   - Add AMS operations only after tray status, active tray, RFID/read state, and error handling are verified.
   - Require admin role and explicit action confirmation for any operation that changes printer state.

5. Raw command handling

   - Do not add a raw command console by default.
   - Any future raw command capability requires a separate security review, an owner-controlled allowlist, clear audit records, and a rollback plan.

## Safety Gates

Any future Bambu write/control work must satisfy these gates before delivery:

- Read-only telemetry is stable for the target printer model and firmware.
- The action is scoped to a named command, not a generic publish channel.
- Admin/owner authorization is enforced server-side.
- LAN access codes remain encrypted and are never returned to the client.
- MQTT request payloads are generated from typed server-side structures.
- Rate limits prevent repeated `pushing.pushall` or command floods.
- UI copy explains LAN/Developer mode tradeoffs and model/firmware caveats.
- Rollback can disable the feature without removing discovery or read-only telemetry.

## Deferrals

- Cloud API integration is out of scope for the LAN-first path.
- Bambu Handy compatibility should be verified per model and firmware before making absolute claims.
- Raw gcode, AMS write actions, file mutation, and print start are deferred until separate tickets approve the safety model.
