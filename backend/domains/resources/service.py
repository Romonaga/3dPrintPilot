from __future__ import annotations

import os
import subprocess
from typing import Any


def build_resource_status() -> dict[str, Any]:
    return {
        "cpu": {
            "cores": os.cpu_count() or 1,
            "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        },
        "memory": _read_memory_status(),
        "gpu": _read_gpu_status(),
    }


def _read_memory_status() -> dict[str, Any]:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            rows = handle.readlines()
    except OSError:
        return {"total_bytes": None, "available_bytes": None, "used_percent": None}

    values: dict[str, int] = {}
    for row in rows:
        name, _, raw_value = row.partition(":")
        parts = raw_value.strip().split()
        if not parts:
            continue
        try:
            values[name] = int(parts[0]) * 1024
        except ValueError:
            continue
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    used_percent = round(((total - available) / total) * 100, 2) if total and available is not None else None
    return {"total_bytes": total, "available_bytes": available, "used_percent": used_percent}


def _read_gpu_status() -> dict[str, Any]:
    query = "name,utilization.gpu,memory.used,memory.total,temperature.gpu"
    try:
        completed = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "error": "nvidia-smi unavailable"}
    if completed.returncode != 0 or not completed.stdout.strip():
        return {"available": False, "error": completed.stderr.strip()[:200] or "nvidia-smi unavailable"}
    parts = [part.strip() for part in completed.stdout.strip().splitlines()[0].split(",")]
    if len(parts) < 5:
        return {"available": False, "error": "unexpected nvidia-smi output"}
    try:
        memory_used = float(parts[2])
        memory_total = float(parts[3])
        return {
            "available": True,
            "name": parts[0],
            "utilization_percent": float(parts[1]),
            "memory_used_mib": memory_used,
            "memory_total_mib": memory_total,
            "memory_used_percent": round((memory_used / memory_total) * 100, 2) if memory_total else None,
            "temperature_c": float(parts[4]),
        }
    except ValueError:
        return {"available": False, "error": "could not parse nvidia-smi output"}

