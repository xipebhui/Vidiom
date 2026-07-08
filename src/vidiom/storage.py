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

                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inspiration_id INTEGER NOT NULL,
                    seed_text TEXT NOT NULL,
                    brief_json TEXT,
                    title TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(inspiration_id) REFERENCES inspirations(id)
                );

                CREATE INDEX IF NOT EXISTS idx_projects_status_id
                    ON projects(status, id);

                CREATE TABLE IF NOT EXISTS canvas_nodes (
                    project_id INTEGER NOT NULL,
                    node_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    x INTEGER NOT NULL,
                    y INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    output_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, node_key),
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS canvas_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    source_key TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                """
            )
            project_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()
            }
            if "brief_json" not in project_columns:
                conn.execute("ALTER TABLE projects ADD COLUMN brief_json TEXT")

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

    def create_project(self, seed_text: str, brief: dict[str, Any] | None = None) -> int:
        inspiration_id = self.add_inspiration(seed_text, source_type="studio", source_ref=None)
        now = utc_now()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO projects(
                    inspiration_id, seed_text, brief_json, status, created_at, updated_at
                )
                VALUES (?, ?, ?, 'draft', ?, ?)
                """,
                (inspiration_id, seed_text.strip(), _json_or_none(brief), now, now),
            )
            return int(cursor.lastrowid)

    def create_canvas_node(
        self,
        project_id: int,
        node_key: str,
        title: str,
        kind: str,
        x: int,
        y: int,
        status: str,
        output: dict[str, Any] | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO canvas_nodes(
                    project_id, node_key, title, kind, x, y, status,
                    output_json, error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    project_id,
                    node_key,
                    title,
                    kind,
                    x,
                    y,
                    status,
                    _json_or_none(output),
                    utc_now(),
                ),
            )

    def create_canvas_edges(self, project_id: int, edges: Iterable[tuple[str, str]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO canvas_edges(project_id, source_key, target_key)
                VALUES (?, ?, ?)
                """,
                [(project_id, source, target) for source, target in edges],
            )

    def list_projects(
        self,
        limit: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if search is not None:
            clean_search = search.strip()
            if clean_search:
                conditions.append("(seed_text LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\')")
                pattern = _like_pattern(clean_search)
                params.extend([pattern, pattern])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    id, inspiration_id, seed_text, brief_json, title,
                    status, last_error, created_at, updated_at
                FROM projects
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
            return [_project_row(row) for row in rows]

    def get_project(self, project_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            project_row = conn.execute(
                """
                SELECT
                    id, inspiration_id, seed_text, brief_json, title,
                    status, last_error, created_at, updated_at
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            if project_row is None:
                raise LookupError(f"Project {project_id} was not found.")

            node_rows = conn.execute(
                """
                SELECT
                    project_id, node_key, title, kind, x, y,
                    status, output_json, error, updated_at
                FROM canvas_nodes
                WHERE project_id = ?
                ORDER BY x, y, node_key
                """,
                (project_id,),
            ).fetchall()
            edge_rows = conn.execute(
                """
                SELECT source_key, target_key
                FROM canvas_edges
                WHERE project_id = ?
                ORDER BY id
                """,
                (project_id,),
            ).fetchall()

        project = _project_row(project_row)
        project["nodes"] = [_node_row(row) for row in node_rows]
        project["edges"] = [
            {"source": row["source_key"], "target": row["target_key"]} for row in edge_rows
        ]
        return project

    def get_project_activity(self, project_id: int) -> list[dict[str, Any]]:
        project = self.get_project(project_id)
        activity = [
            {
                "type": "project",
                "title": "Project created",
                "status": "completed",
                "description": project["seed_text"],
                "occurred_at": project["created_at"],
            }
        ]
        for node in project["nodes"]:
            activity.append(
                {
                    "type": "node",
                    "title": node["title"],
                    "status": node["status"],
                    "description": _activity_description(node),
                    "occurred_at": node["updated_at"],
                }
            )
        return activity

    def export_project_package(self, project_id: int) -> dict[str, Any]:
        project = self.get_project(project_id)
        nodes = {node["key"]: node for node in project["nodes"]}
        script = nodes.get("script", {}).get("output")
        production = nodes.get("production", {}).get("output")
        if (
            project["status"] != "completed"
            or not project["title"]
            or script is None
            or production is None
        ):
            raise RuntimeError("Project is not ready to export.")

        return {
            "project": {
                "id": project["id"],
                "title": project["title"],
                "status": project["status"],
                "seed_text": project["seed_text"],
                "brief": project["brief"],
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
            },
            "deliverables": {
                "script": script,
                "production_pack": production,
            },
            "agent_outputs": {
                key: node["output"]
                for key, node in nodes.items()
                if node["output"] is not None
            },
        }

    def get_canvas_node(self, project_id: int, node_key: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    project_id, node_key, title, kind, x, y,
                    status, output_json, error, updated_at
                FROM canvas_nodes
                WHERE project_id = ? AND node_key = ?
                """,
                (project_id, node_key),
            ).fetchone()
            if row is None:
                raise LookupError(f"Node {node_key!r} was not found in project {project_id}.")
            return _node_row(row)

    def update_project_status(
        self, project_id: int, status: str, last_error: str | None = None
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE projects
                SET status = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, last_error, utc_now(), project_id),
            )

    def update_project_title(self, project_id: int, title: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE projects
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, utc_now(), project_id),
            )

    def update_draft_project(
        self,
        project_id: int,
        seed_text: str | None,
        title: str | None,
        brief: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now()
        clean_seed_text = seed_text.strip() if seed_text is not None else None
        clean_title = title.strip() if title is not None else None
        if clean_seed_text == "":
            raise ValueError("Seed text cannot be empty.")
        if clean_title == "":
            clean_title = None

        with self.connect() as conn:
            project = conn.execute(
                """
                SELECT id, inspiration_id, status, seed_text, brief_json, title
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError(f"Project {project_id} was not found.")
            if project["status"] != "draft":
                raise RuntimeError("Only draft projects can be edited.")

            next_seed_text = (
                clean_seed_text if clean_seed_text is not None else project["seed_text"]
            )
            next_title = clean_title if title is not None else project["title"]
            next_brief = brief if brief is not None else _json_from_column(project["brief_json"])
            conn.execute(
                """
                UPDATE projects
                SET seed_text = ?, brief_json = ?, title = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_seed_text, _json_or_none(next_brief), next_title, now, project_id),
            )
            conn.execute(
                """
                UPDATE inspirations
                SET text = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_seed_text, now, project["inspiration_id"]),
            )
            conn.execute(
                """
                UPDATE canvas_nodes
                SET output_json = ?, updated_at = ?
                WHERE project_id = ? AND node_key = 'seed'
                """,
                (_json_or_none(_seed_output(next_seed_text, next_brief)), now, project_id),
            )

    def update_canvas_node_status(
        self, project_id: int, node_key: str, status: str, error: str | None
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE canvas_nodes
                SET status = ?, error = ?, updated_at = ?
                WHERE project_id = ? AND node_key = ?
                """,
                (status, error, utc_now(), project_id, node_key),
            )

    def complete_canvas_node(self, project_id: int, node_key: str, output: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE canvas_nodes
                SET status = 'completed', output_json = ?, error = NULL, updated_at = ?
                WHERE project_id = ? AND node_key = ?
                """,
                (_json_or_none(output), utc_now(), project_id, node_key),
            )


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json_or_none(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False)


def _json_from_column(payload_json: str | None) -> dict[str, Any] | None:
    if not payload_json:
        return None
    return json.loads(payload_json)


def _like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _seed_output(seed_text: str, brief: dict[str, Any] | None) -> dict[str, Any]:
    output: dict[str, Any] = {"text": seed_text}
    if brief is not None:
        output["brief"] = brief
    return output


def _project_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "inspiration_id": row["inspiration_id"],
        "seed_text": row["seed_text"],
        "brief": _json_from_column(row["brief_json"]),
        "title": row["title"],
        "status": row["status"],
        "last_error": row["last_error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _node_row(row: sqlite3.Row) -> dict[str, Any]:
    output_json = row["output_json"]
    return {
        "project_id": row["project_id"],
        "key": row["node_key"],
        "title": row["title"],
        "kind": row["kind"],
        "x": row["x"],
        "y": row["y"],
        "status": row["status"],
        "output": json.loads(output_json) if output_json else None,
        "error": row["error"],
        "updated_at": row["updated_at"],
    }


def _activity_description(node: dict[str, Any]) -> str:
    if node["error"]:
        return str(node["error"])
    output = node["output"]
    if output is not None:
        return _output_summary(output)
    if node["status"] == "running":
        return "Agent is generating this step."
    return "Waiting for upstream output."


def _output_summary(output: dict[str, Any]) -> str:
    if "text" in output:
        return str(output["text"])
    if "one_sentence_pitch" in output:
        return str(output["one_sentence_pitch"])
    protagonist = output.get("protagonist")
    if isinstance(protagonist, dict) and protagonist.get("name") and protagonist.get("desire"):
        return f"{protagonist['name']} · {protagonist['desire']}"
    if "logline" in output:
        return str(output["logline"])
    if "title" in output:
        return str(output["title"])
    if "visual_style" in output:
        return str(output["visual_style"])
    return "Completed."
