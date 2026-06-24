# Moonraker Agent Architecture Decision

## Decision

Do not build or ship a 3DPrintPilot Moonraker agent yet. Continue using direct
Moonraker object queries, optional standard integrations, and allowlisted
extension-agent calls as the production path.

Build a 3DPrintPilot agent only when a printer needs normalized local behavior
that cannot be represented safely through existing Moonraker APIs.

## Current Capability Path

3DPrintPilot now has a layered Moonraker path:

1. Standard Moonraker printer objects for job state, temperatures, files, and
   controls.
2. Vendor-specific printer objects for printer-native slot metadata, such as
   Snapmaker U1 `filament_detect.info`.
3. Standard integrations such as Spoolman for active spool metadata.
4. Allowlisted extension-agent requests through Moonraker.
5. Saved capability metadata as fallback.

This order keeps live printer truth first while preventing optional integrations
from blocking core telemetry.

## Agent Use Cases

A 3DPrintPilot-controlled Moonraker agent may be justified for:

- normalizing vendor-specific slot, spool, sensor, or camera state near the
  printer;
- exposing a stable method contract for data that Moonraker does not
  standardize;
- aggregating local data sources that are not reachable from the web service;
- reducing repeated vendor-object parsing in the web app once multiple printer
  families need custom behavior.

## Required Contract

Before implementation, the agent contract must define:

- transport: WebSocket or Unix socket connection to Moonraker;
- identity: agent name, version, and URL shown through
  `/server/extensions/list`;
- method namespace: stable methods such as `3dprintpilot.telemetry`;
- request and response schemas;
- timeout and retry behavior;
- auth expectations for the Moonraker connection;
- install, upgrade, and removal flow;
- supported operating systems and service manager assumptions.

## Security Boundary

The agent must not become a generic command runner. 3DPrintPilot should call
only allowlisted methods, and any app API that relays those calls must require
an admin or owner role.

The agent must not receive provider tokens, Verlyn credentials, or unrelated
application secrets. It should return normalized printer data, not execute
arbitrary shell commands or expose raw local files.

## Prototype Gate

Prototype work should stay out of production until:

- a real printer need cannot be solved by object queries, Spoolman, or a vendor
  extension agent;
- request and response schemas are reviewed;
- install and rollback steps are documented;
- the security boundary is reviewed;
- tests cover absent agent, malformed response, timeout, and version mismatch
  behavior.

## Rollback

If an agent prototype is abandoned, keep the existing direct Moonraker object
query path and remove only the agent package, install instructions, and
allowlisted method registration for that prototype.
