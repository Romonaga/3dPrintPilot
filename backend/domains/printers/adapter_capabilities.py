from __future__ import annotations

from typing import Any


def infer_adapter_type(service_type: str | None, printer_type: str | None = None) -> str | None:
    haystack = f"{service_type or ''} {printer_type or ''}".lower()
    if "octoprint" in haystack:
        return "octoprint"
    if "bambu_mqtt" in haystack or ("bambu" in haystack and "mqtt" in haystack):
        return "bambu_mqtt"
    if any(marker in haystack for marker in ("moonraker", "klipper", "mainsail", "fluidd", "snapmaker", "creality")):
        return "moonraker"
    return None


def capabilities_for_service_type(service_type: str | None) -> dict[str, Any]:
    adapter_type = infer_adapter_type(service_type)
    if adapter_type == "octoprint":
        return {
            "adapter": "octoprint",
            "integration_layers": _integration_layers_for_service_type(service_type, adapter_type),
            "read_only_status": True,
            "safe_endpoints": ["/api/version", "/api/printer"],
            "control_enabled": False,
        }
    if adapter_type == "moonraker":
        return {
            "adapter": "moonraker",
            "integration_layers": _integration_layers_for_service_type(service_type, adapter_type),
            "read_only_status": True,
            "safe_endpoints": [
                "/server/info",
                "/printer/info",
                "/printer/objects/list",
                "/printer/objects/query",
                "/server/files/list",
                "/server/files/upload",
                "/printer/print/start",
                "/printer/print/pause",
                "/printer/print/resume",
                "/printer/print/cancel",
            ],
            "control_enabled": True,
            "file_management": True,
            "job_control": True,
            "allowed_file_roots": ["gcodes"],
            "allowed_file_extensions": [".gcode", ".gcode.gz"],
            "allowed_job_actions": ["start", "pause", "resume", "cancel"],
            "raw_gcode_console": False,
            "telemetry_source_priority": [
                "moonraker_object",
                "vendor_object",
                "spoolman",
                "extension_agent",
                "saved_capabilities",
            ],
        }
    if adapter_type == "bambu_mqtt":
        return {
            "adapter": "bambu_mqtt",
            "integration_layers": _integration_layers_for_service_type(service_type, adapter_type),
            "read_only_status": True,
            "control_enabled": False,
            "protocol": "mqtts",
            "default_port": 8883,
            "credential_required": True,
            "required_credentials": ["lan_access_code", "device_id"],
            "safe_topics": ["device/{device_id}/report", "device/{device_id}/request"],
            "safe_methods": ["pushing.pushall"],
            "pushall_min_interval_seconds": 300,
            "raw_gcode_console": False,
            "local_mode_tradeoff": "LAN or Developer mode may limit Bambu Handy or cloud workflows on some firmware.",
            "telemetry_source_priority": [
                "bambu_mqtt_report",
                "saved_capabilities",
            ],
        }
    return {
        "adapter": "unknown",
        "integration_layers": _integration_layers_for_service_type(service_type, adapter_type),
        "read_only_status": False,
        "control_enabled": False,
    }


def _integration_layers_for_service_type(service_type: str | None, adapter_type: str | None) -> dict[str, str | None]:
    haystack = (service_type or "").lower()
    if adapter_type == "moonraker":
        maker_adapter = "generic_moonraker"
        model_profile = None
        if "snapmaker" in haystack:
            maker_adapter = "snapmaker_moonraker"
            model_profile = "snapmaker_u1" if "u1" in haystack or "snapmaker_moonraker" in haystack else None
        elif "creality" in haystack:
            maker_adapter = "creality_moonraker"
        return {"engine": "moonraker", "maker_adapter": maker_adapter, "model_profile": model_profile}
    if adapter_type == "bambu_mqtt":
        return {"engine": "bambu_mqtt", "maker_adapter": "bambu_lan_mqtt", "model_profile": None}
    if adapter_type == "octoprint":
        return {"engine": "octoprint", "maker_adapter": "generic_octoprint", "model_profile": None}
    return {"engine": "unknown", "maker_adapter": None, "model_profile": None}
