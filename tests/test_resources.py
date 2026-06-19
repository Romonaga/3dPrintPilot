from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.domains.resources.service import build_resource_status
from backend.domains.resources.worker import LocalLlmAdmissionPolicy, LocalLlmRequestGate, QueueState, WorkQueue


def test_resource_status_reports_unavailable_gpu_and_controls(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    def fake_urlopen(*args, **kwargs):
        raise OSError("ollama offline")

    monkeypatch.setattr("backend.domains.resources.service.subprocess.run", fake_run)
    monkeypatch.setattr("backend.domains.resources.service.urllib.request.urlopen", fake_urlopen)

    status = build_resource_status()

    assert status["gpu"]["available"] is False
    assert status["local_llm"]["max_concurrent_requests"] == 1
    assert status["local_llm"]["max_context_tokens"] == 8192
    assert "network_scan" in status["queues"]["local_llm"]["supported_job_types"]
    assert status["ollama"]["available"] is False


def test_resource_status_endpoint_exposes_clear_unavailable_state(monkeypatch):
    monkeypatch.setattr(
        "backend.domains.resources.service._read_gpu_status",
        lambda: {"available": False, "error": "nvidia-smi unavailable"},
    )
    monkeypatch.setattr(
        "backend.domains.resources.service._read_ollama_status",
        lambda: {"available": False, "base_url": "http://localhost:11434/api", "model": "qwen3", "error": "offline"},
    )
    client = TestClient(create_app())

    response = client.get("/api/resources/status")

    assert response.status_code == 200
    body = response.json()
    assert body["gpu"]["available"] is False
    assert body["ollama"]["available"] is False
    assert body["queues"]["local_llm"]["max_concurrent"] == 1


def test_local_llm_gate_rejects_pressure_and_limits():
    gate = LocalLlmRequestGate(
        LocalLlmAdmissionPolicy(
            max_concurrent_requests=1,
            max_context_tokens=4000,
            max_output_tokens=1000,
            min_free_vram_mib=2000,
            max_gpu_memory_used_percent=80,
            max_gpu_temperature_c=75,
        )
    )
    healthy_gpu = {
        "available": True,
        "memory_used_percent": 30,
        "memory_total_mib": 24_576,
        "memory_used_mib": 8_000,
        "temperature_c": 62,
    }

    assert gate.evaluate(healthy_gpu, QueueState(), 2000, 500).allowed is True
    assert gate.evaluate(healthy_gpu, QueueState(active_count=1), 2000, 500).reason == "concurrency_limit"
    assert gate.evaluate(healthy_gpu, QueueState(), 4001, 500).reason == "context_limit"
    assert gate.evaluate(healthy_gpu, QueueState(), 2000, 1001).reason == "output_limit"
    assert gate.evaluate({"available": False}, QueueState(), 2000, 500).reason == "gpu_unavailable"
    assert gate.evaluate({**healthy_gpu, "memory_used_percent": 90}, QueueState(), 2000, 500).reason == "vram_pressure"
    assert gate.evaluate({**healthy_gpu, "temperature_c": 80}, QueueState(), 2000, 500).reason == "temperature_pressure"
    free_vram_decision = gate.evaluate(
        {**healthy_gpu, "memory_total_mib": 10_000, "memory_used_mib": 9_000},
        QueueState(),
        2000,
        500,
    )
    assert free_vram_decision.reason == "free_vram_limit"


def test_local_llm_gate_honors_oom_cooldown():
    gate = LocalLlmRequestGate()
    decision = gate.evaluate(
        {"available": True},
        QueueState(cooldown_until=datetime.now(UTC) + timedelta(seconds=60)),
        100,
        100,
    )

    assert decision.allowed is False
    assert decision.reason == "oom_cooldown"
    assert decision.retry_after_seconds is not None


def test_work_queue_orders_by_priority_then_fifo():
    queue = WorkQueue()

    queue.push("website_import", {"id": 2}, priority=50)
    queue.push("network_scan", {"id": 1}, priority=10)
    queue.push("model_analysis", {"id": 3}, priority=50)

    assert queue.pending_count == 3
    assert queue.pop() == ("network_scan", {"id": 1})
    assert queue.pop() == ("website_import", {"id": 2})
    assert queue.pop() == ("model_analysis", {"id": 3})
    assert queue.pop() is None
