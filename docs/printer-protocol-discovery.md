# Printer Protocol Discovery Notes

Created: 2026-06-14

## Goal

3dPrintPilot should discover LAN printer capabilities without overstating what
was found. An open port only proves that something is listening. A device should
only be classified as a printer endpoint when the protocol handshake or response
body identifies a known printer stack or vendor API.

## Common Ports

| Port | Common service | Discovery rule |
| --- | --- | --- |
| 1883 | MQTT, unencrypted | Send MQTT CONNECT. Classify only if MQTT CONNACK is received. |
| 8883 | MQTT over TLS | Establish TLS, send MQTT CONNECT. Classify only if MQTT CONNACK is received. |
| 80 | HTTP web interface | Probe known read-only printer endpoints and marker HTML/API responses. Generic HTML is not enough. |
| 443 | HTTPS web interface | Same as HTTP, with TLS. Generic HTML is not enough. |
| 3000-5000 | Vendor-specific APIs | Classify only on known vendor/API markers. |
| 6000+ | Camera/video streams | Treat as supporting capability only when the same host has a confirmed printer endpoint, unless a vendor signature is known. |
| 7125 | Klipper/Moonraker API | Probe `/server/info` and `/printer/info`; classify only with Moonraker/Klippy/Klipper markers. |
| 8080 | Web interface/API | Probe known printer markers only. Generic web apps should not become printer candidates. |

## Detection Principles

- Do not classify a device as a printer from a TCP open-port check alone.
- Do not classify a device as a printer from generic HTTP status codes alone.
- Prefer read-only probes during discovery.
- Keep scan results grouped by host/IP so one physical printer can expose
  multiple endpoints such as Moonraker, MQTT, and camera streams.
- Separate confirmed printer endpoints from supporting capabilities.
- Let users filter noisy services, but make the default detector conservative.
- Store scan timing, probe count, discovered endpoint count, and classification
  evidence for later metrics and debugging.

## HTTP Classification

HTTP and HTTPS probes should look for known printer indicators, including:

- Moonraker/Klipper/Klippy API responses.
- Fluidd or Mainsail web UI markers.
- OctoPrint API/version markers.
- PrusaLink markers.
- Duet Web Control markers.
- Snapmaker markers.
- Creality/K2/K2 Plus markers.
- Bambu markers when clearly present.

Generic web pages should be ignored unless they contain a known printer marker.
For example, `192.168.1.6:8080` returned a File Browser / PiNAS web UI:

```text
<title>PiNAS</title>
apple-mobile-web-app-title = File Browser
window.FileBrowser = {"Name":"PiNAS","Version":"2.63.14"}
```

That should not be treated as a printer candidate.

## MQTT Classification

MQTT is useful only after the protocol is confirmed.

Scanner levels:

| Level | Meaning | Behavior |
| --- | --- | --- |
| `open_port` | TCP port is open | Do not show as printer by itself. |
| `mqtt_confirmed` | MQTT CONNACK received | Show MQTT capability. |
| `auth_required` | Broker responds but rejects anonymous access | Show MQTT requires credentials when distinguishable. |
| `readable` | Subscribe succeeds | Enable status monitoring. |
| `writable` | Publish/control topics are available | Gate behind explicit advanced control settings. |

Discovery must never publish control commands. It may send a minimal MQTT
CONNECT packet and, in a later diagnostic mode, perform a short read-only
subscribe test.

## MQTT Capabilities

When a printer exposes MQTT, it can support monitoring such as:

- printer status
- nozzle temperature
- bed temperature
- print progress
- current job/file
- remaining time
- error conditions
- filament runout
- paused/resumed/completed events

MQTT data is useful for:

- dashboards
- Home Assistant
- Node-RED
- Grafana
- app notifications
- historical metrics
- reverse-engineering read-only status payloads

Potential historical metrics:

- print duration
- filament usage
- failure rates
- temperature trends
- error frequency
- printer uptime/offline periods

## MQTT Control Safety

Some printers expose command topics such as pause, resume, stop, temperature,
fan, AMS/material, calibration, or raw G-code commands. These should be treated
as dangerous by default.

Rules:

- Do not publish commands during discovery.
- Do not expose raw G-code publishing by default.
- Put any write/control features behind an explicit advanced/local-control gate.
- Require per-printer credentials before control actions.
- Store credentials encrypted.
- Log command attempts as audit events.
- Prefer vendor-supported APIs where available.

Security checks:

- Does anonymous MQTT access work?
- Is subscription read-only?
- Can anonymous clients publish command topics?
- Is the broker bound to LAN only?
- Is TLS used?
- Are credentials required?

