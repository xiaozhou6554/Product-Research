from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.models import RunStatus


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchRepository:
    """Small SQLite adapter for local reproducibility; the schema maps cleanly to PostgreSQL."""

    def __init__(self, db_path: str | Path = "backend/.data/research.db") -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, tenant_id TEXT NOT NULL, role TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research_runs (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, created_by TEXT NOT NULL, idempotency_key TEXT, input_json TEXT NOT NULL, status TEXT NOT NULL, nodes_json TEXT NOT NULL, analysis_json TEXT, error_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
            CREATE UNIQUE INDEX IF NOT EXISTS ux_runs_tenant_idempotency ON research_runs(tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
            CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, run_id TEXT NOT NULL, source_type TEXT NOT NULL, source_version TEXT NOT NULL, marketplace TEXT NOT NULL, fetched_at TEXT NOT NULL, raw_record_hash TEXT NOT NULL, excerpt TEXT NOT NULL, confidence REAL NOT NULL, assumption INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS reports (run_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, report_json TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL);
            """)

    def seed_users(self, users: list[dict[str, str]]) -> None:
        with self.lock, self.conn:
            for user in users:
                self.conn.execute("INSERT OR IGNORE INTO users(id,email,password_hash,tenant_id,role) VALUES(?,?,?,?,?)", (user["id"], user["email"], user["password_hash"], user["tenant_id"], user["role"]))

    def user_by_email(self, email: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(row) if row else None

    def create_run(self, *, tenant_id: str, created_by: str, input_data: dict[str, Any], idempotency_key: str | None) -> dict[str, Any]:
        with self.lock, self.conn:
            if idempotency_key:
                existing = self.conn.execute("SELECT * FROM research_runs WHERE tenant_id=? AND idempotency_key=?", (tenant_id, idempotency_key)).fetchone()
                if existing:
                    return self._run_row(existing)
            run_id = f"run_{uuid.uuid4().hex[:12]}"
            nodes = {name: {"name": name, "status": "NOT_STARTED", "retry_count": 0, "payload": {}} for name in ("trend", "products", "comments", "keywords", "suppliers", "risks", "profit", "score", "evidence", "report")}
            stamp = now_iso()
            self.conn.execute("INSERT INTO research_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (run_id, tenant_id, created_by, idempotency_key, json.dumps(input_data, ensure_ascii=False), RunStatus.PENDING.value, json.dumps(nodes), None, None, stamp, stamp, 1))
            return self.get_run(run_id, tenant_id)

    def _run_row(self, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["input"] = json.loads(result.pop("input_json"))
        result["nodes"] = json.loads(result.pop("nodes_json"))
        result["analysis"] = json.loads(result.pop("analysis_json")) if result.get("analysis_json") else None
        result["error"] = json.loads(result.pop("error_json")) if result.get("error_json") else None
        return result

    def get_run(self, run_id: str, tenant_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM research_runs WHERE id=? AND tenant_id=?", (run_id, tenant_id)).fetchone()
        return self._run_row(row) if row else None

    def update_run(self, run_id: str, tenant_id: str, *, status: str | None = None, nodes: dict[str, Any] | None = None, analysis: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> None:
        current = self.get_run(run_id, tenant_id)
        if not current:
            raise KeyError("run not found")
        with self.lock, self.conn:
            self.conn.execute("UPDATE research_runs SET status=?,nodes_json=?,analysis_json=?,error_json=?,updated_at=?,version=version+1 WHERE id=? AND tenant_id=?", (status or current["status"], json.dumps(nodes if nodes is not None else current["nodes"], ensure_ascii=False), json.dumps(analysis if analysis is not None else current["analysis"], ensure_ascii=False) if (analysis is not None or current["analysis"] is not None) else None, json.dumps(error if error is not None else current["error"], ensure_ascii=False) if (error is not None or current["error"] is not None) else None, now_iso(), run_id, tenant_id))

    def save_evidence(self, run_id: str, tenant_id: str, items: list[dict[str, Any]]) -> None:
        with self.lock, self.conn:
            for item in items:
                self.conn.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?)", (f"ev_{uuid.uuid4().hex[:12]}", tenant_id, run_id, item["source_type"], item["source_version"], item["marketplace"], item["fetched_at"], item["raw_record_hash"], item["excerpt"], item["confidence"], int(item.get("assumption", False))))

    def get_evidence(self, run_id: str, tenant_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM evidence WHERE run_id=? AND tenant_id=? ORDER BY fetched_at", (run_id, tenant_id)).fetchall()
        return [dict(row) for row in rows]

    def save_report(self, run_id: str, tenant_id: str, report: dict[str, Any]) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO reports VALUES(?,?,?,?,?)", (run_id, tenant_id, json.dumps(report, ensure_ascii=False), report.get("version", 1), now_iso()))

    def get_report(self, run_id: str, tenant_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT report_json FROM reports WHERE run_id=? AND tenant_id=?", (run_id, tenant_id)).fetchone()
        return json.loads(row[0]) if row else None
