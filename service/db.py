"""
Durable store for leads, events, deals, commissions.
SQLite for local/prod-lite; swap DATABASE_URL to Postgres in production.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

_DB_PATH = Path(os.environ.get("SAHIIXX_DB", "sahiixx_revenue.db"))
_LOCK = threading.Lock()

_IDEMPOTENCY_SCHEMA = """
CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    response_json TEXT NOT NULL,
    PRIMARY KEY (tenant_id, key)
)
"""

_LEADS_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    lead_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT,
    data_json TEXT NOT NULL,
    cohort TEXT NOT NULL DEFAULT 'ai_assisted',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, lead_id)
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate_tenant_key(conn: sqlite3.Connection, table: str, key: str, schema: str) -> None:
    """Copy global-key tables into tenant-key tables, retaining the original data."""
    columns = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    primary_key = [
        column["name"]
        for column in sorted(columns, key=lambda column: column["pk"])
        if column["pk"]
    ]
    if primary_key == ["tenant_id", key]:
        return
    if primary_key != [key]:
        raise RuntimeError(f"Unexpected primary key for {table}: {primary_key}")

    # No DROP: the legacy table remains a snapshot for inspection/recovery.
    conn.execute(f'ALTER TABLE "{table}" RENAME TO "{table}_legacy_v1"')
    conn.execute(schema)
    names = ", ".join('"' + column["name"].replace('"', '""') + '"' for column in columns)
    conn.execute(
        f'INSERT INTO "{table}" ({names}) SELECT {names} FROM "{table}_legacy_v1"'
    )


def init_db() -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.executescript(
                f"""
                BEGIN IMMEDIATE;
                {_IDEMPOTENCY_SCHEMA};
                {_LEADS_SCHEMA};

                CREATE TABLE IF NOT EXISTS events (
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
                CREATE INDEX IF NOT EXISTS idx_events_corr ON events(correlation_id);
                CREATE INDEX IF NOT EXISTS idx_events_lead ON events(lead_id);
                CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

                CREATE TABLE IF NOT EXISTS appointments (
                    appointment_id TEXT PRIMARY KEY,
                    lead_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    scheduled_at TEXT,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS deals (
                    deal_id TEXT PRIMARY KEY,
                    lead_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    value REAL NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'AED',
                    ai_assisted INTEGER NOT NULL DEFAULT 1,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    closed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_deals_lead ON deals(lead_id);

                CREATE TABLE IF NOT EXISTS commissions (
                    commission_id TEXT PRIMARY KEY,
                    deal_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'AED',
                    status TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_costs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    lead_id TEXT,
                    agent_run_id TEXT,
                    model TEXT,
                    cost_usd REAL NOT NULL DEFAULT 0,
                    occurred_at TEXT NOT NULL
                );
                """
            )
            _migrate_tenant_key(conn, "idempotency", "key", _IDEMPOTENCY_SCHEMA)
            _migrate_tenant_key(conn, "leads", "lead_id", _LEADS_SCHEMA)
            # Legacy indexes retain their names on the archived table.
            conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_cohort_scoped ON leads(cohort)")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    with _LOCK:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def get_idempotent(key: str, tenant_id: str) -> Optional[dict[str, Any]]:
    with session() as conn:
        row = conn.execute(
            "SELECT response_json FROM idempotency WHERE tenant_id = ? AND key = ?",
            (tenant_id, key),
        ).fetchone()
        if row:
            return json.loads(row["response_json"])
    return None


def put_idempotent(key: str, tenant_id: str, response: dict[str, Any], created_at: str) -> None:
    with session() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO idempotency (key, tenant_id, created_at, response_json) VALUES (?,?,?,?)",
            (key, tenant_id, created_at, json.dumps(response)),
        )


def upsert_lead(lead: dict[str, Any], cohort: str = "ai_assisted") -> None:
    with session() as conn:
        conn.execute(
            """
            INSERT INTO leads (lead_id, tenant_id, status, source, data_json, cohort, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, lead_id) DO UPDATE SET
              status=excluded.status,
              data_json=excluded.data_json,
              updated_at=excluded.updated_at
            """,
            (
                lead["lead_id"],
                lead["tenant_id"],
                lead["status"],
                lead.get("source"),
                json.dumps(lead),
                cohort,
                lead.get("created_at") or lead.get("updated_at") or "",
                lead.get("updated_at") or "",
            ),
        )


def insert_event(event: dict[str, Any]) -> None:
    entities = event.get("entities") or {}
    with session() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO events
            (event_id, event_type, tenant_id, correlation_id, causation_id, idempotency_key, lead_id, data_json, occurred_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                event["event_id"],
                event["event_type"],
                event["tenant_id"],
                event.get("correlation_id"),
                event.get("causation_id"),
                event.get("idempotency_key"),
                entities.get("lead_id"),
                json.dumps(event),
                event.get("occurred_at") or "",
            ),
        )


def insert_deal(deal: dict[str, Any]) -> None:
    with session() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO deals
            (deal_id, lead_id, tenant_id, status, value, currency, ai_assisted, data_json, created_at, closed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                deal["deal_id"],
                deal["lead_id"],
                deal["tenant_id"],
                deal["status"],
                float(deal.get("value") or 0),
                deal.get("currency") or "AED",
                1 if deal.get("ai_assisted", True) else 0,
                json.dumps(deal),
                deal.get("created_at") or "",
                deal.get("closed_at"),
            ),
        )


def insert_commission(c: dict[str, Any]) -> None:
    with session() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO commissions
            (commission_id, deal_id, tenant_id, amount, currency, status, data_json, recorded_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                c["commission_id"],
                c["deal_id"],
                c["tenant_id"],
                float(c["amount"]),
                c.get("currency") or "AED",
                c["status"],
                json.dumps(c),
                c.get("recorded_at") or "",
            ),
        )


def record_cost(
    tenant_id: str,
    cost_usd: float,
    *,
    lead_id: Optional[str] = None,
    agent_run_id: Optional[str] = None,
    model: Optional[str] = None,
    occurred_at: str = "",
) -> None:
    with session() as conn:
        conn.execute(
            """
            INSERT INTO agent_costs (tenant_id, lead_id, agent_run_id, model, cost_usd, occurred_at)
            VALUES (?,?,?,?,?,?)
            """,
            (tenant_id, lead_id, agent_run_id, model, float(cost_usd), occurred_at),
        )


def fetch_metrics(tenant_id: Optional[str] = None) -> dict[str, Any]:
    """Cohort-level revenue proof metrics."""
    with session() as conn:
        where = "WHERE tenant_id = ?" if tenant_id else ""
        params: tuple = (tenant_id,) if tenant_id else ()

        leads = conn.execute(
            f"SELECT cohort, status, COUNT(*) AS n FROM leads {where} GROUP BY cohort, status",
            params,
        ).fetchall()

        deals = conn.execute(
            f"""
            SELECT
              CASE WHEN ai_assisted=1 THEN 'ai_assisted' ELSE 'human_only' END AS cohort,
              status,
              COUNT(*) AS n,
              COALESCE(SUM(value),0) AS revenue
            FROM deals {where}
            GROUP BY ai_assisted, status
            """,
            params,
        ).fetchall()

        if tenant_id:
            commissions = conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM commissions WHERE tenant_id = ? AND status IN ('approved','paid')",
                params,
            ).fetchone()
            costs = conn.execute(
                "SELECT COALESCE(SUM(cost_usd),0) AS total FROM agent_costs WHERE tenant_id = ?",
                params,
            ).fetchone()
            funnel = conn.execute(
                "SELECT event_type, COUNT(*) AS n FROM events WHERE tenant_id = ? GROUP BY event_type",
                params,
            ).fetchall()
        else:
            commissions = conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM commissions WHERE status IN ('approved','paid')"
            ).fetchone()
            costs = conn.execute(
                "SELECT COALESCE(SUM(cost_usd),0) AS total FROM agent_costs"
            ).fetchone()
            funnel = conn.execute(
                "SELECT event_type, COUNT(*) AS n FROM events GROUP BY event_type"
            ).fetchall()

    by_cohort: dict[str, dict[str, int]] = {}
    for row in leads:
        by_cohort.setdefault(row["cohort"], {})[row["status"]] = row["n"]

    deal_by_cohort: dict[str, dict[str, Any]] = {}
    for row in deals:
        c = row["cohort"]
        deal_by_cohort.setdefault(c, {"count": 0, "revenue": 0.0, "by_status": {}})
        deal_by_cohort[c]["count"] += row["n"]
        deal_by_cohort[c]["revenue"] += float(row["revenue"])
        deal_by_cohort[c]["by_status"][row["status"]] = {
            "n": row["n"],
            "revenue": float(row["revenue"]),
        }

    total_leads = sum(sum(s.values()) for s in by_cohort.values()) or 1
    total_cost = float(costs["total"] if costs else 0)
    total_commission = float(commissions["total"] if commissions else 0)

    return {
        "leads_by_cohort_status": by_cohort,
        "deals_by_cohort": deal_by_cohort,
        "commission_total": total_commission,
        "agent_cost_usd": total_cost,
        "revenue_per_lead": round(total_commission / total_leads, 4) if total_leads else 0,
        "cost_per_lead": round(total_cost / total_leads, 6) if total_leads else 0,
        "roi": round((total_commission - total_cost) / total_cost, 4) if total_cost > 0 else None,
        "funnel_event_counts": {r["event_type"]: r["n"] for r in funnel},
    }
