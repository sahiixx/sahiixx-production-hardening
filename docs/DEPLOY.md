# Deploy runbook

## 1. FirstCall API (any host with Python 3.12+)

```bash
git clone https://github.com/sahiixx/sahiixx-production-hardening.git
cd sahiixx-production-hardening
cp .env.example .env   # fill secrets
pip install -r service/requirements.txt
export SAHIIXX_DB=/var/lib/sahiixx/revenue.db
export PYTHONPATH=stubs/python:service
python3 service/demo_seed.py   # optional proof data
python3 -m uvicorn app:app --app-dir service --host 0.0.0.0 --port 8080
```

Docker:

```bash
docker compose -f service/docker-compose.yml up -d --build
```

Health: `GET /health`  Metrics: `GET /v1/metrics?tenant_id=...`

## 2. Cloudflare Worker → FirstCall

```bash
cd stubs/typescript
npx wrangler deploy
npx wrangler secret put BUS_TOKEN   # optional
# In dashboard vars:
#   FIRSTCALL_URL = https://YOUR-API-HOST/v1/leads
```

Worker POSTs leads with `Idempotency-Key` and `X-Tenant-Id`.

## 3. Secrets you must supply

| Variable | Where |
|----------|--------|
| `SAHIIXX_DB` | API host path or Postgres URL |
| `AZURE_FOUNDRY_API_KEY` | agentic-harness runtime |
| `FIRSTCALL_URL` | Worker vars |
| `CRM_API_KEY` / channel tokens | your connectors |

No public cloud can be fully deployed without these values.
