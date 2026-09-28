# Production Stubs

Drop-in skeletons aligned with the hardening pack contracts.

| File | Purpose | Target repo |
|------|---------|-------------|
| `python/event_envelope.py` | Canonical event builder | agentic-harness / agency-agents |
| `python/model_router.py` | Provider-neutral task → binding | agentic-harness |
| `python/lead_ingestion.py` | Normalize + dedupe + qualify + emit | agency-agents / FirstCall |
| `typescript/cloudflare-ingress.ts` | Edge lead.received Worker | moltworker / edge gateway |

## Quick smoke test (Python)

```bash
cd stubs/python
python3 -c "
from event_envelope import lead_received
from model_router import select_binding
from lead_ingestion import ingest_lead, reset_seen

reset_seen()
r = ingest_lead({
    'full_name': 'Aisha Al Maktoum',
    'phone': '+971500000000',
    'transaction_type': 'buy',
    'budget_min': 2000000,
    'contact_consent': True,
    'marketing_consent': False,
}, tenant_id='tenant-demo', source_channel='web_form')
print('duplicate', r['duplicate'])
print('status', r['lead']['status'], r['lead']['qualification'])
print('events', [e['event_type'] for e in r['events']])
print('route', select_binding('classify'))
"
```

## Production notes

1. Replace `_SEEN` in `lead_ingestion.py` with a durable unique constraint.
2. Wire `select_binding` health via your observability / circuit breakers.
3. Point the Worker `BUS_URL` at sahiixx-bus produce endpoint.
4. Do not hardcode Azure deployment names outside the registry layer.
