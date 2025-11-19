# TODO: implement src/sandbox/core/db.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

class DB:
    def __init__(self, path: Path):
        self.path = path
        self._ensure_schema()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _ensure_schema(self):
        with self._connect() as conn:
            c = conn.cursor()
            c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                lang TEXT NOT NULL,
                status TEXT NOT NULL,
                exit_code INTEGER,
                reason TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                entry TEXT NOT NULL
            )""")
            c.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                job_id TEXT PRIMARY KEY,
                stdout_path TEXT,
                stderr_path TEXT,
                meta_path TEXT
            )""")
            c.execute("""
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                event TEXT,
                payload TEXT,
                ts TEXT NOT NULL
            )""")
            conn.commit()

    def insert_job(self, job_id: str, lang: str, entry: str):
        ts = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs(id, lang, status, created_at, entry) VALUES(?,?,?,?,?)",
                (job_id, lang, "QUEUED", ts, entry),
            )
            conn.commit()

    def set_running(self, job_id: str):
        ts = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute("UPDATE jobs SET status=?, started_at=? WHERE id=?",
                         ("RUNNING", ts, job_id))
            conn.commit()

    def finalize(self, job_id: str, status: str, rc: int, reason: str | None):
        ts = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status=?, exit_code=?, reason=?, finished_at=? WHERE id=?",
                (status, rc, reason, ts, job_id),
            )
            conn.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def upsert_artifacts(self, job_id: str, stdout_path: str, stderr_path: str, meta_path: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO artifacts(job_id,stdout_path,stderr_path,meta_path) VALUES(?,?,?,?) "
                "ON CONFLICT(job_id) DO UPDATE SET stdout_path=excluded.stdout_path, "
                "stderr_path=excluded.stderr_path, meta_path=excluded.meta_path",
                (job_id, stdout_path, stderr_path, meta_path),
            )
            conn.commit()

    def get_artifacts(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM artifacts WHERE job_id=?", (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def audit(self, job_id: str, event: str, payload: str = ""):
        ts = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit(job_id,event,payload,ts) VALUES(?,?,?,?)",
                (job_id, event, payload, ts),
            )
            conn.commit()
