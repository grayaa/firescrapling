import sqlite3
import os
import uuid
import json
from datetime import datetime

DB_DIR = "apps/firescrapling/backend/data/db"
DB_PATH = os.path.join(DB_DIR, "app.db")

def _get_db():
    """Open a connection with recommended settings."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    """Initialize the database schema."""
    conn = _get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                markdown TEXT,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
    finally:
        conn.close()

def create_job(job_id: str, job_type: str, url: str):
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO jobs (id, type, url, status) VALUES (?, ?, ?, ?)",
            (job_id, job_type, url, "pending")
        )
        conn.commit()
    finally:
        conn.close()

def update_job_status(job_id: str, status: str, finished: bool = False):
    conn = _get_db()
    try:
        if finished:
            conn.execute(
                "UPDATE jobs SET status = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, job_id)
            )
        else:
            conn.execute(
                "UPDATE jobs SET status = ? WHERE id = ?",
                (status, job_id)
            )
        conn.commit()
    finally:
        conn.close()

def add_result(job_id: str, url: str, title: str, markdown: str, metadata: dict):
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO results (job_id, url, title, markdown, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (job_id, url, title, markdown, json.dumps(metadata))
        )
        conn.commit()
    finally:
        conn.close()

def get_jobs(limit: int = 50):
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_results_for_job(job_id: str):
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM results WHERE job_id = ? ORDER BY created_at ASC",
            (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def delete_job_record(job_id: str):
    conn = _get_db()
    try:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        return True
    finally:
        conn.close()
