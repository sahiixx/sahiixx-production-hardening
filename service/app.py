"""
FirstCall-style revenue API — real-time, durable, cohort-aware.

Run:
  pip install -r requirements.txt
  PYTHONPATH=../stubs/python uvicorn app:app --reload --port 8080

Endpoints:
  POST /v1/leads              — idempotent ingest + qualify + events
  POST /v1/appointments       — book appointment (human-gate friendly)
  POST /v1/deals              — create/update deal
  POST /v1/commissions        — record commission (revenue outcome)
  GET  /v1/metrics            — cohort ROI / funnel proof
  GET  /health
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

_STUBS = Path(__file__).resolve().parent.parent / "stubs" / "python"
if str(_STUBS) not in sys.path:
    sys.path.insert(0, str(_STUBS))

from event_envelope import build_event, lead_received  # noqa: E402
from lead_ingestion import normalize_lead, score_qualification  # noqa: E402
from model_router import resolve_for_event  # noqa: E402

import db  # noqa: E402

app = FastAPI(title="SAHIIXX FirstCall Revenue API", version="1.0.0")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "firstcall-revenue"}


class LeadIn(BaseModel):
    full_name: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    transaction_type: Optional[str] = "buy"
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: str = "AED"
    contact_consent: bool = True
    marketing_consent: bool = False
    source: str = "api"
    lead_id: Optional[str] = None
    tenant_id: Optional[str] = None
    cohort: str = Field(default="ai_assisted", description="ai_assisted | human_only")


class AppointmentIn(BaseModel):
    lead_id: str
    tenant_id: str
    scheduled_at: str
    meeting_type: str = "in_person"
    location: Optional[str] = None
    agent_id: Optional[str] = None
    human_approved: bool = False


class DealIn(BaseModel):
    lead_id: str
    tenant_id: str
    value: float
    currency: str = "AED"
    status: str = "created"
    ai_assisted: bool = True
    appointment_id: Optional[str] = None
    human_approved: bool = False


class CommissionIn(BaseModel):
    deal_id: str
    tenant_id: str
    amount: float
    currency: str = "AED"
    status: str = "pending"
    beneficiary_agent_id: Optional[str] = None


@app.post("/v1/leads")
def create_lead(
    body: LeadIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    if not isinstance(idempotency_key, (str, type(None))):
        idempotency_key = None
    if not isinstance(x_tenant_id, (str, type(None))):
        x_tenant_id = None
    tenant_id = body.tenant_id or x_tenant_id or "default-tenant"
    raw = body.model_dump(exclude_none=True)
    lead = normalize_lead(raw, tenant_id=tenant_id)
    key = idempotency_key or f"lead:{tenant_id}:{lead['lead_id']}"

    cached = db.get_idempotent(key, tenant_id)
    if cached:
        return {**cached, "duplicate": True}

    route = resolve_for_event("classify")
    qual = score_qualification(lead)
    qual["model"] = route["model"]
    lead["qualification"] = qual
    lead["status"] = "qualified" if qual["score"] >= 0.6 else "disqualified"
    lead["updated_at"] = utc_now()
    lead["created_at"] = lead.get("created_at") or utc_now()

    events = []
    channel = body.source if body.source in {
        "telegram", "web_form", "crm", "api", "voice", "whatsapp", "email", "internal"
    } else "api"
    received = lead_received(
        lead,
        tenant_id=tenant_id,
        source_channel=channel,
        source_system="firstcall-api",
        idempotency_key=key,
    )
    events.append(received)

    q_event = build_event(
        "lead.qualified",
        {"lead": lead, "qualification": qual},
        tenant_id=tenant_id,
        source_channel=received["source"]["channel"],
        source_system="firstcall-api",
        correlation_id=received["correlation_id"],
        causation_id=received["event_id"],
        idempotency_key=f"lead.qualified:{lead['lead_id']}",
        entities={"lead_id": lead["lead_id"]},
        model=route["model"],
        cost_usd=0.001,
    )
    events.append(q_event)

    db.upsert_lead(lead, cohort=body.cohort)
    for e in events:
        db.insert_event(e)
    db.record_cost(
        tenant_id,
        0.001,
        lead_id=lead["lead_id"],
        model=route["model"],
        occurred_at=utc_now(),
    )

    response = {
        "lead": lead,
        "events": events,
        "duplicate": False,
        "model": route["model"],
    }
    db.put_idempotent(key, tenant_id, response, utc_now())
    return response


@app.post("/v1/appointments")
def book_appointment(body: AppointmentIn) -> dict[str, Any]:
    if not body.human_approved:
        raise HTTPException(
            status_code=403,
            detail="human_approval_required: set human_approved=true after operator gate",
        )
    appt_id = str(uuid.uuid4())
    now = utc_now()
    appt = {
        "appointment_id": appt_id,
        "lead_id": body.lead_id,
        "tenant_id": body.tenant_id,
        "status": "booked",
        "scheduled_at": body.scheduled_at,
        "meeting_type": body.meeting_type,
        "location": body.location,
        "agent_id": body.agent_id,
        "created_at": now,
    }
    event = build_event(
        "appointment.booked",
        {"appointment": appt},
        tenant_id=body.tenant_id,
        source_channel="internal",
        source_system="firstcall-api",
        entities={"lead_id": body.lead_id, "appointment_id": appt_id},
        human_approved=True,
    )
    with db.session() as conn:
        conn.execute(
            """
            INSERT INTO appointments (appointment_id, lead_id, tenant_id, status, scheduled_at, data_json, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (appt_id, body.lead_id, body.tenant_id, "booked", body.scheduled_at, __import__("json").dumps(appt), now),
        )
    db.insert_event(event)
    return {"appointment": appt, "event": event}


