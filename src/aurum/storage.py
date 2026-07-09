"""SQLite persistence for reports, evidence, and immutable audit events."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from .models import AnalysisReport
from .retrieval import Document


class Repository:
    def __init__(self, path: str | Path = "data/aurum.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, target TEXT NOT NULL,
                    payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, origin TEXT NOT NULL,
                    published_at TEXT NOT NULL, text TEXT NOT NULL,
                    confidence TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'unknown',
                    entities TEXT NOT NULL DEFAULT '[]', UNIQUE(origin, published_at, text)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
                    event_type TEXT NOT NULL, run_id TEXT, details TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
                );
                """
            )
            columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(evidence)").fetchall()
            }
            if "source_type" not in columns:
                self._connection.execute(
                    "ALTER TABLE evidence ADD COLUMN source_type TEXT NOT NULL DEFAULT 'unknown'"
                )
            if "entities" not in columns:
                self._connection.execute(
                    "ALTER TABLE evidence ADD COLUMN entities TEXT NOT NULL DEFAULT '[]'"
                )

    def save_report(self, report: AnalysisReport) -> str:
        from .model_risk import enforce_report_controls, hash_retrieval_evidence

        enforce_report_controls(report)
        payload = report.model_dump_json()
        digest = hashlib.sha256(payload.encode()).hexdigest()
        run_id = report.audit.run_id or digest[:16]
        details = {
            "input_hash": report.audit.input_hash,
            "output_hash": digest,
            "dataset_hash": report.metadata.get("dataset_hash", ""),
            "feature_hash": report.metadata.get("feature_hash", ""),
            "model_hash": report.metadata.get("model_hash", ""),
            "evidence_hash": hash_retrieval_evidence(report),
            "model_version": report.audit.model_version,
            "forecast_timestamp": report.audit.forecast_start.isoformat(),
            "inference_parameters": report.metadata.get("inference_parameters", {}),
            "user_query_hash": report.metadata.get("user_query_hash", ""),
        }
        with self._lock, self._connection:
            self.append_audit("report.authorized", details, run_id)
            self._connection.execute(
                "INSERT OR REPLACE INTO reports VALUES (?, ?, ?, ?, ?)",
                (run_id, datetime.now(UTC).isoformat(), report.forecast.target, payload, digest),
            )
        return run_id

    def get_report(self, run_id: str) -> AnalysisReport | None:
        row = self._connection.execute(
            "SELECT payload FROM reports WHERE run_id = ?", (run_id,)
        ).fetchone()
        return AnalysisReport.model_validate_json(row["payload"]) if row else None

    def list_reports(self, limit: int = 50) -> list[dict[str, str]]:
        rows = self._connection.execute(
            "SELECT run_id, created_at, target, payload_sha256 FROM reports "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def add_document(self, document: Document) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO evidence"
                "(origin,published_at,text,confidence,source_type,entities) VALUES(?,?,?,?,?,?)",
                (
                    document.origin,
                    document.published_at.isoformat(),
                    document.text,
                    document.source_confidence.value,
                    document.source_type,
                    json.dumps(document.entities),
                ),
            )

    def load_documents(self) -> list[Document]:
        rows = self._connection.execute(
            "SELECT origin,published_at,text,confidence,source_type,entities FROM evidence"
        ).fetchall()
        return [
            Document(
                origin=row["origin"],
                published_at=datetime.fromisoformat(row["published_at"]),
                text=row["text"],
                source_confidence=row["confidence"],
                source_type=row["source_type"],
                entities=json.loads(row["entities"]),
            )
            for row in rows
        ]

    def append_audit(
        self, event_type: str, details: dict[str, Any], run_id: str | None = None
    ) -> str:
        with self._lock, self._connection:
            previous = self._connection.execute(
                "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            previous_hash = previous["event_hash"] if previous else "GENESIS"
            occurred_at = datetime.now(UTC).isoformat()
            serialized = json.dumps(details, sort_keys=True, default=str)
            event_hash = hashlib.sha256(
                f"{previous_hash}|{occurred_at}|{event_type}|{run_id}|{serialized}".encode()
            ).hexdigest()
            self._connection.execute(
                "INSERT INTO audit_events VALUES(NULL,?,?,?,?,?,?)",
                (occurred_at, event_type, run_id, serialized, previous_hash, event_hash),
            )
        return event_hash

    def verify_audit_chain(self) -> bool:
        previous_hash = "GENESIS"
        rows = self._connection.execute("SELECT * FROM audit_events ORDER BY id").fetchall()
        for row in rows:
            expected = hashlib.sha256(
                (
                    f"{previous_hash}|{row['occurred_at']}|{row['event_type']}|"
                    f"{row['run_id']}|{row['details']}"
                ).encode()
            ).hexdigest()
            if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
                return False
            previous_hash = row["event_hash"]
        return True
