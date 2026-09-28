"""
Integration tests for the revenue path.
Run: cd service && SAHIIXX_DB=/tmp/t.db PYTHONPATH=../stubs/python python3 test_revenue_path.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "stubs" / "python"))

_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["SAHIIXX_DB"] = _db_file.name

import db  # noqa: E402
from app import (  # noqa: E402
    create_lead,
    book_appointment,
    upsert_deal,
    record_commission,
    LeadIn,
    AppointmentIn,
    DealIn,
    CommissionIn,
)


class RevenuePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()

    def test_idempotent_lead(self):
        body = LeadIn(
            full_name="Test Lead",
            phone="+971500000001",
            transaction_type="buy",
            budget_min=1_000_000,
            contact_consent=True,
            tenant_id="t-test",
            source="api",
            lead_id="lead-fixed-001",
        )
        r1 = create_lead(body, idempotency_key="idem-1")
        r2 = create_lead(body, idempotency_key="idem-1")
        self.assertFalse(r1["duplicate"])
        self.assertTrue(r2["duplicate"])
        self.assertEqual(r1["lead"]["status"], "qualified")

    def test_human_gate_blocks_appointment(self):
        body = LeadIn(
            full_name="Gate Test",
            phone="+971500000002",
            transaction_type="buy",
            budget_min=500_000,
            contact_consent=True,
            tenant_id="t-test",
            source="web_form",
        )
        r = create_lead(body)
        lid = r["lead"]["lead_id"]
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            book_appointment(
                AppointmentIn(
                    lead_id=lid,
                    tenant_id="t-test",
                    scheduled_at="2026-10-01T10:00:00Z",
                    human_approved=False,
                )
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_full_funnel_and_metrics(self):
        body = LeadIn(
            full_name="Funnel Lead",
            phone="+971500000003",
            email="funnel@example.ae",
            transaction_type="buy",
            budget_min=2_000_000,
            contact_consent=True,
            tenant_id="t-funnel",
            source="telegram",
            cohort="ai_assisted",
        )
        r = create_lead(body)
        lid = r["lead"]["lead_id"]
        book_appointment(
            AppointmentIn(
                lead_id=lid,
                tenant_id="t-funnel",
                scheduled_at="2026-10-02T12:00:00Z",
                human_approved=True,
            )
        )
        d = upsert_deal(
            DealIn(
                lead_id=lid,
                tenant_id="t-funnel",
                value=2_500_000,
                status="won",
                ai_assisted=True,
                human_approved=True,
            )
        )
        record_commission(
            CommissionIn(
                deal_id=d["deal"]["deal_id"],
                tenant_id="t-funnel",
                amount=50_000,
                status="paid",
            )
        )
        m = db.fetch_metrics("t-funnel")
        self.assertGreaterEqual(m["commission_total"], 50_000)
        self.assertIn("lead.received", m["funnel_event_counts"])
        self.assertIn("revenue.attributed", m["funnel_event_counts"])
        self.assertIn("ai_assisted", m["deals_by_cohort"])


if __name__ == "__main__":
    unittest.main()
