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
                    review_notes_json TEXT,
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

                CREATE TABLE IF NOT EXISTS project_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    description TEXT NOT NULL,
                    details_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );

                CREATE INDEX IF NOT EXISTS idx_project_events_project_id
                    ON project_events(project_id, id);
                """
            )
            project_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()
            }
            if "brief_json" not in project_columns:
                conn.execute("ALTER TABLE projects ADD COLUMN brief_json TEXT")
            if "review_notes_json" not in project_columns:
                conn.execute("ALTER TABLE projects ADD COLUMN review_notes_json TEXT")

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
            conditions.append("p.status = ?")
            params.append(status)
        if search is not None:
            clean_search = search.strip()
            if clean_search:
                conditions.append("(p.seed_text LIKE ? ESCAPE '\\' OR p.title LIKE ? ESCAPE '\\')")
                pattern = _like_pattern(clean_search)
                params.extend([pattern, pattern])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    p.id, p.inspiration_id, p.seed_text, p.brief_json, p.title,
                    p.review_notes_json, p.status, p.last_error, p.created_at, p.updated_at,
                    COALESCE(SUM(CASE WHEN n.kind = 'agent' THEN 1 ELSE 0 END), 0)
                        AS progress_total,
                    COALESCE(SUM(
                        CASE WHEN n.kind = 'agent' AND n.status = 'completed' THEN 1 ELSE 0 END
                    ), 0) AS progress_completed,
                    MAX(CASE WHEN n.kind = 'agent' AND n.status = 'running' THEN n.node_key END)
                        AS active_key,
                    MAX(CASE WHEN n.kind = 'agent' AND n.status = 'running' THEN n.title END)
                        AS active_title,
                    MAX(CASE WHEN n.kind = 'agent' AND n.status = 'failed' THEN n.node_key END)
                        AS failed_key,
                    MAX(CASE WHEN n.kind = 'agent' AND n.status = 'failed' THEN n.title END)
                        AS failed_title
                FROM projects p
                LEFT JOIN canvas_nodes n ON n.project_id = p.id
                {where_clause}
                GROUP BY p.id
                ORDER BY p.id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
            return [_project_row(row, include_progress=True) for row in rows]

    def get_project(self, project_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            project_row = conn.execute(
                """
                SELECT
                    id, inspiration_id, seed_text, brief_json, title,
                    review_notes_json, status, last_error, created_at, updated_at
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
        with self.connect() as conn:
            event_rows = conn.execute(
                """
                SELECT event_type, title, status, description, details_json, created_at
                FROM project_events
                WHERE project_id = ?
                ORDER BY id
                """,
                (project_id,),
            ).fetchall()
        for row in event_rows:
            activity.append(
                {
                    "type": row["event_type"],
                    "title": row["title"],
                    "status": row["status"],
                    "description": row["description"],
                    "details": _json_from_column(row["details_json"]),
                    "occurred_at": row["created_at"],
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
                "review_notes": project["review_notes"],
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
            },
            "deliverables": {
                "script": script,
                "production_pack": production,
                "review_notes": project["review_notes"],
            },
            "agent_outputs": {
                key: node["output"]
                for key, node in nodes.items()
                if node["output"] is not None
            },
            "activity": self.get_project_activity(project_id),
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
        now = utc_now()
        with self.connect() as conn:
            project = conn.execute(
                """
                SELECT id, status
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError(f"Project {project_id} was not found.")

            conn.execute(
                """
                UPDATE projects
                SET status = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, last_error, now, project_id),
            )
            if project["status"] != status:
                event = _status_event(project["status"], status, last_error)
                _insert_project_event(
                    conn=conn,
                    project_id=project_id,
                    event_type="status_change",
                    title=event["title"],
                    status=status,
                    description=event["description"],
                    details=event["details"],
                    created_at=now,
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
            current_brief = _json_from_column(project["brief_json"])
            next_brief = brief if brief is not None else current_brief
            seed_changed = (
                clean_seed_text is not None and clean_seed_text != project["seed_text"]
            )
            brief_changed = brief is not None and brief != current_brief
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
            if seed_changed or brief_changed:
                conn.execute(
                    """
                    UPDATE canvas_nodes
                    SET status = 'pending', output_json = NULL, error = NULL, updated_at = ?
                    WHERE project_id = ? AND kind = 'agent'
                    """,
                    (now, project_id),
                )

    def reset_failed_project(self, project_id: int) -> None:
        now = utc_now()
        with self.connect() as conn:
            project = conn.execute(
                """
                SELECT id, status
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError(f"Project {project_id} was not found.")
            if project["status"] != "failed":
                raise RuntimeError("Only failed projects can be reset.")

            conn.execute(
                """
                UPDATE projects
                SET status = 'draft', last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, project_id),
            )
            conn.execute(
                """
                UPDATE canvas_nodes
                SET status = 'pending', output_json = NULL, error = NULL, updated_at = ?
                WHERE project_id = ?
                  AND kind = 'agent'
                  AND status != 'completed'
                """,
                (now, project_id),
            )
            event = _status_event(project["status"], "draft", None)
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="status_change",
                title=event["title"],
                status="draft",
                description=event["description"],
                details=event["details"],
                created_at=now,
            )

    def pause_running_project(self, project_id: int) -> None:
        now = utc_now()
        with self.connect() as conn:
            project = conn.execute(
                """
                SELECT id, status
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError(f"Project {project_id} was not found.")
            if project["status"] != "running":
                raise RuntimeError("Only running projects can be paused.")

            conn.execute(
                """
                UPDATE projects
                SET status = 'paused', last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, project_id),
            )
            event = _status_event(project["status"], "paused", None)
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="status_change",
                title=event["title"],
                status="paused",
                description=event["description"],
                details=event["details"],
                created_at=now,
            )

    def update_completed_project_script(self, project_id: int, script: dict[str, Any]) -> None:
        now = utc_now()
        title = str(script["title"]).strip()
        with self.connect() as conn:
            project = conn.execute(
                """
                SELECT id, inspiration_id, status
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError(f"Project {project_id} was not found.")
            if project["status"] != "completed":
                raise RuntimeError("Only completed projects can have script edits saved.")

            node = conn.execute(
                """
                SELECT status, output_json
                FROM canvas_nodes
                WHERE project_id = ? AND node_key = 'script'
                """,
                (project_id,),
            ).fetchone()
            if node is None:
                raise LookupError(f"Node 'script' was not found in project {project_id}.")
            if node["status"] != "completed" or not node["output_json"]:
                raise RuntimeError("Project script is not ready to edit.")

            previous_script = json.loads(node["output_json"])
            edit_summary = _script_edit_summary(previous_script, script)
            script_json = _json_or_none(script)
            conn.execute(
                """
                UPDATE canvas_nodes
                SET output_json = ?, error = NULL, updated_at = ?
                WHERE project_id = ? AND node_key = 'script'
                """,
                (script_json, now, project_id),
            )
            conn.execute(
                """
                UPDATE projects
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, now, project_id),
            )
            conn.execute(
                """
                UPDATE productions
                SET title = ?, payload_json = ?
                WHERE inspiration_id = ?
                """,
                (title, script_json, project["inspiration_id"]),
            )
            conn.execute(
                """
                INSERT INTO project_events(
                    project_id, event_type, title, status, description, details_json, created_at
                )
                VALUES (?, 'script_edit', 'Script edits saved', 'completed', ?, ?, ?)
                """,
                (
                    project_id,
                    edit_summary["description"],
                    _json_or_none(edit_summary["details"]),
                    now,
                ),
            )

    def update_completed_project_production(
        self, project_id: int, production: dict[str, Any]
    ) -> None:
        _validate_production_pack(production)
        now = utc_now()
        with self.connect() as conn:
            project = conn.execute(
                """
                SELECT id, status
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError(f"Project {project_id} was not found.")
            if project["status"] != "completed":
                raise RuntimeError("Only completed projects can have production edits saved.")

            node = conn.execute(
                """
                SELECT status, output_json
                FROM canvas_nodes
                WHERE project_id = ? AND node_key = 'production'
                """,
                (project_id,),
            ).fetchone()
            if node is None:
                raise LookupError(f"Node 'production' was not found in project {project_id}.")
            if node["status"] != "completed" or not node["output_json"]:
                raise RuntimeError("Project production pack is not ready to edit.")

            previous_production = json.loads(node["output_json"])
            edit_summary = _production_edit_summary(previous_production, production)
            conn.execute(
                """
                UPDATE canvas_nodes
                SET output_json = ?, error = NULL, updated_at = ?
                WHERE project_id = ? AND node_key = 'production'
                """,
                (_json_or_none(production), now, project_id),
            )
            conn.execute(
                """
                UPDATE projects
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, project_id),
            )
            conn.execute(
                """
                INSERT INTO project_events(
                    project_id, event_type, title, status, description, details_json, created_at
                )
                VALUES (?, 'production_edit', 'Production edits saved', 'completed', ?, ?, ?)
                """,
                (
                    project_id,
                    edit_summary["description"],
                    _json_or_none(edit_summary["details"]),
                    now,
                ),
            )

    def update_completed_project_review_notes(
        self, project_id: int, review_notes: dict[str, Any]
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            project = conn.execute(
                """
                SELECT id, status, review_notes_json
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError(f"Project {project_id} was not found.")
            if project["status"] != "completed":
                raise RuntimeError("Only completed projects can have review notes saved.")

            previous_notes = _json_from_column(project["review_notes_json"]) or {}
            summary = _review_notes_summary(previous_notes, review_notes)
            conn.execute(
                """
                UPDATE projects
                SET review_notes_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (_json_or_none(review_notes), now, project_id),
            )
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="review_notes",
                title="Review notes saved",
                status="completed",
                description=summary["description"],
                details=summary["details"],
                created_at=now,
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


def _project_row(row: sqlite3.Row, include_progress: bool = False) -> dict[str, Any]:
    project = {
        "id": row["id"],
        "inspiration_id": row["inspiration_id"],
        "seed_text": row["seed_text"],
        "brief": _json_from_column(row["brief_json"]),
        "review_notes": _json_from_column(row["review_notes_json"]),
        "title": row["title"],
        "status": row["status"],
        "last_error": row["last_error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_progress:
        project["progress"] = {
            "completed": row["progress_completed"],
            "total": row["progress_total"],
            "active_key": row["active_key"],
            "active_title": row["active_title"],
            "failed_key": row["failed_key"],
            "failed_title": row["failed_title"],
        }
    return project


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


def _insert_project_event(
    conn: sqlite3.Connection,
    project_id: int,
    event_type: str,
    title: str,
    status: str,
    description: str,
    details: dict[str, Any] | None,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO project_events(
            project_id, event_type, title, status, description, details_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            event_type,
            title,
            status,
            description,
            _json_or_none(details),
            created_at,
        ),
    )


def _status_event(previous_status: str, status: str, last_error: str | None) -> dict[str, Any]:
    events = {
        "running": ("Project run started", "Agent run is now active."),
        "paused": ("Project paused", "Run will stop after the active agent node."),
        "completed": ("Project completed", "All agent nodes completed."),
        "failed": ("Project failed", (last_error or "Agent run failed.")[:2000]),
        "draft": ("Project reset to draft", "Failed run was reset for editing."),
    }
    if status not in events:
        raise ValueError(f"Unsupported project status: {status}")
    title, description = events[status]
    return {
        "title": title,
        "description": description,
        "details": {
            "previous_status": previous_status,
            "status": status,
        },
    }


def _script_edit_summary(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    changed_fields: list[str] = []
    if previous.get("title") != current.get("title"):
        changed_fields.append("title")
    if previous.get("logline") != current.get("logline"):
        changed_fields.append("logline")

    changed_beats = _changed_index_count(
        previous.get("episode_outline", []),
        current.get("episode_outline", []),
        ("beat", "purpose"),
    )
    changed_scenes = _changed_index_count(
        previous.get("scenes", []),
        current.get("scenes", []),
        ("summary",),
    )
    changed_dialogue = _changed_dialogue_count(
        previous.get("scenes", []),
        current.get("scenes", []),
    )

    summary_parts = []
    if changed_fields:
        summary_parts.append(", ".join(changed_fields))
    if changed_beats:
        summary_parts.append(f"{changed_beats} beat{'s' if changed_beats != 1 else ''}")
    if changed_scenes:
        summary_parts.append(f"{changed_scenes} scene{'s' if changed_scenes != 1 else ''}")
    if changed_dialogue:
        summary_parts.append(
            f"{changed_dialogue} dialogue line{'s' if changed_dialogue != 1 else ''}"
        )

    description = "Updated " + "; ".join(summary_parts) if summary_parts else "Saved script."
    return {
        "description": description,
        "details": {
            "changed_fields": changed_fields,
            "changed_beats": changed_beats,
            "changed_scenes": changed_scenes,
            "changed_dialogue": changed_dialogue,
            "title": current.get("title"),
            "logline": current.get("logline"),
        },
    }


def _production_edit_summary(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    changed_fields: list[str] = []
    if previous.get("visual_style") != current.get("visual_style"):
        changed_fields.append("visual_style")

    changed_locations = _changed_sequence_count(
        previous.get("locations", []),
        current.get("locations", []),
    )
    changed_props = _changed_sequence_count(previous.get("props", []), current.get("props", []))
    changed_shots = _changed_index_count(
        previous.get("shot_plan", []),
        current.get("shot_plan", []),
        ("shot", "purpose", "duration_seconds"),
    )
    changed_edit_notes = _changed_sequence_count(
        previous.get("edit_notes", []),
        current.get("edit_notes", []),
    )

    summary_parts = []
    if changed_fields:
        summary_parts.append(", ".join(changed_fields))
    if changed_locations:
        summary_parts.append(
            f"{changed_locations} location{'s' if changed_locations != 1 else ''}"
        )
    if changed_props:
        summary_parts.append(f"{changed_props} prop{'s' if changed_props != 1 else ''}")
    if changed_shots:
        summary_parts.append(f"{changed_shots} shot{'s' if changed_shots != 1 else ''}")
    if changed_edit_notes:
        summary_parts.append(
            f"{changed_edit_notes} edit note{'s' if changed_edit_notes != 1 else ''}"
        )

    description = (
        "Updated " + "; ".join(summary_parts) if summary_parts else "Saved production pack."
    )
    return {
        "description": description,
        "details": {
            "changed_fields": changed_fields,
            "changed_locations": changed_locations,
            "changed_props": changed_props,
            "changed_shots": changed_shots,
            "changed_edit_notes": changed_edit_notes,
            "visual_style": current.get("visual_style"),
        },
    }


def _review_notes_summary(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    changed_fields = [
        field
        for field in (
            "release_status",
            "summary",
            "next_actions",
            "approval_notes",
            "action_items",
        )
        if previous.get(field) != current.get(field)
    ]
    action_count = len(current.get("next_actions", []))
    approval_count = len(current.get("approval_notes", []))
    action_items = current.get("action_items", [])
    open_items = _review_action_status_count(action_items, "open")
    blocked_items = _review_action_status_count(action_items, "blocked")
    done_items = _review_action_status_count(action_items, "done")
    description = (
        f"Marked {current.get('release_status')}; "
        f"{action_count} next action{'s' if action_count != 1 else ''}; "
        f"{approval_count} approval note{'s' if approval_count != 1 else ''}; "
        f"{open_items} open, {blocked_items} blocked, {done_items} done review task"
        f"{'s' if len(action_items) != 1 else ''}"
    )
    return {
        "description": description,
        "details": {
            "changed_fields": changed_fields,
            "release_status": current.get("release_status"),
            "next_actions": current.get("next_actions", []),
            "approval_notes": current.get("approval_notes", []),
            "action_items": action_items,
            "action_item_counts": {
                "open": open_items,
                "blocked": blocked_items,
                "done": done_items,
            },
        },
    }


def _review_action_status_count(action_items: list[dict[str, Any]], status: str) -> int:
    return sum(1 for item in action_items if item.get("status") == status)


def _changed_sequence_count(previous_items: list[Any], current_items: list[Any]) -> int:
    changed = 0
    for index, current_item in enumerate(current_items):
        previous_item = previous_items[index] if index < len(previous_items) else None
        if previous_item != current_item:
            changed += 1
    return changed + max(0, len(previous_items) - len(current_items))


def _changed_index_count(
    previous_items: list[dict[str, Any]],
    current_items: list[dict[str, Any]],
    keys: tuple[str, ...],
) -> int:
    changed = 0
    for index, current_item in enumerate(current_items):
        previous_item = previous_items[index] if index < len(previous_items) else {}
        if any(previous_item.get(key) != current_item.get(key) for key in keys):
            changed += 1
    return changed


def _changed_dialogue_count(
    previous_scenes: list[dict[str, Any]],
    current_scenes: list[dict[str, Any]],
) -> int:
    changed = 0
    for scene_index, current_scene in enumerate(current_scenes):
        previous_scene = previous_scenes[scene_index] if scene_index < len(previous_scenes) else {}
        previous_lines = previous_scene.get("dialogue", [])
        for line_index, current_line in enumerate(current_scene.get("dialogue", [])):
            previous_line = previous_lines[line_index] if line_index < len(previous_lines) else {}
            if (
                previous_line.get("line") != current_line.get("line")
                or previous_line.get("direction") != current_line.get("direction")
            ):
                changed += 1
    return changed


def _validate_production_pack(production: dict[str, Any]) -> None:
    required = {"visual_style", "locations", "props", "shot_plan", "edit_notes"}
    missing = sorted(required - set(production))
    if missing:
        raise ValueError(f"Production pack is missing required fields: {missing}")
    if not str(production.get("visual_style", "")).strip():
        raise ValueError("Production pack must contain a visual style.")
    _validate_string_list(production.get("locations"), "locations", 2)
    _validate_string_list(production.get("props"), "props", 3)
    _validate_string_list(production.get("edit_notes"), "edit notes", 3)
    shot_plan = production.get("shot_plan")
    if not isinstance(shot_plan, list) or len(shot_plan) < 5:
        raise ValueError("Production pack must contain at least 5 shots.")
    for shot in shot_plan:
        if not isinstance(shot, dict):
            raise ValueError("Each production shot must be an object.")
        if not str(shot.get("shot", "")).strip():
            raise ValueError("Each production shot must contain a shot description.")
        if not str(shot.get("purpose", "")).strip():
            raise ValueError("Each production shot must contain a purpose.")
        duration = shot.get("duration_seconds")
        if not isinstance(duration, int) or duration < 1 or duration > 60:
            raise ValueError("Each production shot duration must be 1-60 seconds.")


def _validate_string_list(value: Any, label: str, min_items: int) -> None:
    if not isinstance(value, list) or len(value) < min_items:
        raise ValueError(f"Production pack must contain at least {min_items} {label}.")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"Production pack {label} cannot contain empty items.")
