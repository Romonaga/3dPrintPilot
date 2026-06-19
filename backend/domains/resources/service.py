from __future__ import annotations

import os
import subprocess
import urllib.error
import urllib.request
from typing import Any

from backend.core.config import get_settings
from backend.domains.resources.store import SUPPORTED_JOB_TYPES
from backend.domains.resources.worker import LocalLlmAdmissionPolicy


def build_resource_status() -> dict[str, Any]:
    policy = LocalLlmAdmissionPolicy()
    return {
        "cpu": {
            "cores": os.cpu_count() or 1,
            "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        },
        "memory": _read_memory_status(),
        "gpu": _read_gpu_status(),
        "queues": {
            "local_llm": {
                "pending_count": 0,
                "active_count": 0,
                "max_concurrent": policy.max_concurrent_requests,
                "supported_job_types": list(SUPPORTED_JOB_TYPES),
            }
        },
        "ollama": _read_ollama_status(),
        "local_llm": {
            "max_concurrent_requests": policy.max_concurrent_requests,
            "request_timeout_seconds": policy.request_timeout_seconds,
            "max_context_tokens": policy.max_context_tokens,
            "max_output_tokens": policy.max_output_tokens,
            "min_free_vram_mib": policy.min_free_vram_mib,
            "max_gpu_memory_used_percent": policy.max_gpu_memory_used_percent,
            "max_gpu_temperature_c": policy.max_gpu_temperature_c,
            "oom_cooldown_seconds": policy.oom_cooldown_seconds,
        },
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


def _read_ollama_status() -> dict[str, Any]:
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    tags_url = f"{base_url}/tags"
    try:
        with urllib.request.urlopen(tags_url, timeout=1.5) as response:
            available = 200 <= response.status < 300
    except (OSError, urllib.error.URLError) as exc:
        return {
            "available": False,
            "base_url": settings.ollama_base_url,
            "model": settings.local_llm_default_model,
            "error": str(exc)[:200],
        }
    return {
        "available": available,
        "base_url": settings.ollama_base_url,
        "model": settings.local_llm_default_model,
        "error": None if available else "Ollama tags endpoint returned a non-success status",
    }
