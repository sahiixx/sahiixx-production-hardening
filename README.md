# SAHIIXX Production Hardening Pack

**Generated:** 2026-09-29  
**Purpose:** Concrete artifacts that close every gap identified in the estate assessment.

This pack turns the high-level “consolidate and harden” diagnosis into implementable contracts, policies, schemas, and checklists.

## What was fixed

| Weakness | Artifact that addresses it |
|----------|----------------------------|
| Too many overlapping control planes | `matrix/repo-classification.md` + Phase 1 checklist |
| Bus lacks production semantics | `contracts/bus-requirements.md` + event envelope |
| Revenue attribution not first-class | `contracts/event-envelope.json` + `schemas/lead-appointment-deal.json` |
| Model routing provider-specific | `contracts/model-routing.yaml` |
| Memory lacks business correctness | `policies/memory-policy.md` |
| Self-healing can be dangerous | `policies/action-class-gates.md` |
| No clear implementation sequence | `checklists/phase-1` … `phase-4` |
| Architecture not locked | `docs/PRODUCTION_ARCHITECTURE.md` |

## Directory layout

```text
sahiixx-production-hardening/
├── README.md
├── contracts/
│   ├── event-envelope.json
│   ├── model-routing.yaml
│   └── bus-requirements.md
├── schemas/
│   └── lead-appointment-deal.json
├── policies/
│   ├── memory-policy.md
│   └── action-class-gates.md
├── matrix/
│   └── repo-classification.md
├── checklists/
│   ├── phase-1-establish-truth.md
│   ├── phase-2-revenue-path.md
│   ├── phase-3-prove-outcomes.md
│   └── phase-4-scale-safely.md
└── docs/
    └── PRODUCTION_ARCHITECTURE.md
```

## How to use

1. Treat this pack as the **authoritative production contracts**.
2. Start with **Phase 1** checklist — inventory, classify, lock schemas and envelope.
3. Implement the event envelope and model router inside `agentic-harness` / `agency-agents`.
4. Harden `sahiixx-bus` against the requirements doc.
5. Enforce memory policy and action-class gates at the tool/dispatcher boundary.
6. Progress through Phases 2–4; do not skip the human-approval gates.

## Non-goals

- This pack does **not** rewrite the existing repositories.
- It does **not** delete any code.
- It supplies the missing contracts so the existing strong pieces (`agentic-harness`, Agency presets, etc.) can converge on one production path.

## Next immediate actions

1. Publish the event envelope and model-routing contract into `agentic-harness`.
2. Run the full repository classification (Phase 1.1).
3. Identify the live FirstCall / CRM source of truth and map it to the revenue schemas.
