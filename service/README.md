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

## Tenant-scoped lead storage

`/v1/leads` resolves the tenant from the request body, then `X-Tenant-Id`, then
`default-tenant`. Idempotency keys and lead IDs are unique **within that tenant**.
The same key or supplied lead ID can be used by another tenant independently;
replaying a key returns only that tenant's cached response without new events or
cost records. Public lead IDs and response shapes are unchanged.

On startup, `init_db()` upgrades legacy SQLite `idempotency` and `leads` tables
to composite primary keys `(tenant_id, key)` and `(tenant_id, lead_id)`. Both
table upgrades run in one write transaction. Existing rows, JSON, cohorts, and
timestamps are copied unchanged, and the original tables remain as
`idempotency_legacy_v1` and `leads_legacy_v1` snapshots; nothing is dropped.
Events and cost records stay in their existing tables. Repeated startup is safe,
and a failed migration rolls back the entire upgrade.

Back up the SQLite database and stop old service processes before upgrading;
the old global-key upsert is incompatible with the new primary key. The retained
tables are pre-upgrade snapshots, not live mirrors. Migration preserves the
stored data but cannot recover lead data already overwritten by an earlier
cross-tenant collision.

## Offline regression tests

From the repository root, using a local virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r service/requirements-test.txt
.venv/bin/python -m unittest discover -s service -p 'test_*.py' -v
```

Every test uses a separate temporary SQLite database. Qualification is
deterministic and no model inference or paid provider calls are made.

`docs/revenue-path-workflow.yml` is a GitHub Actions template for the same suite,
with pinned Python, action revisions, and dependency versions. CI is **not yet
active**: the current GitHub token lacks the `workflow` scope required to publish
it. Once workflow access is available, place the template at
`.github/workflows/revenue-path.yml` to run on relevant pull requests and
main-branch changes. The pinned install and test command have been verified in
a fresh local environment; execution on a GitHub-hosted runner remains unverified.

## Production swap

- Set `SAHIIXX_DB` to a Postgres DSN and replace `db.py` SQL with Postgres (or SQLAlchemy).
- Point Cloudflare Worker `BUS_URL` at your bus; have consumers call this API or write the same tables.
- Replace deterministic `score_qualification` with structured-output model via `model_router.select_binding("classify")`.

## Human gates

Outreach and terminal deal changes refuse without `human_approved=true` — matches action-class policy.
