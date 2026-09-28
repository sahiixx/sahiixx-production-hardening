"""
End-to-end example: ingest lead → select model → emit events.

Run: python3 example_flow.py
"""

from event_envelope import build_event
from model_router import select_binding, resolve_for_event
from lead_ingestion import ingest_lead, reset_seen


def main() -> None:
    reset_seen()

    raw = {
        "full_name": "Aisha Al Maktoum",
        "phone": "+971500000000",
        "email": "aisha@example.ae",
        "transaction_type": "buy",
        "budget_min": 2_500_000,
        "budget_max": 4_000_000,
        "currency": "AED",
        "contact_consent": True,
        "marketing_consent": False,
        "source": "web_form",
    }

    result = ingest_lead(
        raw,
        tenant_id="tenant-dubai-re",
        source_channel="web_form",
        source_system="firstcall-api",
    )

    print("=== Lead ===")
    print(result["lead"]["status"], result["lead"]["qualification"])
    print("duplicate:", result["duplicate"])

    print("\n=== Events ===")
    for e in result["events"]:
        print(e["event_type"], e["event_id"][:8], "corr=", e["correlation_id"][:8])

    print("\n=== Model routes ===")
    for task in ("classify", "extract", "plan", "judge"):
        try:
            b = select_binding(task)
            print(f"  {task:10} → {b['provider']}/{b['model']}  [{b['binding']}]")
        except RuntimeError as err:
            print(f"  {task:10} → FAIL {err}")

    route = resolve_for_event("classify")
    run_event = build_event(
        "agent.run.completed",
        {"result": "qualified", "band": result["lead"]["qualification"]["band"]},
        tenant_id="tenant-dubai-re",
        source_channel="internal",
        source_system="agency-agents",
        correlation_id=result["events"][0]["correlation_id"] if result["events"] else None,
        model=route["model"],
        cost_usd=0.001,
        entities={"lead_id": result["lead"]["lead_id"]},
    )
    print("\n=== agent.run.completed ===")
    print(run_event["event_type"], "model=", run_event["agent"]["model"])


if __name__ == "__main__":
    main()
