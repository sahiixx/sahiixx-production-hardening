"""
Seed a realistic Dubai RE cohort comparison and print revenue proof.

Run:
  cd service && SAHIIXX_DB=/tmp/demo.db PYTHONPATH=../stubs/python python3 demo_seed.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "stubs" / "python"))

os.environ.setdefault("SAHIIXX_DB", str(Path(__file__).parent / "demo_revenue.db"))

import db
from app import (
    create_lead,
    book_appointment,
    upsert_deal,
    record_commission,
    LeadIn,
    AppointmentIn,
    DealIn,
    CommissionIn,
)


def run() -> None:
    db.init_db()
    tenant = "tenant-dubai-re"

    ai_leads = [
        LeadIn(
            full_name="Aisha Al Maktoum",
            phone="+971501111111",
            email="aisha@example.ae",
            transaction_type="buy",
            budget_min=2_500_000,
            budget_max=4_000_000,
            contact_consent=True,
            source="web_form",
            tenant_id=tenant,
            cohort="ai_assisted",
        ),
        LeadIn(
            full_name="James Chen",
            phone="+971502222222",
            transaction_type="invest",
            budget_min=5_000_000,
            contact_consent=True,
            source="telegram",
            tenant_id=tenant,
            cohort="ai_assisted",
        ),
        LeadIn(
            full_name="Sara Noor",
            phone="+971503333333",
            transaction_type="rent",
            budget_min=120_000,
            contact_consent=True,
            source="api",
            tenant_id=tenant,
            cohort="ai_assisted",
        ),
    ]

    human_leads = [
        LeadIn(
            full_name="Omar Hassan",
            phone="+971504444444",
            transaction_type="buy",
            budget_min=1_800_000,
            contact_consent=True,
            source="crm",
            tenant_id=tenant,
            cohort="human_only",
        ),
        LeadIn(
            full_name="Lina Petrova",
            phone="+971505555555",
            transaction_type="buy",
            budget_min=3_000_000,
            contact_consent=True,
            source="web_form",
            tenant_id=tenant,
            cohort="human_only",
        ),
    ]

    created = []
    for lead in ai_leads + human_leads:
        r = create_lead(lead)
        created.append(r)
        print(f"lead {r['lead']['status']:12} cohort={lead.cohort:12} {r['lead']['contact']['full_name']}")

    ai_ids = [c["lead"]["lead_id"] for c in created[:3] if c["lead"]["status"] == "qualified"]
    human_ids = [c["lead"]["lead_id"] for c in created[3:] if c["lead"]["status"] == "qualified"]

    for lid in ai_ids[:2]:
        book_appointment(
            AppointmentIn(
                lead_id=lid,
                tenant_id=tenant,
                scheduled_at="2026-10-05T10:00:00Z",
                human_approved=True,
            )
        )
        d = upsert_deal(
            DealIn(
                lead_id=lid,
                tenant_id=tenant,
                value=3_200_000,
                status="won",
                ai_assisted=True,
                human_approved=True,
            )
        )
        record_commission(
            CommissionIn(
                deal_id=d["deal"]["deal_id"],
                tenant_id=tenant,
                amount=64_000,
                status="paid",
            )
        )
        print(f"  AI deal won lead={lid[:8]} commission=64000 AED")

    if human_ids:
        lid = human_ids[0]
        book_appointment(
            AppointmentIn(
                lead_id=lid,
                tenant_id=tenant,
                scheduled_at="2026-10-06T14:00:00Z",
                human_approved=True,
            )
        )
        d = upsert_deal(
            DealIn(
                lead_id=lid,
                tenant_id=tenant,
                value=2_100_000,
                status="won",
                ai_assisted=False,
                human_approved=True,
            )
        )
        record_commission(
            CommissionIn(
                deal_id=d["deal"]["deal_id"],
                tenant_id=tenant,
                amount=42_000,
                status="paid",
            )
        )
        print(f"  Human deal won lead={lid[:8]} commission=42000 AED")

    m = db.fetch_metrics(tenant)
    print("\n========== REVENUE PROOF ==========")
    print(f"Commission total:   {m['commission_total']:,.0f} AED")
    print(f"Agent cost (USD):   {m['agent_cost_usd']:.4f}")
    print(f"Revenue / lead:     {m['revenue_per_lead']:,.2f}")
    print(f"Cost / lead (USD):  {m['cost_per_lead']:.6f}")
    print(f"ROI (vs agent $):   {m['roi']}")
    print(f"Leads by cohort:    {m['leads_by_cohort_status']}")
    print(f"Deals by cohort:    {m['deals_by_cohort']}")
    print(f"Funnel events:      {m['funnel_event_counts']}")
    print("===================================")


if __name__ == "__main__":
    run()
