# Printer Plugin Layering Contract

## Purpose

Printer support must stay layered as more protocols, makers, and printer models
arrive. Put behavior at the highest reusable layer that is still correct for the
evidence we have. Do not hide model-specific assumptions in generic engine code.

The layers are:

1. Engine
2. Maker adapter
3. Model profile

## Engine Layer

An engine owns the transport and protocol runtime. It should know how to connect,
authenticate, request data, enforce protocol safety boundaries, and return common
printer telemetry.

Examples:

- `moonraker`: Moonraker/Klipper HTTP APIs, object queries, files, print actions,
  extension-agent calls, and standard integrations such as Spoolman.
- `bambu_mqtt`: Bambu LAN MQTT over TLS, read-only report subscription, safe
  `pushing.pushall` request generation, and MQTT topic boundaries.
- Future engines: OctoPrint, PrusaLink, Duet, or generic MQTT.

Engine code may define:

- connection setup, timeout, retry, and auth shape;
- raw protocol request and response parsing;
- common telemetry contracts such as job state, temperatures, toolheads, files,
  and safe action results;
- safety defaults such as disabled raw command consoles.

Engine code must not contain maker-only payload assumptions unless that maker is
the engine's protocol identity, as with the current Bambu LAN MQTT path.

## Maker Adapter Layer

A maker adapter owns vendor semantics on top of an engine. It interprets vendor
payloads, normalizes capability names, and sets maker-specific defaults while
still using the engine's connection, auth, role, and safety boundary.

Examples:

- `snapmaker_moonraker`: Snapmaker semantics over the Moonraker engine.
- `creality_moonraker`: future Creality semantics over the Moonraker engine.
- `bambu_lan_mqtt`: Bambu printer semantics over the Bambu LAN MQTT engine.
- `generic_moonraker`: standard Moonraker behavior with no maker-specific
  assumptions.

Maker adapter code may define:

- vendor object names and their normalized meanings;
- maker-specific capability defaults;
- safe vendor extension methods;
- telemetry source priority inside that maker family;
- maker safety policy, such as keeping Bambu LAN MQTT read-only until a separate
  control ticket approves specific commands.

Maker adapters must not bypass engine authentication, transport restrictions,
server-side role checks, or raw command safety gates.

## Model Profile Layer

A model profile owns narrow printer-family or model-specific behavior. It is the
place for fields, object names, camera paths, AMS/toolhead mappings, or firmware
workarounds that are not proven reusable across the maker.

Examples:

- `snapmaker_u1`: Snapmaker U1 toolhead and filament slot metadata from
  `filament_detect.info` and related Moonraker objects.
- Future Bambu profiles for camera or file-access differences across A, P, X, or
  H series printers.
- Future Creality profiles for model-specific Moonraker objects, camera streams,
  or sensor naming.

Model profile code may define:

- object names, topic suffixes, and fields known only for that model family;
- firmware-specific parsing fallbacks with clear provenance;
- model-specific camera, AMS, or toolhead mappings;
- temporary compatibility workarounds.

Every model profile behavior needs a source: live printer evidence, documented
vendor behavior, or a clearly named community-derived protocol observation. Add
tests for the payload shape before relying on it in the UI.

## Promotion Rules

Promote behavior upward only when evidence shows it is broader than the current
layer:

- Move model profile behavior to a maker adapter after two or more model
  families share the same payload shape and semantics.
- Move maker adapter behavior to an engine only when the protocol standard, not
  the maker, defines it.
- Keep behavior in a lower layer when fields have the same names but different
  meanings, units, safety impact, or firmware stability.

Demote behavior when later evidence proves it was too broad. Demotion should
preserve the public response contract or include a migration note.

## Capability Metadata

Printer capabilities should expose enough metadata for the UI and future code to
understand which layer made a decision:

```json
{
  "adapter": "moonraker",
  "integration_layers": {
    "engine": "moonraker",
    "maker_adapter": "snapmaker_moonraker",
    "model_profile": "snapmaker_u1"
  },
  "telemetry_source_priority": [
    "moonraker_object",
    "vendor_object",
    "spoolman",
    "extension_agent",
    "saved_capabilities"
  ]
}
```

Use `engine` for the protocol runtime, `maker_adapter` for vendor semantics, and
`model_profile` for the narrow model or family override. Use `null` when a layer
is not applicable or not yet known.

## Current Mappings

| Printer path | Engine | Maker adapter | Model profile |
| --- | --- | --- | --- |
| Generic Moonraker/Klipper | `moonraker` | `generic_moonraker` | `null` |
| Snapmaker U1 through Moonraker | `moonraker` | `snapmaker_moonraker` | `snapmaker_u1` |
| Future Creality through Moonraker | `moonraker` | `creality_moonraker` | model-specific profile when evidence requires one |
| Bambu LAN MQTT | `bambu_mqtt` | `bambu_lan_mqtt` | model-specific profile when camera, files, or AMS behavior requires one |
| OctoPrint | `octoprint` | `generic_octoprint` | `null` |

## Testing Expectations

- Engine tests cover connection-independent parsing, safety defaults, and common
  response contracts.
- Maker adapter tests cover vendor payload normalization and capability metadata.
- Model profile tests cover exact payload examples and fallback behavior.
- UI tests or API tests should assert only the normalized contract unless the UI
  intentionally exposes layer provenance.

## Safety Boundary

Layering is not permission to add controls. New write actions, file mutation,
camera streams, AMS actions, raw commands, or extension-agent calls need their
own change ticket, server-side authorization check, audit trail, and rollback
plan. A model profile must never be able to turn on a capability that the engine
or maker adapter explicitly disables.
