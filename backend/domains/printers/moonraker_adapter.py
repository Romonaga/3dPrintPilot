from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from backend.domains.printers.adapter_capabilities import capabilities_for_service_type, infer_adapter_type
from backend.domains.printers.adapter_types import (
    ExtensionMethodNotAllowedError,
    MoonrakerActionResult,
    MoonrakerCapabilityDiagnostics,
    MoonrakerExtensionResult,
    MoonrakerFile,
    MoonrakerJobStatus,
    MoonrakerTemperature,
    MoonrakerToolheadTelemetry,
    SnapmakerU1FilamentSlot,
    SpoolmanFilamentMetadata,
    UnsupportedPrinterControlError,
)
from backend.domains.printers.adapter_utils import (
    base_url as build_base_url,
    float_or_none,
    int_or_none,
    string_or_none,
    validate_sliced_filename,
)
from backend.domains.printers.models import Printer

DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS = 5.0


def fetch_moonraker_capability_diagnostics(
    printer: Printer,
    timeout_seconds: float = DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS,
) -> MoonrakerCapabilityDiagnostics:
    _require_moonraker_adapter(printer)
    endpoint_base_url = build_base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        extensions_payload, extensions_error = _optional_moonraker_json(client, f"{endpoint_base_url}/server/extensions/list")
        spoolman_payload, spoolman_error = _optional_moonraker_json(client, f"{endpoint_base_url}/server/spoolman/status")
    errors = {}
    if extensions_error:
        errors["extensions"] = extensions_error
    if spoolman_error:
        errors["spoolman"] = spoolman_error
    return parse_moonraker_capability_diagnostics(
        extensions_payload=extensions_payload,
        spoolman_payload=spoolman_payload,
        probe_errors=errors,
    )


def request_moonraker_extension(
    printer: Printer,
    agent: str,
    method: str,
    arguments: dict[str, Any] | None = None,
    timeout_seconds: float = 5.0,
) -> MoonrakerExtensionResult:
    _require_moonraker_adapter(printer)
    if not _moonraker_extension_method_allowed(printer.capabilities or {}, agent, method):
        raise ExtensionMethodNotAllowedError("Moonraker extension method is not allowlisted for this printer")
    endpoint_base_url = build_base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.post(
            f"{endpoint_base_url}/server/extensions/request",
            json={"agent": agent, "method": method, "arguments": arguments or {}},
        ).json()
    return MoonrakerExtensionResult(agent=agent, method=method, accepted=True, raw_response=payload)


def parse_moonraker_capability_diagnostics(
    extensions_payload: dict[str, Any] | None = None,
    spoolman_payload: dict[str, Any] | None = None,
    probe_errors: dict[str, str] | None = None,
) -> MoonrakerCapabilityDiagnostics:
    errors = dict(probe_errors or {})
    extension_agents = _moonraker_extension_agents(extensions_payload)
    spoolman_status = _moonraker_spoolman_status(spoolman_payload)
    return MoonrakerCapabilityDiagnostics(
        adapter_type="moonraker",
        extension_agents_available=bool(extension_agents),
        extension_agents=extension_agents,
        spoolman_available=spoolman_status is not None and "spoolman" not in errors,
        spoolman_status=spoolman_status,
        probe_errors=errors,
        observed_at=datetime.now(UTC),
    )