## Bambu Lab Notes

Official Bambu network ports include:

- `8883/TCP` for LAN MQTT
- `990/TCP` plus passive `50000-50100/TCP` for FTPS
- `322/TCP` and `6000/TCP` for video/camera services
- discovery ports around `1990/2021`

Known local MQTT pattern from public reverse-engineered integrations:

```text
host: printer IP
port: 8883
username: bblp
password: printer LAN/developer access code
report topic: device/{serial}/report
request topic: device/{serial}/request
payloads: JSON
```

Implementation guidance:

- Treat Bambu MQTT as read-only monitoring first.
- Require LAN access code before subscribing to private topics.
- Do not assume control commands work on current firmware without Developer Mode
  or other official authorization paths.
- Validate TLS properly where possible; printer certificates may use serial-based
  names rather than IP addresses.

## Klipper And Moonraker Notes

Moonraker is a local HTTP and WebSocket API commonly used by Klipper printers.
Default port is often `7125`.

Safe read-only discovery/status endpoints:

- `GET /access/info`
- `GET /server/info`
- `GET /printer/info`
- `GET /printer/objects/list`
- `GET /printer/objects/query?...`
- `GET /server/temperature_store?include_monitors=false`
- `GET /machine/proc_stats`
- `GET /server/webcams/list`

Useful status objects:

- `webhooks`
- `print_stats`
- `virtual_sdcard`
- `toolhead`
- `gcode_move`
- `heaters`
- `extruder`
- `heater_bed`
- temperature sensors
- fans
- `configfile`
- `system_stats`

Avoid during discovery:

- emergency stop
- restart/firmware restart
- raw G-code script execution
- job start/pause/resume/cancel
- file upload/delete/move/copy
- machine shutdown/reboot/service controls
- API key rotation
- sudo/password operations

## Snapmaker U1 Notes

Snapmaker U1 exposes a Moonraker-compatible surface and Snapmaker-specific
components. Useful observed markers include:

- hostname `lava`
- `snapmakercloud` Moonraker component
- `client_manager`
- `mqtt`
- multiple extruders such as `extruder`, `extruder1`, `extruder2`, `extruder3`

Primary safe integration path:

- Probe `http://<ip>:7125/server/info`.
- Use Moonraker read-only endpoints and WebSocket subscriptions.
- Treat Snapmaker MQTT as a paired-client/control plane, not the first status
  integration path.
- Expect touchscreen approval or credential/certificate pairing for deeper LAN
  integration.

## Creality K2 / K2 Plus Notes

Creality K2/K2 Plus devices are Klipper/Moonraker based. Useful ports:

- `4408` for Fluidd/Moonraker on some K2/K2 Plus configurations
- `7125` as Moonraker fallback
- `8000` for camera on some firmware versions

Use Moonraker detection rather than hardcoded model assumptions:

- `GET /server/info`
- `GET /printer/info`
- `GET /printer/objects/list`
- `GET /printer/objects/query`

Camera behavior is firmware-sensitive. Treat camera ports as optional
supporting capabilities.

## Current LAN Observations

Observed during development:

- `192.168.1.44`: Snapmaker U1 / Moonraker on `7125`.
- `192.168.1.185`: Klipper/Moonraker-like endpoint on `7125` and sometimes `4408`.
- `192.168.1.76`: confirmed Bambu MQTT over TLS on `8883`; camera/control TCP on `6000`.
- `192.168.1.49`: confirmed Bambu MQTT over TLS on `8883`; camera/control TCP on `6000`.
- `192.168.1.218`: `8883` may be open at times, but no MQTT ACK was confirmed; ignore as printer MQTT until proven.
- `192.168.1.228`: HP OfficeJet / IPP paper printer, not a 3D printer.
- `192.168.1.6`: Raspberry Pi running File Browser / PiNAS on `8080`, not a 3D printer.

## Future Work

- Add `1883` MQTT probing with the same ACK-required rule as `8883`.
- Split detection into two phases:
  1. Confirm printer identity endpoints.
  2. Attach supporting ports such as camera/video only to confirmed printer hosts.
- Add an MQTT diagnostics screen:
  - credential-aware connection setup
  - subscribe-only topic capture
  - timestamped payload storage
  - redaction of secrets and serials where needed
  - no publishing unless advanced control mode is explicitly enabled
- Add per-printer encrypted credential storage for LAN access codes, API keys,
  client certificates, and tokens.
- Add user-managed filters for known non-printer services while keeping detector
  defaults conservative.
