"""Offline API/storage regressions, each using a disposable SQLite database."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import app as service_app  # noqa: E402
import db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

LEGACY_SCHEMA = """
CREATE TABLE idempotency (
    key TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    response_json TEXT NOT NULL
);
CREATE TABLE leads (
    lead_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT,
    data_json TEXT NOT NULL,
    cohort TEXT NOT NULL DEFAULT 'ai_assisted',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_leads_tenant ON leads(tenant_id);
CREATE INDEX idx_leads_cohort ON leads(cohort);
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    correlation_id TEXT,
    causation_id TEXT,
    idempotency_key TEXT,
    lead_id TEXT,
    data_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE TABLE agent_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    lead_id TEXT,
    agent_run_id TEXT,
    model TEXT,
    cost_usd REAL NOT NULL DEFAULT 0,
    occurred_at TEXT NOT NULL
);
"""


class IsolatedDatabaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tenant-isolation-")
        self.addCleanup(temporary.cleanup)
        self.enterContext(patch.object(db, "_DB_PATH", Path(temporary.name) / "revenue.db"))
        self.enterContext(
            patch.object(service_app, "resolve_for_event", return_value={"model": "stub/deterministic"})
        )

    def snapshot(self):
        with db.session() as conn:
            return {
                table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                for table in ("leads", "idempotency", "events", "agent_costs")
            }


class TenantIsolationTests(IsolatedDatabaseTests):
    def setUp(self):
        super().setUp()
        self.client = self.enterContext(TestClient(service_app.app))

    def post_lead(self, tenant_id, *, key=None, lead_id=None, name="Private name", cohort="ai_assisted"):
        headers = {"X-Tenant-Id": tenant_id}
        if key is not None:
            headers["Idempotency-Key"] = key
        body = {"full_name": name, "phone": "+971500000001", "cohort": cohort}
        if lead_id is not None:
            body["lead_id"] = lead_id
        response = self.client.post("/v1/leads", headers=headers, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def assert_single_ingest(self, tenant_id, cohort="ai_assisted"):
        metrics = db.fetch_metrics(tenant_id)
        self.assertEqual(metrics["leads_by_cohort_status"], {cohort: {"qualified": 1}})
        self.assertEqual(metrics["funnel_event_counts"], {"lead.received": 1, "lead.qualified": 1})
        self.assertEqual(metrics["agent_cost_usd"], 0.001)
        with db.session() as conn:
            for table, expected in (("leads", 1), ("idempotency", 1), ("events", 2), ("agent_costs", 1)):
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE tenant_id = ?", (tenant_id,)
                ).fetchone()[0]
                self.assertEqual(count, expected, (tenant_id, table))

    def test_shared_key_replays_only_own_response_without_extra_events_or_costs(self):
        originals = {}
        for tenant in ("tenant-a", "tenant-b"):
            result = self.post_lead(tenant, key="shared-key", name=f"{tenant} private name")
            self.assertFalse(result["duplicate"])
            self.assertEqual(result["lead"]["tenant_id"], tenant)
            self.assertEqual(result["lead"]["contact"]["full_name"], f"{tenant} private name")
            self.assertTrue(all(event["tenant_id"] == tenant for event in result["events"]))
            originals[tenant] = result
        self.assertNotEqual(originals["tenant-a"]["lead"]["lead_id"], originals["tenant-b"]["lead"]["lead_id"])
        before = self.snapshot()
        for tenant in ("tenant-a", "tenant-b", "tenant-a", "tenant-b"):
            with self.subTest(tenant=tenant):
                replay = self.post_lead(tenant, key="shared-key", name="Changed retry payload")
                self.assertEqual(replay, {**originals[tenant], "duplicate": True})
                self.assertEqual(self.snapshot(), before)
                self.assert_single_ingest(tenant)

    def test_shared_explicit_lead_id_does_not_overwrite_other_tenant(self):
        original_a = self.post_lead("tenant-a", key="key-a", lead_id="shared-id", name="A original")
        original_b = self.post_lead(
            "tenant-b", key="key-b", lead_id="shared-id", name="B original", cohort="human_only"
        )
        with db.session() as conn:
            rows = conn.execute("SELECT tenant_id, data_json, cohort FROM leads ORDER BY tenant_id").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(json.loads(rows[0]["data_json"]), original_a["lead"])
        self.assertEqual(json.loads(rows[1]["data_json"]), original_b["lead"])
        self.assertEqual(original_a["lead"]["lead_id"], "shared-id")
        self.assertEqual(original_b["lead"]["lead_id"], "shared-id")
        self.assert_single_ingest("tenant-a")
        self.assert_single_ingest("tenant-b", "human_only")

        updated_b = self.post_lead("tenant-b", key="key-b-update", lead_id="shared-id", name="B updated")
        with db.session() as conn:
            rows = conn.execute("SELECT tenant_id, data_json, cohort FROM leads ORDER BY tenant_id").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(json.loads(rows[0]["data_json"]), original_a["lead"])
        self.assertEqual(json.loads(rows[1]["data_json"]), updated_b["lead"])
        self.assertEqual(rows[1]["cohort"], "human_only")
        before = self.snapshot()
        self.assertEqual(
            self.post_lead("tenant-a", key="key-a", lead_id="shared-id"),
            {**original_a, "duplicate": True},
        )
        self.assertEqual(
            self.post_lead("tenant-b", key="key-b-update", lead_id="shared-id"),
            {**updated_b, "duplicate": True},
        )
        self.assertEqual(self.snapshot(), before)

    def test_default_keys_are_tenant_scoped_even_with_delimiter_collisions(self):
        cases = (("tenant-a", "shared-id"), ("tenant-b", "shared-id"), ("tenant:c", "id"), ("tenant", "c:id"))
        originals = {}
        for tenant, lead_id in cases:
            result = self.post_lead(tenant, lead_id=lead_id, name=tenant)
            self.assertFalse(result["duplicate"])
            self.assertEqual(result["lead"]["tenant_id"], tenant)
            self.assertEqual(result["lead"]["lead_id"], lead_id)
            originals[tenant] = result
        before = self.snapshot()
        for tenant, lead_id in cases:
            self.assertEqual(
                self.post_lead(tenant, lead_id=lead_id, name="Changed retry"),
                {**originals[tenant], "duplicate": True},
            )
            self.assert_single_ingest(tenant)
        self.assertEqual(self.snapshot(), before)

    def test_cache_uses_effective_body_header_or_default_tenant(self):
        cases = (
            ({"tenant_id": "body-tenant"}, {"X-Tenant-Id": "ignored-header"}, "body-tenant"),
            ({}, {"X-Tenant-Id": "header-tenant"}, "header-tenant"),
            ({}, {}, "default-tenant"),
        )
        originals = []
        for body, headers, tenant in cases:
            headers = {**headers, "Idempotency-Key": "same-key"}
            result = self.client.post("/v1/leads", headers=headers, json=body)
            self.assertEqual(result.status_code, 200)
            self.assertFalse(result.json()["duplicate"])
            self.assertEqual(result.json()["lead"]["tenant_id"], tenant)
            originals.append(result.json())
        before = self.snapshot()
        for (body, headers, _), original in zip(cases, originals):
            replay = self.client.post("/v1/leads", headers={**headers, "Idempotency-Key": "same-key"}, json=body)
            self.assertEqual(replay.json(), {**original, "duplicate": True})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(db.fetch_metrics("ignored-header")["leads_by_cohort_status"], {})


class TenantMigrationTests(IsolatedDatabaseTests):
    def seed_legacy(self):
        with db.session() as conn:
            conn.executescript(LEGACY_SCHEMA)
        lead = service_app.normalize_lead(
            {"lead_id": "legacy-lead", "full_name": "Legacy private name", "phone": "+971500000002"},
            tenant_id="legacy-tenant",
        )
        lead.update(status="qualified", created_at="2026-09-01T00:00:00Z", updated_at="2026-09-02T00:00:00Z")
        event = service_app.lead_received(
            lead, tenant_id="legacy-tenant", source_channel="api", idempotency_key="legacy-key"
        )
        response = {"lead": lead, "events": [event], "duplicate": False, "model": "stub/deterministic"}
        with db.session() as conn:
            conn.execute(
                "INSERT INTO leads VALUES (?,?,?,?,?,?,?,?)",
                (lead["lead_id"], lead["tenant_id"], lead["status"], lead["source"], json.dumps(lead),
                 "human_only", lead["created_at"], lead["updated_at"]),
            )
            conn.execute(
                "INSERT INTO idempotency VALUES (?,?,?,?)",
                ("legacy-key", "legacy-tenant", lead["created_at"], json.dumps(response)),
            )
        db.insert_event(event)
        db.record_cost("legacy-tenant", 0.02, lead_id="legacy-lead", occurred_at=lead["created_at"])
        return response

    def test_migration_preserves_rows_and_legacy_replay_then_allows_other_tenant(self):
        original = self.seed_legacy()
        before = self.snapshot()
        with TestClient(service_app.app) as client:
            self.assertEqual(self.snapshot(), before)
            with db.session() as conn:
                for table, key in (("idempotency", "key"), ("leads", "lead_id")):
                    info = conn.execute(f"PRAGMA table_info({table})").fetchall()
                    primary_key = [row["name"] for row in sorted(info, key=lambda row: row["pk"]) if row["pk"]]
                    self.assertEqual(primary_key, ["tenant_id", key])
                    backup = [tuple(row) for row in conn.execute(f"SELECT * FROM {table}_legacy_v1 ORDER BY rowid")]
                    self.assertEqual(backup, before[table])
                indexes = conn.execute("PRAGMA index_list(leads)").fetchall()
                self.assertIn("idx_leads_cohort_scoped", [row["name"] for row in indexes])

            replay = client.post(
                "/v1/leads",
                headers={"X-Tenant-Id": "legacy-tenant", "Idempotency-Key": "legacy-key"},
                json={"full_name": "Changed retry payload"},
            )
            self.assertEqual(replay.status_code, 200)
            self.assertEqual(replay.json(), {**original, "duplicate": True})
            self.assertEqual(self.snapshot(), before)

            other = client.post(
                "/v1/leads",
                headers={"X-Tenant-Id": "new-tenant", "Idempotency-Key": "legacy-key"},
                json={"lead_id": "legacy-lead", "full_name": "New tenant", "phone": "+971500000003"},
            )
            self.assertEqual(other.status_code, 200)
            self.assertFalse(other.json()["duplicate"])
            self.assertEqual(other.json()["lead"]["tenant_id"], "new-tenant")
            self.assertEqual(db.get_idempotent("legacy-key", "legacy-tenant"), original)
            self.assertEqual(db.get_idempotent("legacy-key", "new-tenant"), other.json())
            self.assertEqual(db.fetch_metrics("legacy-tenant")["agent_cost_usd"], 0.02)
            self.assertEqual(db.fetch_metrics("new-tenant")["agent_cost_usd"], 0.001)
            with db.session() as conn:
                legacy_row = conn.execute(
                    "SELECT * FROM leads WHERE tenant_id = ? AND lead_id = ?", ("legacy-tenant", "legacy-lead")
                ).fetchone()
                self.assertEqual(tuple(legacy_row), before["leads"][0])

        after = self.snapshot()
        db.init_db()
        self.assertEqual(self.snapshot(), after)
        with db.session() as conn:
            for table in ("idempotency", "leads"):
                self.assertEqual(
                    [tuple(row) for row in conn.execute(f"SELECT * FROM {table}_legacy_v1 ORDER BY rowid")],
                    before[table],
                )
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_migration_failure_rolls_back_both_tables_and_keeps_original_data(self):
        self.seed_legacy()
        with db.session() as conn:
            # A real SQLite rename failure after the first table has been migrated.
            conn.execute("CREATE TABLE leads_legacy_v1 (sentinel TEXT)")
            conn.execute("INSERT INTO leads_legacy_v1 VALUES ('keep me')")
            names_before = [row[0] for row in conn.execute("SELECT name FROM sqlite_master ORDER BY name")]
        before = self.snapshot()
        with self.assertRaises(sqlite3.OperationalError):
            db.init_db()
        self.assertEqual(self.snapshot(), before)
        with db.session() as conn:
            self.assertEqual(
                [row[0] for row in conn.execute("SELECT name FROM sqlite_master ORDER BY name")], names_before
            )
            self.assertEqual(conn.execute("SELECT sentinel FROM leads_legacy_v1").fetchone()[0], "keep me")
            for table, key in (("idempotency", "key"), ("leads", "lead_id")):
                self.assertEqual(
                    [row["name"] for row in conn.execute(f"PRAGMA table_info({table})") if row["pk"]], [key]
                )


if __name__ == "__main__":
    unittest.main()
