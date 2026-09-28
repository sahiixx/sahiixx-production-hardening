"""
Idempotent lead ingestion skeleton.

Aligns with schemas/lead-appointment-deal.json and the event envelope.
In production: replace in-memory SEEN with Redis/Postgres unique constraint
on (tenant_id, idempotency_key) or (tenant_id, lead_id).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from event_envelope import build_event, lead_received

_SEEN: set[str] = set()


def normalize_lead(raw: dict[str, Any], *, tenant_id: Optional[str] = None) -> dict[str, Any]:
    lead_id = raw.get("lead_id") or str(uuid.uuid4())
    return {
        "lead_id": lead_id,
        "tenant_id": tenant_id or raw.get("tenant_id") or "default-tenant",
        "source": raw.get("source") or "api",
        "status": "normalized",
        "contact": {
            "full_name": raw.get("full_name") or raw.get("name"),
            "email": raw.get("email"),
            "phone": raw.get("phone"),
            "preferred_channel": raw.get("preferred_channel"),
            "locale": raw.get("locale"),
            "timezone": raw.get("timezone"),
        },
        "intent": {
            "transaction_type": raw.get("transaction_type") or "buy",
            "property_type": raw.get("property_type"),
            "budget_min": raw.get("budget_min"),
            "budget_max": raw.get("budget_max"),
            "currency": raw.get("currency") or "AED",
            "bedrooms": raw.get("bedrooms"),
            "notes": raw.get("notes"),
        },
        "consent": {
            "marketing": bool(raw.get("marketing_consent", False)),
            "contact": bool(raw.get("contact_consent", True)),
            "recorded_at": raw.get("consent_recorded_at"),
            "channel": raw.get("source") or "api",
        },
    }


def score_qualification(lead: dict[str, Any]) -> dict[str, Any]:
    score = 0.0
    intent = lead.get("intent") or {}
    contact = lead.get("contact") or {}
    consent = lead.get("consent") or {}

    if intent.get("transaction_type") in {"buy", "rent", "sell", "invest"}:
        score += 0.35
    if contact.get("phone"):
        score += 0.20
    if contact.get("email"):
        score += 0.10
    if consent.get("contact"):
        score += 0.20
    if intent.get("budget_min") is not None or intent.get("budget_max") is not None:
        score += 0.15

    score = min(score, 1.0)
    if score >= 0.8:
        band = "A"
    elif score >= 0.6:
        band = "B"
    elif score >= 0.4:
        band = "C"
    else:
        band = "F"

    return {
        "score": round(score, 3),
        "band": band,
        "reasons": [],
        "model": "stub/deterministic",
        "human_override": False,
    }


def ingest_lead(
    raw: dict[str, Any],
    *,
    tenant_id: Optional[str] = None,
    source_channel: str = "api",
    source_system: str = "firstcall-api",
    idempotency_key: Optional[str] = None,
    emit_events: bool = True,
) -> dict[str, Any]:
    lead = normalize_lead(raw, tenant_id=tenant_id)
    tid = lead["tenant_id"]
    key = idempotency_key or f"lead:{tid}:{lead['lead_id']}"

    if key in _SEEN:
        return {"lead": lead, "events": [], "duplicate": True}

    _SEEN.add(key)

    qual = score_qualification(lead)
    lead["qualification"] = qual
    lead["status"] = "qualified" if qual["score"] >= 0.6 else "disqualified"

    events: list[dict[str, Any]] = []
    if emit_events:
        received = lead_received(
            lead,
            tenant_id=tid,
            source_channel=source_channel,
            source_system=source_system,
            idempotency_key=key,
        )
        events.append(received)

        events.append(
            build_event(
                "lead.qualified",
                {"lead": lead, "qualification": qual},
                tenant_id=tid,
                source_channel=source_channel,
                source_system=source_system,
                correlation_id=received["correlation_id"],
                causation_id=received["event_id"],
                idempotency_key=f"lead.qualified:{lead['lead_id']}",
                entities={"lead_id": lead["lead_id"]},
                model=qual.get("model"),
            )
        )

    return {"lead": lead, "events": events, "duplicate": False}


def reset_seen() -> None:
    _SEEN.clear()
