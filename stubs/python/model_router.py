"""
SAHIIXX Provider-Neutral Model Router — drop-in.

Aligns with contracts/model-routing.yaml v1.0.
Resolve task_class → binding at runtime. Never hardcode Azure deployment names
in application code; map them only inside the registry/adapter layer.
"""

from __future__ import annotations

from typing import Any, Optional

ROUTING_TABLE: dict[str, dict[str, Any]] = {
    "classify": {
        "preferred": "local_fast",
        "fallback": ["hosted_general"],
        "constraints": {"max_latency_ms": 800, "structured_output": True, "privacy": "tenant_ok"},
    },
    "extract": {
        "preferred": "local_structured",
        "fallback": ["hosted_general"],
        "constraints": {"max_latency_ms": 1500, "structured_output": True, "privacy": "tenant_ok"},
    },
    "plan": {
        "preferred": "hosted_reasoning",
        "fallback": ["local_reasoning", "hosted_general"],
        "constraints": {"max_latency_ms": 8000, "structured_output": False, "privacy": "tenant_ok"},
    },
    "voice": {
        "preferred": "realtime_low_latency",
        "fallback": [],
        "constraints": {"max_latency_ms": 400, "structured_output": False, "privacy": "tenant_ok"},
    },
    "judge": {
        "preferred": "independent_evaluator",
        "fallback": ["hosted_reasoning"],
        "constraints": {
            "max_latency_ms": 5000,
            "structured_output": True,
            "privacy": "tenant_ok",
            "must_differ_from": "plan",
        },
    },
    "enrich": {
        "preferred": "hosted_general",
        "fallback": [],
        "constraints": {"max_latency_ms": 10000, "privacy": "external_ok"},
    },
}

CAPABILITY_SLOTS: dict[str, dict[str, str]] = {
    "local_fast": {"provider": "ollama", "model": "qwen2.5-3b"},
    "local_structured": {"provider": "ollama", "model": "qwen2.5-7b"},
    "local_reasoning": {"provider": "ollama", "model": "qwen2.5-32b"},
    "hosted_general": {"provider": "openai", "model": "gpt-4o-mini"},
    "hosted_reasoning": {"provider": "openai", "model": "o3"},
    "realtime_low_latency": {"provider": "openai", "model": "gpt-4o-realtime-preview"},
    "independent_evaluator": {"provider": "anthropic", "model": "claude-opus-4"},
}

_HEALTH: dict[str, bool] = {slot: True for slot in CAPABILITY_SLOTS}


def set_slot_health(slot: str, healthy: bool) -> None:
    if slot in _HEALTH:
        _HEALTH[slot] = healthy


def select_binding(
    task_class: str,
    *,
    privacy_tier: str = "tenant_ok",
    latency_budget_ms: Optional[int] = None,
    cost_budget_usd: Optional[float] = None,
    structured_output: Optional[bool] = None,
    exclude_slots: Optional[set[str]] = None,
) -> dict[str, Any]:
    if task_class not in ROUTING_TABLE:
        raise ValueError(f"Unknown task_class: {task_class}")

    entry = ROUTING_TABLE[task_class]
    constraints = entry["constraints"]
    candidates = [entry["preferred"]] + list(entry.get("fallback") or [])
    exclude = exclude_slots or set()

    need_structured = constraints.get("structured_output", False)
    if structured_output is not None:
        need_structured = structured_output

    for slot in candidates:
        if slot in exclude:
            continue
        if not _HEALTH.get(slot, True):
            continue
        binding = CAPABILITY_SLOTS.get(slot)
        if not binding:
            continue

        if privacy_tier == "local_only" and not slot.startswith("local_"):
            continue
        if constraints.get("privacy") == "local_only" and not slot.startswith("local_"):
            continue

        if need_structured and slot in {"hosted_reasoning", "local_reasoning"} and task_class != "plan":
            continue

        return {
            "task_class": task_class,
            "binding": slot,
            "provider": binding["provider"],
            "model": binding["model"],
            "constraints": constraints,
        }

    raise RuntimeError(f"No valid route for task_class={task_class} under given constraints")


def resolve_for_event(task_class: str, **kwargs: Any) -> dict[str, Any]:
    sel = select_binding(task_class, **kwargs)
    return {
        "model": f"{sel['provider']}/{sel['model']}",
        "binding": sel["binding"],
        "task_class": task_class,
    }
