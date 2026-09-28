# SAHIIXX Production Target Architecture

```text
                    ┌─────────────────────┐
                    │ Telegram / Web / CRM │
                    │ Forms / Voice / API  │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ Authenticated Edge  │
                    │ Cloudflare Gateway  │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ FirstCall API       │
                    │ Idempotency + Auth  │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ sahiixx-bus         │
                    │ Durable Events      │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ agency-agents       │
                    │ Bounded Workflows   │
                    │ (agentic-harness)   │
                    └──────┬─────┬───────┘
                            ↓     ↓
                ┌──────────────┐ ┌──────────────┐
                │ Qualification│ │ Matching     │
                │ Agent        │ │ Agent        │
                └──────┬──────┘ └──────┬──────┘
                       ↓                ↓
                ┌──────────────────────────────┐
                │ Human Approval / CRM Action  │
                └─────────────┬───────────────┘
                               ↓
                    ┌─────────────────────┐
                    │ Revenue Ledger      │
                    │ Deals + Commission  │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ Metrics / Dashboard │
                    │ ROI / Conversion    │
                    └─────────────────────┘
```

## Non-negotiable rules

1. **One platform** — agency-agents + agentic-harness is the only production orchestrator.
2. **One event contract** — every revenue and agent event uses the canonical envelope.
3. **One memory policy** — verified CRM facts cannot be overwritten by model hypotheses.
4. **One revenue owner** — FirstCall owns lead → deal → commission state.
5. **Adapters only** — friday-os, hermes, openclaw, n8n, etc. never own business state.
6. **Human gates** — outreach and irreversible revenue mutations require approval.
7. **Proof over vanity** — dashboards show cohort conversion and cost, not raw lead counts.

## Supporting contracts (this package)

| File | Purpose |
|------|---------|
| `contracts/event-envelope.json` | Canonical event schema |
| `contracts/model-routing.yaml` | Provider-neutral model selection |
| `contracts/bus-requirements.md` | Production bus checklist |
| `schemas/lead-appointment-deal.json` | Revenue entity schemas |
| `policies/memory-policy.md` | Memory correctness rules |
| `policies/action-class-gates.md` | Self-healing safety classes |
| `matrix/repo-classification.md` | Repo ownership matrix |
| `checklists/phase-*.md` | Implementation sequence |
