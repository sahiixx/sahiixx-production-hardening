# GO-LIVE — Production cutover checklist

Use this after contracts are merged and the revenue service has been proven locally.

## Prerequisites (done)

- [x] Canonical event envelope
- [x] Provider-neutral model router (in agentic-harness)
- [x] Bus requirements documented
- [x] Revenue schemas + FirstCall service
- [x] Cohort metrics (`GET /v1/metrics`)
- [x] Human gates on appointments / terminal deals
- [x] Integration tests green
- [x] PRs merged: agentic-harness, agency-agents, sahiixx-bus

## Cutover steps (your environment)

### 1. Database

```bash
export SAHIIXX_DB=/var/lib/sahiixx/revenue.db
# later: postgresql://user:pass@host:5432/firstcall
```

### 2. Deploy FirstCall API

```bash
cd sahiixx-production-hardening
docker compose -f service/docker-compose.yml up -d --build
```

Health: `GET /health` → `{"status":"ok"}`

### 3. Edge ingress

Cloudflare Worker env:

```text
BUS_URL   = https://<firstcall-or-bus>/v1/leads
BUS_TOKEN = <service token>
```

### 4. CRM source of truth

- Map external IDs into `lead.external_ids`
- Only FirstCall writes lead / deal / commission state

### 5. Model routing in call sites

```python
from model_router import complete_for
complete_for("classify", prompt)
```

### 6. Bus hardening

Implement durable store, idempotency, DLQ, schema validation per `BUS_REQUIREMENTS.md`.

### 7. Prove revenue

```bash
curl -s "$API/v1/metrics?tenant_id=<tenant>" | jq .
```

### 8. Freeze duplicates

Add `STATUS.md` per `matrix/repo-classification.md`. Mark before archive.

## Success criteria

1. Duplicate Idempotency-Key → single ledger row
2. Appointment/deal.won without human_approved → 403
3. `/v1/metrics` shows `revenue.attributed` for paid commission
4. No hardcoded Azure deployment names outside the router registry
