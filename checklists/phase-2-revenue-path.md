# Phase 2 — Make the Revenue Path Reliable

**Goal:** Idempotent, durable, auditable lead → appointment → deal flow with human gates.

## Ingestion

- [ ] Idempotent lead ingestion endpoint (idempotency_key required).
- [ ] Normalize and emit `lead.received` → `lead.normalized`.
- [ ] Consent verification path emits `lead.consent_verified` (or blocks).

## Workflow state

- [ ] Durable workflow state machine (persisted, not only in-memory).
- [ ] Every transition emits the corresponding domain event with correlation_id.
- [ ] Replay from event log can reconstruct lead state.

## Qualification & matching

- [ ] Structured-output qualification scoring (score, band, reasons).
- [ ] Emit `lead.qualified` / disqualification with model + cost.
- [ ] Match / routing rules produce `lead.matched` with rule IDs.

## Human approval

- [ ] Outreach and deal-status changes require human approval tokens.
- [ ] Emit `human.approval.requested` / `granted` / `denied`.
- [ ] Agent cannot send messages or mutate deals without a valid token.

## Persistence & cost

- [ ] Every agent decision and model cost written to the event stream and revenue ledger.
- [ ] Memory writes follow the memory policy (no inference overwriting CRM facts).

## Bus hardening (parallel)

- [ ] Durable storage + ack + DLQ + retry policy live.
- [ ] Schema validation on produce.
- [ ] Basic lag and delivery metrics exposed.
