from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Inspiration:
    id: int
    text: str
    source_type: str
    source_ref: str | None
    status: str
    attempts: int


@dataclass(frozen=True)
class Production:
    id: int
    inspiration_id: int
    title: str
    payload: dict[str, Any]
    created_at: str


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterable[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS inspirations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_inspirations_status_id
                    ON inspirations(status, id);

                CREATE TABLE IF NOT EXISTS productions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inspiration_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(inspiration_id) REFERENCES inspirations(id)
                );

                CREATE TABLE IF NOT EXISTS run_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    processed INTEGER NOT NULL,
                    succeeded INTEGER NOT NULL,
                    failed INTEGER NOT NULL
                );
                """
            )

    def add_inspiration(
        self, text: str, source_type: str = "manual", source_ref: str | None = None
    ) -> int:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Inspiration text cannot be empty.")
        now = utc_now()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO inspirations(text, source_type, source_ref, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (clean_text, source_type, source_ref, now, now),
            )
            return int(cursor.lastrowid)

    def add_inspirations(self, rows: Iterable[dict[str, Any]]) -> int:
        count = 0
        for row in rows:
            self.add_inspiration(
                text=str(row["text"]),
                source_type=str(row.get("source_type", "file")),
                source_ref=row.get("source_ref"),
            )
            count += 1
        return count

    def claim_pending(self, limit: int) -> list[Inspiration]:
        now = utc_now()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, text, source_type, source_ref, status, attempts
                FROM inspirations
                WHERE status = 'pending'
                ORDER BY id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                conn.execute(
                    f"""
                    UPDATE inspirations
                    SET status = 'processing', attempts = attempts + 1, updated_at = ?
                    WHERE id IN ({placeholders})
                    """,
                    (now, *ids),
                )
            return [
                Inspiration(
                    id=row["id"],
                    text=row["text"],
                    source_type=row["source_type"],
                    source_ref=row["source_ref"],
                    status=row["status"],
                    attempts=row["attempts"],
                )
                for row in rows
            ]

    def complete(self, inspiration_id: int, payload: dict[str, Any]) -> int:
        now = utc_now()
        title = str(payload["title"])
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO productions(inspiration_id, title, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (inspiration_id, title, json.dumps(payload, ensure_ascii=False), now),
            )
            conn.execute(
                """
                UPDATE inspirations
                SET status = 'completed', last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, inspiration_id),
            )
            return int(cursor.lastrowid)

    def fail(self, inspiration_id: int, error: str) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE inspirations
                SET status = 'failed', last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (error[:2000], now, inspiration_id),
            )

    def log_run(self, started_at: str, processed: int, succeeded: int, failed: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO run_log(started_at, finished_at, processed, succeeded, failed)
                VALUES (?, ?, ?, ?, ?)
                """,
                (started_at, utc_now(), processed, succeeded, failed),
            )

    def list_productions(self, limit: int) -> list[Production]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, inspiration_id, title, payload_json, created_at
                FROM productions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                Production(
                    id=row["id"],
                    inspiration_id=row["inspiration_id"],
                    title=row["title"],
                    payload=json.loads(row["payload_json"]),
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def get_production(self, production_id: int) -> Production:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, inspiration_id, title, payload_json, created_at
                FROM productions
                WHERE id = ?
                """,
                (production_id,),
            ).fetchone()
            if row is None:
                raise LookupError(f"Production {production_id} was not found.")
            return Production(
                id=row["id"],
                inspiration_id=row["inspiration_id"],
                title=row["title"],
                payload=json.loads(row["payload_json"]),
                created_at=row["created_at"],
            )


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")