@app.post("/v1/deals")
def upsert_deal(body: DealIn) -> dict[str, Any]:
    if body.status in {"won", "lost"} and not body.human_approved:
        raise HTTPException(
            status_code=403,
            detail="human_approval_required for terminal deal status",
        )
    deal_id = str(uuid.uuid4())
    now = utc_now()
    deal = {
        "deal_id": deal_id,
        "lead_id": body.lead_id,
        "tenant_id": body.tenant_id,
        "status": body.status,
        "value": body.value,
        "currency": body.currency,
        "ai_assisted": body.ai_assisted,
        "appointment_id": body.appointment_id,
        "created_at": now,
        "closed_at": now if body.status in {"won", "lost"} else None,
    }
    etype = "deal.won" if body.status == "won" else "deal.created"
    if body.status == "lost":
        etype = "deal.lost"
    event = build_event(
        etype,
        {"deal": deal},
        tenant_id=body.tenant_id,
        source_channel="internal",
        source_system="firstcall-api",
        entities={"lead_id": body.lead_id, "deal_id": deal_id},
        human_approved=body.human_approved,
    )
    db.insert_deal(deal)
    db.insert_event(event)
    return {"deal": deal, "event": event}


@app.post("/v1/commissions")
def record_commission(body: CommissionIn) -> dict[str, Any]:
    cid = str(uuid.uuid4())
    now = utc_now()
    c = {
        "commission_id": cid,
        "deal_id": body.deal_id,
        "tenant_id": body.tenant_id,
        "amount": body.amount,
        "currency": body.currency,
        "status": body.status,
        "beneficiary_agent_id": body.beneficiary_agent_id,
        "recorded_at": now,
    }
    event = build_event(
        "commission.recorded",
        {"commission": c},
        tenant_id=body.tenant_id,
        source_channel="internal",
        source_system="firstcall-api",
        entities={"deal_id": body.deal_id, "commission_id": cid},
    )
    events = [event]
    if body.status in {"approved", "paid"}:
        events.append(
            build_event(
                "revenue.attributed",
                {"commission": c, "amount": body.amount, "currency": body.currency},
                tenant_id=body.tenant_id,
                source_channel="internal",
                source_system="firstcall-api",
                causation_id=event["event_id"],
                correlation_id=event["correlation_id"],
                entities={"deal_id": body.deal_id, "commission_id": cid},
            )
        )
    db.insert_commission(c)
    for e in events:
        db.insert_event(e)
    return {"commission": c, "events": events}


@app.get("/v1/metrics")
def metrics(tenant_id: Optional[str] = None) -> dict[str, Any]:
    """Proof dashboard data: cohort conversion, cost, ROI."""
    return db.fetch_metrics(tenant_id)
