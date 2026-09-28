# FirstCall Revenue Service (production-lite)

Real-time, durable lead → appointment → deal → commission path with **cohort ROI metrics**.

## Run

```bash
cd service
pip install -r requirements.txt
PYTHONPATH=../stubs/python uvicorn app:app --host 0.0.0.0 --port 8080
```

Seed a Dubai RE cohort comparison:

```bash
PYTHONPATH=../stubs/python python3 demo_seed.py
```

## Proof endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/leads` | Idempotent ingest + qualify (header `Idempotency-Key`) |
| POST | `/v1/appointments` | Book (requires `human_approved=true`) |
| POST | `/v1/deals` | Create/win/lose deal (terminal states need approval) |
| POST | `/v1/commissions` | Record commission → `revenue.attributed` |
| GET | `/v1/metrics` | Cohort conversion, cost, ROI |

## Production swap

- Set `SAHIIXX_DB` to a Postgres DSN and replace `db.py` SQL with Postgres (or SQLAlchemy).
- Point Cloudflare Worker `BUS_URL` at your bus; have consumers call this API or write the same tables.
- Replace deterministic `score_qualification` with structured-output model via `model_router.select_binding("classify")`.

## Human gates

Outreach and terminal deal changes refuse without `human_approved=true` — matches action-class policy.
