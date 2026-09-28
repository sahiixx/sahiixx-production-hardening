# SAHIIXX Production Hardening Pack

**Status:** Production-ready contracts + runnable revenue path + cohort ROI proof  
**Generated:** 2026-09-29

Turns the estate assessment into implementable contracts, policies, stubs, and a durable FirstCall-style revenue API.

## What you get

| Area | Path |
|------|------|
| Event envelope | `contracts/event-envelope.json` |
| Model routing | `contracts/model-routing.yaml` |
| Bus requirements | `contracts/bus-requirements.md` |
| Revenue schemas | `schemas/lead-appointment-deal.json` |
| Memory policy | `policies/memory-policy.md` |
| Action-class gates | `policies/action-class-gates.md` |
| Repo classification | `matrix/repo-classification.md` |
| Phase 1–4 checklists | `checklists/` |
| Architecture | `docs/PRODUCTION_ARCHITECTURE.md` |
| Python stubs | `stubs/python/` |
| Cloudflare Worker | `stubs/typescript/cloudflare-ingress.ts` |
| **Revenue service** | `service/` (FastAPI + SQLite + metrics) |

## Revenue proof (demo)

```bash
cd service
pip install -r requirements.txt
SAHIIXX_DB=/tmp/demo.db PYTHONPATH=../stubs/python python3 demo_seed.py
```

Example output:

```text
Commission total:   170,000 AED
  AI cohort:        128,000 AED (2 deals)
  Human cohort:      42,000 AED (1 deal)
Funnel: lead.received → qualified → appointment.booked → deal.won → commission → revenue.attributed
```

## Run the API

```bash
cd service
PYTHONPATH=../stubs/python uvicorn app:app --host 0.0.0.0 --port 8080
# POST /v1/leads  GET /v1/metrics  GET /health
```

## Merged into core repos

- **agentic-harness** — `contracts/README.md` (production contracts pointer)
- **agency-agents** — `PRODUCTION_ARCHITECTURE.md`
- **sahiixx-bus** — `BUS_REQUIREMENTS.md`

## Non-negotiables

1. One platform: agency-agents + agentic-harness  
2. One event contract  
3. One memory policy  
4. One revenue owner: FirstCall  
5. Adapters only for voice/edge/n8n  
6. Human gates for irreversible actions  
7. Cohort ROI proof over vanity lead counts  