class MoonrakerTelemetryEngine:
    def __init__(self, client: httpx.Client, base_url: str) -> None:
        self.client = client
        self.base_url = base_url

    def fetch_job_status_payload(self) -> dict[str, Any]:
        object_names = self._available_object_names()
        extruder_names = _moonraker_extruder_names_from_object_names(object_names) or ("extruder",)
        snapmaker_objects = tuple(
            name
            for name in (
                "filament_detect",
                "filament_feed left",
                "filament_feed right",
                "gcode_macro _FILAMENT_FEED_VARIABLE",
            )
            if name in object_names
        )
        query_objects = [
            "print_stats",
            "virtual_sdcard",
            "display_status",
            "heater_bed",
            "configfile",
            *extruder_names,
            *snapmaker_objects,
        ]
        query = "&".join(quote(name, safe="") for name in dict.fromkeys(query_objects))
        payload = self.client.get(f"{self.base_url}/printer/objects/query?{query}").json()
        self._attach_spoolman_payload(payload)
        return payload

    def _available_object_names(self) -> tuple[str, ...]:
        try:
            payload = self.client.get(f"{self.base_url}/printer/objects/list").json()
        except httpx.HTTPError:
            return ()
        return _moonraker_object_names_from_object_list(payload)

    def _attach_spoolman_payload(self, payload: dict[str, Any]) -> None:
        spoolman_payload, spoolman_error = _optional_moonraker_json(self.client, f"{self.base_url}/server/spoolman/status")
        if spoolman_error or not isinstance(spoolman_payload, dict):
            return
        status = _moonraker_query_status(payload)
        spoolman_status = _moonraker_spoolman_status(spoolman_payload)
        if not isinstance(status, dict) or spoolman_status is None:
            return
        status["spoolman"] = spoolman_status
        spool_id = int_or_none(spoolman_status.get("spool_id"))
        if spool_id is None:
            return
        active_spool_payload, active_spool_error = _optional_moonraker_post_json(
            self.client,
            f"{self.base_url}/server/spoolman/proxy",
            {
                "use_v2_response": True,
                "request_method": "GET",
                "path": f"/v1/spool/{spool_id}",
            },
        )
        if active_spool_error is None and isinstance(active_spool_payload, dict):
            status["spoolman_active_spool"] = active_spool_payload


def parse_moonraker_job_status(payload: dict[str, Any], capabilities: dict[str, Any] | None = None) -> MoonrakerJobStatus:
    result = payload.get("result", payload)
    status = result.get("status", result) if isinstance(result, dict) else {}
    print_stats = status.get("print_stats", {}) if isinstance(status, dict) else {}
    virtual_sdcard = status.get("virtual_sdcard", {}) if isinstance(status, dict) else {}
    display_status = status.get("display_status", {}) if isinstance(status, dict) else {}
    state = str(print_stats.get("state") or "unknown").lower()
    progress = float_or_none(virtual_sdcard.get("progress") or display_status.get("progress"))
    return MoonrakerJobStatus(
        state=state,
        filename=string_or_none(print_stats.get("filename") or virtual_sdcard.get("file_path")),
        progress=progress,
        message=string_or_none(print_stats.get("message")),
        bed_temperature=_moonraker_temperature(status.get("heater_bed") if isinstance(status, dict) else None),
        toolheads=_moonraker_toolhead_telemetry(status, capabilities or {}),
        raw_status=payload,
        observed_at=datetime.now(UTC),
    )


def list_moonraker_files(printer: Printer, timeout_seconds: float = 5.0) -> list[MoonrakerFile]:
    require_moonraker_control(printer)
    endpoint_base_url = build_base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.get(f"{endpoint_base_url}/server/files/list", params={"root": "gcodes"}).json()
    files = payload.get("result", payload) if isinstance(payload, dict) else payload
    if not isinstance(files, list):
        return []
    return [
        MoonrakerFile(
            path=str(item.get("path") or item.get("filename") or ""),
            size=int_or_none(item.get("size")),
            modified=float_or_none(item.get("modified")),
            permissions=string_or_none(item.get("permissions")),
        )
        for item in files
        if isinstance(item, dict) and (item.get("path") or item.get("filename"))
    ]


def upload_moonraker_file(
    printer: Printer,
    filename: str,
    content: bytes,
    content_type: str | None = None,
    timeout_seconds: float = 30.0,
) -> MoonrakerActionResult:
    require_moonraker_control(printer)
    safe_filename = validate_sliced_filename(filename)
    endpoint_base_url = build_base_url(printer)
    files = {
        "file": (
            safe_filename,
            content,
            content_type or "application/octet-stream",
        )
    }
    data = {"root": "gcodes", "print": "false"}
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.post(f"{endpoint_base_url}/server/files/upload", files=files, data=data).json()
    return MoonrakerActionResult(action="upload", accepted=True, raw_response=payload)


