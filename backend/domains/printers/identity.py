from __future__ import annotations

import re
from collections.abc import Mapping


MDNS_EVIDENCE_PATTERN = re.compile(r"mDNS service (?P<service>\S+) advertised (?P<name>.+)")


def printer_identity_key(
    name: str,
    host: str,
    port: int,
    protocol: str,
    service_type: str,
    evidence: tuple[str, ...] | list[str] = (),
) -> str:
    mdns_key = _mdns_identity_from_evidence(evidence)
    if mdns_key is not None:
        return mdns_key

    normalized_service_type = _normalize_identity_part(service_type)
    if service_type.startswith("_") or service_type.lower().startswith("mdns:"):
        return f"mdns:{normalized_service_type}:{_normalize_identity_part(name)}"

    return (
        f"endpoint:{normalized_service_type}:"
        f"{_normalize_identity_part(protocol)}:{_normalize_identity_part(host)}:{port}"
    )


def is_stable_printer_identity(identity_key: str | None) -> bool:
    return bool(identity_key) and not identity_key.startswith("endpoint:")


def moonraker_identity_key(payload: Mapping | None, service_type: str = "moonraker") -> str | None:
    if not payload:
        return None
    data = payload.get("result", payload)
    if not isinstance(data, Mapping):
        return None

    for field_name in ("instance_uuid", "instance_id", "machine_id", "device_id", "serial", "uuid"):
        value = _stable_identity_value(data.get(field_name))
        if value is not None:
            return f"moonraker:{_normalize_identity_part(service_type)}:{field_name}:{_normalize_identity_part(value)}"

    hostname = _stable_identity_value(data.get("hostname"))
    if hostname is not None:
        return f"moonraker:{_normalize_identity_part(service_type)}:hostname:{_normalize_identity_part(hostname)}"

    return None


def _mdns_identity_from_evidence(evidence: tuple[str, ...] | list[str]) -> str | None:
    for item in evidence:
        match = MDNS_EVIDENCE_PATTERN.search(item)
        if match is None:
            continue
        return (
            f"mdns:{_normalize_identity_part(match.group('service'))}:"
            f"{_normalize_identity_part(match.group('name'))}"
        )
    return None


def _normalize_identity_part(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_.:-]+", "-", value.strip().lower())
    return normalized.strip("-") or "unknown"


def _stable_identity_value(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"localhost", "unknown", "none", "null"}:
        return None
    return text
