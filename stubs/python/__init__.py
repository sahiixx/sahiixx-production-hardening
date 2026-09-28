"""SAHIIXX production stubs — event envelope, model router, lead ingestion."""

from event_envelope import build_event, lead_received, EVENT_TYPES
from model_router import select_binding, resolve_for_event, ROUTING_TABLE
from lead_ingestion import ingest_lead, normalize_lead, score_qualification

__all__ = [
    "build_event",
    "lead_received",
    "EVENT_TYPES",
    "select_binding",
    "resolve_for_event",
    "ROUTING_TABLE",
    "ingest_lead",
    "normalize_lead",
    "score_qualification",
]