def start_moonraker_print(printer: Printer, filename: str, timeout_seconds: float = 5.0) -> MoonrakerActionResult:
    require_moonraker_control(printer)
    safe_filename = validate_sliced_filename(filename)
    endpoint_base_url = build_base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.post(f"{endpoint_base_url}/printer/print/start?filename={quote(safe_filename)}").json()
    return MoonrakerActionResult(action="start", accepted=True, raw_response=payload)


def pause_moonraker_print(printer: Printer, timeout_seconds: float = 5.0) -> MoonrakerActionResult:
    return _moonraker_print_action(printer, "pause", timeout_seconds)


def resume_moonraker_print(printer: Printer, timeout_seconds: float = 5.0) -> MoonrakerActionResult:
    return _moonraker_print_action(printer, "resume", timeout_seconds)


def cancel_moonraker_print(printer: Printer, timeout_seconds: float = 5.0) -> MoonrakerActionResult:
    return _moonraker_print_action(printer, "cancel", timeout_seconds)


def require_moonraker_control(printer: Printer) -> None:
    _require_moonraker_adapter(printer)
    stored_capabilities = printer.capabilities or {}
    inferred_capabilities = capabilities_for_service_type(printer.printer_type)
    control_enabled = bool(inferred_capabilities.get("control_enabled") or stored_capabilities.get("control_enabled"))
    if not control_enabled:
        raise UnsupportedPrinterControlError("Moonraker file and job controls are not available for this printer")


def _require_moonraker_adapter(printer: Printer) -> None:
    adapter_type = printer.adapter_type or infer_adapter_type(None, printer.printer_type)
    if adapter_type != "moonraker":
        raise UnsupportedPrinterControlError("Moonraker file and job controls are not available for this printer")


def _moonraker_print_action(printer: Printer, action: str, timeout_seconds: float) -> MoonrakerActionResult:
    require_moonraker_control(printer)
    endpoint_base_url = build_base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.post(f"{endpoint_base_url}/printer/print/{action}").json()
    return MoonrakerActionResult(action=action, accepted=True, raw_response=payload)


def _moonraker_extruder_names_from_object_list(payload: dict[str, Any]) -> tuple[str, ...]:
    return _moonraker_extruder_names_from_object_names(_moonraker_object_names_from_object_list(payload))


def _moonraker_object_names_from_object_list(payload: dict[str, Any]) -> tuple[str, ...]:
    result = payload.get("result", payload)
    objects = result.get("objects", result) if isinstance(result, dict) else result
    if not isinstance(objects, list):
        return ()
    return tuple(name for name in objects if isinstance(name, str))


def _moonraker_extruder_names_from_object_names(objects: tuple[str, ...]) -> tuple[str, ...]:
    names = [name for name in objects if _is_moonraker_extruder_name(name)]
    return tuple(sorted(set(names), key=_moonraker_extruder_sort_key))


def _optional_moonraker_json(client: httpx.Client, url: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = client.get(url)
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None, "unreachable"
    if response.status_code == 404:
        return payload if isinstance(payload, dict) else None, "not_configured"
    if response.status_code >= 400:
        return payload if isinstance(payload, dict) else None, f"http_{response.status_code}"
    return payload if isinstance(payload, dict) else None, None


def _optional_moonraker_post_json(client: httpx.Client, url: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = client.post(url, json=payload)
        response_payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None, "unreachable"
    if response.status_code == 404:
        return response_payload if isinstance(response_payload, dict) else None, "not_configured"
    if response.status_code >= 400:
        return response_payload if isinstance(response_payload, dict) else None, f"http_{response.status_code}"
    return response_payload if isinstance(response_payload, dict) else None, None


def _moonraker_query_status(payload: dict[str, Any]) -> dict[str, Any] | None:
    result = payload.get("result", payload)
    status = result.get("status", result) if isinstance(result, dict) else None
    return status if isinstance(status, dict) else None


def _moonraker_extension_agents(payload: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, dict):
        return ()
    result = payload.get("result", payload)
    agents = result.get("agents") if isinstance(result, dict) else None
    if not isinstance(agents, list):
        return ()
    return tuple(
        {
            "name": string_or_none(agent.get("name")),
            "version": string_or_none(agent.get("version")),
            "type": string_or_none(agent.get("type")),
            "url": string_or_none(agent.get("url")),
        }
        for agent in agents
        if isinstance(agent, dict) and string_or_none(agent.get("name"))
    )


def _moonraker_spoolman_status(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    result = payload.get("result", payload)
    if not isinstance(result, dict) or "error" in result:
        return None
    return result


def _spoolman_filament_metadata(status: dict[str, Any]) -> SpoolmanFilamentMetadata | None:
    active_spool = status.get("spoolman_active_spool") if isinstance(status, dict) else None
    if not isinstance(active_spool, dict):
        return None
    response = active_spool.get("response", active_spool)
    if not isinstance(response, dict):
        return None
    filament = response.get("filament")
    if not isinstance(filament, dict):
        return None
    vendor = filament.get("vendor")
    return SpoolmanFilamentMetadata(
        color=_spoolman_color(filament),
        material=string_or_none(filament.get("material")),
        vendor=string_or_none(vendor.get("name")) if isinstance(vendor, dict) else string_or_none(vendor),
    )


def _spoolman_color(filament: dict[str, Any]) -> str | None:
    color = string_or_none(filament.get("color_hex"))
    if not color:
        return None
    normalized = color.lstrip("#").strip()
    if len(normalized) != 6:
        return None
    return f"#{normalized.lower()}"


def _moonraker_extension_method_allowed(capabilities: dict[str, Any], agent: str, method: str) -> bool:
    allowed_methods = capabilities.get("moonraker_extension_methods")
    if not isinstance(allowed_methods, list):
        return False
    for item in allowed_methods:
        if not isinstance(item, dict):
            continue
        if string_or_none(item.get("agent")) == agent and string_or_none(item.get("method")) == method:
            return True
    return False


def _moonraker_toolhead_telemetry(status: dict[str, Any], capabilities: dict[str, Any]) -> tuple[MoonrakerToolheadTelemetry, ...]:
    if not isinstance(status, dict):
        return ()
    configfile = status.get("configfile", {})
    settings = {}
    if isinstance(configfile, dict):
        settings = configfile.get("settings") or configfile.get("config") or {}
    if not isinstance(settings, dict):
        settings = {}
    capability_toolheads = capabilities.get("toolheads")
    capability_colors = _capability_tool_colors(capability_toolheads)
    snapmaker_slots = _snapmaker_u1_filament_slots(status)
    spoolman_metadata = _spoolman_filament_metadata(status)
    names = sorted(
        {key for key in status if _is_moonraker_extruder_name(key)} | {key for key in settings if _is_moonraker_extruder_name(key)},
        key=_moonraker_extruder_sort_key,
    )
    toolheads = []
    for name in names:
        index = _moonraker_extruder_index(name)
        payload = status.get(name) if isinstance(status.get(name), dict) else {}
        config = settings.get(name) if isinstance(settings.get(name), dict) else {}
        snapmaker_slot = snapmaker_slots.get(index)
        spoolman_slot = spoolman_metadata if len(names) == 1 else None
        color, color_source = _moonraker_toolhead_color(payload, config, snapmaker_slot, spoolman_slot, capability_colors.get(index))
        material = snapmaker_slot.material if snapmaker_slot else spoolman_slot.material if spoolman_slot else None
        material_source = "vendor_object" if snapmaker_slot and snapmaker_slot.material else "spoolman" if spoolman_slot and spoolman_slot.material else None
        vendor = snapmaker_slot.vendor if snapmaker_slot else spoolman_slot.vendor if spoolman_slot else None
        toolheads.append(
            MoonrakerToolheadTelemetry(
                name=name,
                label=f"T{index}",
                index=index,
                current_temperature=_moonraker_temperature(payload),
                color=color,
                color_source=color_source,
                material=material,
                material_source=material_source,
                vendor=vendor,
                subtype=snapmaker_slot.subtype if snapmaker_slot else None,
            )
        )
    return tuple(toolheads)


def _moonraker_temperature(payload: Any) -> MoonrakerTemperature | None:
    if not isinstance(payload, dict):
        return None
    current = float_or_none(payload.get("temperature"))
    target = float_or_none(payload.get("target"))
    power = float_or_none(payload.get("power"))
    if current is None and target is None and power is None:
        return None
    return MoonrakerTemperature(current_c=current, target_c=target, power=power)


def _moonraker_color(payload: dict[str, Any], config: dict[str, Any], fallback: str | None = None) -> str | None:
    color, _source = _moonraker_color_with_source(payload, config, fallback)
    return color


def _moonraker_toolhead_color(
    payload: dict[str, Any],
    config: dict[str, Any],
    vendor_slot: SnapmakerU1FilamentSlot | None,
    spoolman_metadata: SpoolmanFilamentMetadata | None,
    capability_fallback: str | None,
) -> tuple[str | None, str | None]:
    color, source = _moonraker_color_with_source(payload, config)
    if color:
        return color, source
    if vendor_slot and vendor_slot.color:
        return vendor_slot.color, "vendor_object"
    if spoolman_metadata and spoolman_metadata.color:
        return spoolman_metadata.color, "spoolman"
    if capability_fallback:
        return capability_fallback, "saved_capabilities"
    return None, None


def _moonraker_color_with_source(
    payload: dict[str, Any],
    config: dict[str, Any],
    fallback: str | None = None,
) -> tuple[str | None, str | None]:
    for source in (payload, config):
        color = _color_from_mapping(source)
        if color:
            return color, "moonraker_object" if source is payload else "moonraker_config"
    if fallback:
        return fallback, "saved_capabilities"
    return None, None


def _color_from_mapping(source: dict[str, Any]) -> str | None:
    for key in ("filament_color", "material_color", "spool_color", "color", "colour"):
        color = string_or_none(source.get(key))
        if color:
            return color
    for nested_key in ("filament", "material", "spool"):
        nested = source.get(nested_key)
        if isinstance(nested, dict):
            color = _color_from_mapping(nested)
            if color:
                return color
    return None


def _capability_tool_colors(toolheads: Any) -> dict[int, str]:
    if not isinstance(toolheads, list):
        return {}
    colors: dict[int, str] = {}
    for item in toolheads:
        if not isinstance(item, dict):
            continue
        index = int_or_none(item.get("index"))
        color = _color_from_mapping(item)
        if index is not None and color:
            colors[index] = color
    return colors


def _snapmaker_u1_filament_slots(status: dict[str, Any]) -> dict[int, SnapmakerU1FilamentSlot]:
    filament_detect = status.get("filament_detect") if isinstance(status, dict) else None
    info_items = filament_detect.get("info") if isinstance(filament_detect, dict) else None
    if not isinstance(info_items, list):
        return {}
    slots: dict[int, SnapmakerU1FilamentSlot] = {}
    for index, item in enumerate(info_items):
        if not isinstance(item, dict) or _snapmaker_filament_is_empty(item):
            continue
        slots[index] = SnapmakerU1FilamentSlot(
            index=index,
            color=_snapmaker_color(item),
            material=string_or_none(item.get("MAIN_TYPE")),
            vendor=string_or_none(item.get("VENDOR")) or string_or_none(item.get("MANUFACTURER")),
            subtype=string_or_none(item.get("SUB_TYPE")),
        )
    return slots


def _snapmaker_filament_is_empty(item: dict[str, Any]) -> bool:
    material = (string_or_none(item.get("MAIN_TYPE")) or "").upper()
    vendor = (string_or_none(item.get("VENDOR")) or "").upper()
    manufacturer = (string_or_none(item.get("MANUFACTURER")) or "").upper()
    return material in {"", "NONE"} and vendor in {"", "NONE"} and manufacturer in {"", "NONE"}


def _snapmaker_color(item: dict[str, Any]) -> str | None:
    for key in ("RGB_1", "ARGB_COLOR"):
        value = int_or_none(item.get(key))
        if value is not None:
            return f"#{value & 0xFFFFFF:06x}"
    return None


def _is_moonraker_extruder_name(name: str) -> bool:
    return name == "extruder" or (name.startswith("extruder") and name[8:].isdigit())


def _moonraker_extruder_index(name: str) -> int:
    if name == "extruder":
        return 0
    return int_or_none(name[8:]) or 0


def _moonraker_extruder_sort_key(name: str) -> tuple[int, str]:
    return (_moonraker_extruder_index(name), name)
