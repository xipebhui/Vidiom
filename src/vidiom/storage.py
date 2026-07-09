from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .storyboard import normalize_storyboard_payload
from .storyboard_schema import (
    STORYBOARD_IMAGE_LINK_TYPES,
    STORYBOARD_REVIEW_STATUSES,
    STORYBOARD_STATUSES,
    derive_storyboard_readiness,
)

STORYBOARD_SHOT_EDITABLE_FIELDS = {
    "beat_ref",
    "scene_ref",
    "characters",
    "scene",
    "props",
    "visual_description",
    "action_focus",
    "dialogue_or_sound",
    "duration_seconds",
    "aspect_ratio",
    "visual_style",
    "image_prompt",
    "review_status",
    "prompt_ready",
}

STORYBOARD_SHOT_PRODUCTION_FIELDS = STORYBOARD_SHOT_EDITABLE_FIELDS - {
    "review_status",
    "prompt_ready",
}


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


@dataclass(frozen=True)
class GeneratedImageAsset:
    id: int
    project_id: int
    prompt: str
    model: str
    status: str
    artifact_url: str | None
    b64_json: str | None
    revised_prompt: str | None
    provider_response: dict[str, Any] | None
    error_message: str | None
    created_at: str


@dataclass(frozen=True)
class Storyboard:
    id: int
    project_id: int
    status: str
    model: str | None
    generation_status: str
    generation_started_at: str | None
    generation_finished_at: str | None
    generation_error_message: str | None
    last_completed_at: str | None
    last_completed_model: str | None
    source_script_updated_at: str | None
    source_production_updated_at: str | None
    error_message: str | None
    created_at: str
    updated_at: str


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
                    instruction_json TEXT,
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

                CREATE TABLE IF NOT EXISTS generated_image_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    prompt TEXT NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    artifact_url TEXT,
                    b64_json TEXT,
                    revised_prompt TEXT,
                    provider_response_json TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );

                CREATE INDEX IF NOT EXISTS idx_generated_image_assets_project_id
                    ON generated_image_assets(project_id, id);

                CREATE TABLE IF NOT EXISTS storyboards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'not_started',
                    model TEXT,
                    generation_status TEXT NOT NULL DEFAULT 'not_started',
                    generation_started_at TEXT,
                    generation_finished_at TEXT,
                    generation_error_message TEXT,
                    last_completed_at TEXT,
                    last_completed_model TEXT,
                    source_script_updated_at TEXT,
                    source_production_updated_at TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_storyboards_project_id
                    ON storyboards(project_id);

                CREATE INDEX IF NOT EXISTS idx_storyboards_status
                    ON storyboards(status);

                CREATE TABLE IF NOT EXISTS storyboard_shots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    storyboard_id INTEGER NOT NULL,
                    sequence_index INTEGER NOT NULL,
                    review_status TEXT NOT NULL DEFAULT 'pending',
                    beat_ref TEXT NOT NULL,
                    scene_ref TEXT NOT NULL,
                    characters_json TEXT NOT NULL,
                    scene TEXT NOT NULL,
                    props_json TEXT NOT NULL,
                    visual_description TEXT NOT NULL,
                    action_focus TEXT NOT NULL,
                    dialogue_or_sound TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    aspect_ratio TEXT NOT NULL,
                    visual_style TEXT NOT NULL,
                    image_prompt TEXT NOT NULL,
                    prompt_ready INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(storyboard_id) REFERENCES storyboards(id) ON DELETE CASCADE,
                    UNIQUE(storyboard_id, sequence_index)
                );

                CREATE INDEX IF NOT EXISTS idx_storyboard_shots_storyboard_sequence
                    ON storyboard_shots(storyboard_id, sequence_index);

                CREATE TABLE IF NOT EXISTS project_story_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    asset_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    reference_prompt TEXT NOT NULL,
                    consistency_notes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    UNIQUE(project_id, asset_type, name)
                );

                CREATE INDEX IF NOT EXISTS idx_project_story_assets_project_type
                    ON project_story_assets(project_id, asset_type, name);

                CREATE TABLE IF NOT EXISTS storyboard_shot_assets (
                    shot_id INTEGER NOT NULL,
                    asset_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    PRIMARY KEY(shot_id, asset_id, role),
                    FOREIGN KEY(shot_id) REFERENCES storyboard_shots(id) ON DELETE CASCADE,
                    FOREIGN KEY(asset_id) REFERENCES project_story_assets(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_storyboard_shot_assets_asset_id
                    ON storyboard_shot_assets(asset_id);

                CREATE TABLE IF NOT EXISTS storyboard_shot_image_assets (
                    shot_id INTEGER NOT NULL,
                    image_asset_id INTEGER NOT NULL,
                    link_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(shot_id, image_asset_id, link_type),
                    FOREIGN KEY(shot_id) REFERENCES storyboard_shots(id) ON DELETE CASCADE,
                    FOREIGN KEY(image_asset_id) REFERENCES generated_image_assets(id)
                );

                CREATE INDEX IF NOT EXISTS idx_storyboard_shot_image_assets_image_asset_id
                    ON storyboard_shot_image_assets(image_asset_id);
                """
            )
            project_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()
            }
            if "brief_json" not in project_columns:
                conn.execute("ALTER TABLE projects ADD COLUMN brief_json TEXT")
            if "review_notes_json" not in project_columns:
                conn.execute("ALTER TABLE projects ADD COLUMN review_notes_json TEXT")
            node_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(canvas_nodes)").fetchall()
            }
            if "instruction_json" not in node_columns:
                conn.execute("ALTER TABLE canvas_nodes ADD COLUMN instruction_json TEXT")
            storyboard_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(storyboards)").fetchall()
            }
            if "generation_status" not in storyboard_columns:
                conn.execute(
                    "ALTER TABLE storyboards "
                    "ADD COLUMN generation_status TEXT NOT NULL DEFAULT 'not_started'"
                )
            if "generation_started_at" not in storyboard_columns:
                conn.execute("ALTER TABLE storyboards ADD COLUMN generation_started_at TEXT")
            if "generation_finished_at" not in storyboard_columns:
                conn.execute("ALTER TABLE storyboards ADD COLUMN generation_finished_at TEXT")
            if "generation_error_message" not in storyboard_columns:
                conn.execute("ALTER TABLE storyboards ADD COLUMN generation_error_message TEXT")
            if "last_completed_at" not in storyboard_columns:
                conn.execute("ALTER TABLE storyboards ADD COLUMN last_completed_at TEXT")
            if "last_completed_model" not in storyboard_columns:
                conn.execute("ALTER TABLE storyboards ADD COLUMN last_completed_model TEXT")
            conn.execute(
                """
                UPDATE storyboards
                SET generation_status = status
                WHERE generation_status = 'not_started' AND status != 'not_started'
                """
            )
            conn.execute(
                """
                UPDATE storyboards
                SET last_completed_at = COALESCE(last_completed_at, updated_at),
                    last_completed_model = COALESCE(last_completed_model, model)
                WHERE status = 'completed'
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
        instructions: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO canvas_nodes(
                    project_id, node_key, title, kind, x, y, status,
                    output_json, instruction_json, error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
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
                    _json_or_none(instructions),
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
                    status, output_json, instruction_json, error, updated_at
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
            asset_rows = conn.execute(
                """
                SELECT
                    id, project_id, prompt, model, status, artifact_url, b64_json,
                    revised_prompt, provider_response_json, error_message, created_at
                FROM generated_image_assets
                WHERE project_id = ?
                ORDER BY id DESC
                """,
                (project_id,),
            ).fetchall()

        project = _project_row(project_row)
        project["nodes"] = [_node_row(row) for row in node_rows]
        project["edges"] = [
            {"source": row["source_key"], "target": row["target_key"]} for row in edge_rows
        ]
        project["image_assets"] = [_image_asset_row(row) for row in asset_rows]
        return project

    def get_or_create_project_storyboard(
        self,
        project_id: int,
        *,
        status: str = "not_started",
        model: str | None = None,
        error_message: str | None = None,
    ) -> Storyboard:
        if status not in STORYBOARD_STATUSES:
            raise ValueError(f"Unsupported storyboard status: {status}")
        now = utc_now()
        with self.connect() as conn:
            source = _storyboard_source_row(conn, project_id)
            if source["project"] is None:
                raise LookupError(f"Project {project_id} was not found.")
            row = conn.execute(
                """
                SELECT
                    id, project_id, status, model, generation_status, generation_started_at,
                    generation_finished_at, generation_error_message, last_completed_at,
                    last_completed_model, source_script_updated_at,
                    source_production_updated_at, error_message, created_at, updated_at
                FROM storyboards
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
            if row is None:
                cursor = conn.execute(
                    """
                    INSERT INTO storyboards(
                        project_id, status, model, generation_status, generation_started_at,
                        generation_finished_at, generation_error_message, last_completed_at,
                        last_completed_model, source_script_updated_at,
                        source_production_updated_at, error_message, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        status,
                        model,
                        status,
                        now if status == "generating" else None,
                        now if status in {"completed", "failed", "interrupted"} else None,
                        error_message[:2000] if error_message else None,
                        now if status == "completed" else None,
                        model if status == "completed" else None,
                        source["script_updated_at"],
                        source["production_updated_at"],
                        error_message[:2000] if error_message else None,
                        now,
                        now,
                    ),
                )
                row = conn.execute(
                    """
                    SELECT
                        id, project_id, status, model, generation_status, generation_started_at,
                        generation_finished_at, generation_error_message, last_completed_at,
                        last_completed_model, source_script_updated_at,
                        source_production_updated_at, error_message, created_at, updated_at
                    FROM storyboards
                    WHERE id = ?
                    """,
                    (int(cursor.lastrowid),),
                ).fetchone()
                _insert_project_event(
                    conn=conn,
                    project_id=project_id,
                    event_type="storyboard_generation",
                    title="Storyboard initialized",
                    status=status,
                    description="Storyboard workspace created for this project.",
                    details={"storyboard_id": int(cursor.lastrowid), "model": model},
                    created_at=now,
                )
            if row is None:
                raise RuntimeError("Storyboard could not be created.")
            return _storyboard_row(row)

    def update_project_storyboard_status(
        self,
        project_id: int,
        *,
        status: str,
        model: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if status not in STORYBOARD_STATUSES:
            raise ValueError(f"Unsupported storyboard status: {status}")
        now = utc_now()
        with self.connect() as conn:
            source = _storyboard_source_row(conn, project_id)
            if source["project"] is None:
                raise LookupError(f"Project {project_id} was not found.")
            row = _ensure_storyboard_row(
                conn=conn,
                project_id=project_id,
                status=status,
                model=model,
                source_script_updated_at=source["script_updated_at"],
                source_production_updated_at=source["production_updated_at"],
                error_message=error_message,
                now=now,
            )
            conn.execute(
                """
                UPDATE storyboards
                SET status = ?, model = COALESCE(?, model),
                    generation_status = ?,
                    generation_started_at = CASE
                        WHEN ? = 'generating' THEN ?
                        ELSE generation_started_at
                    END,
                    generation_finished_at = CASE
                        WHEN ? IN ('completed', 'failed', 'interrupted') THEN ?
                        ELSE NULL
                    END,
                    generation_error_message = ?,
                    last_completed_at = CASE
                        WHEN ? = 'completed' THEN ?
                        ELSE last_completed_at
                    END,
                    last_completed_model = CASE
                        WHEN ? = 'completed' THEN COALESCE(?, last_completed_model)
                        ELSE last_completed_model
                    END,
                    source_script_updated_at = ?, source_production_updated_at = ?,
                    error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    model,
                    status,
                    status,
                    now,
                    status,
                    now,
                    error_message[:2000] if error_message else None,
                    status,
                    now,
                    status,
                    model,
                    source["script_updated_at"],
                    source["production_updated_at"],
                    error_message[:2000] if error_message else None,
                    now,
                    row["id"],
                ),
            )
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="storyboard_generation",
                title=_storyboard_status_title(status),
                status=status,
                description=(error_message or _storyboard_status_description(status))[:2000],
                details={"storyboard_id": row["id"], "model": model or row["model"]},
                created_at=now,
            )

    def replace_project_storyboard(
        self,
        project_id: int,
        payload: dict[str, Any],
        *,
        model: str | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_storyboard_payload(payload)
        now = utc_now()
        with self.connect() as conn:
            source = _storyboard_source_row(conn, project_id)
            if source["project"] is None:
                raise LookupError(f"Project {project_id} was not found.")
            storyboard = _ensure_storyboard_row(
                conn=conn,
                project_id=project_id,
                status="completed",
                model=model,
                source_script_updated_at=source["script_updated_at"],
                source_production_updated_at=source["production_updated_at"],
                error_message=None,
                now=now,
            )
            storyboard_id = int(storyboard["id"])
            conn.execute(
                "DELETE FROM storyboard_shots WHERE storyboard_id = ?",
                (storyboard_id,),
            )
            conn.execute(
                "DELETE FROM project_story_assets WHERE project_id = ?",
                (project_id,),
            )

            shot_ids_by_sequence: dict[int, int] = {}
            for shot in sorted(normalized["shots"], key=lambda item: item["sequence_index"]):
                cursor = conn.execute(
                    """
                    INSERT INTO storyboard_shots(
                        storyboard_id, sequence_index, review_status, beat_ref, scene_ref,
                        characters_json, scene, props_json, visual_description, action_focus,
                        dialogue_or_sound, duration_seconds, aspect_ratio, visual_style,
                        image_prompt, prompt_ready, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        storyboard_id,
                        shot["sequence_index"],
                        shot["review_status"],
                        shot["beat_ref"],
                        shot["scene_ref"],
                        _json_or_none({"items": shot["characters"]}),
                        shot["scene"],
                        _json_or_none({"items": shot["props"]}),
                        shot["visual_description"],
                        shot["action_focus"],
                        shot["dialogue_or_sound"],
                        shot["duration_seconds"],
                        shot["aspect_ratio"],
                        shot["visual_style"],
                        shot["image_prompt"],
                        1 if shot["prompt_ready"] else 0,
                        now,
                        now,
                    ),
                )
                shot_ids_by_sequence[shot["sequence_index"]] = int(cursor.lastrowid)

            asset_ids_by_key: dict[tuple[str, str], int] = {}
            for asset in normalized["assets"]:
                cursor = conn.execute(
                    """
                    INSERT INTO project_story_assets(
                        project_id, asset_type, name, description, reference_prompt,
                        consistency_notes, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        asset["asset_type"],
                        asset["name"],
                        asset["description"],
                        asset["reference_prompt"],
                        asset["consistency_notes"],
                        now,
                        now,
                    ),
                )
                asset_ids_by_key[(asset["asset_type"], asset["name"])] = int(cursor.lastrowid)

            for relationship in normalized["relationships"]:
                shot_id = shot_ids_by_sequence[relationship["shot_sequence_index"]]
                asset_id = asset_ids_by_key[
                    (relationship["asset_type"], relationship["asset_name"])
                ]
                conn.execute(
                    """
                    INSERT INTO storyboard_shot_assets(shot_id, asset_id, role)
                    VALUES (?, ?, ?)
                    """,
                    (shot_id, asset_id, relationship["role"]),
                )

            conn.execute(
                """
                UPDATE storyboards
                SET status = 'completed', model = COALESCE(?, model),
                    generation_status = 'completed',
                    generation_finished_at = ?,
                    generation_error_message = NULL,
                    last_completed_at = ?,
                    last_completed_model = COALESCE(?, last_completed_model),
                    source_script_updated_at = ?, source_production_updated_at = ?,
                    error_message = NULL, updated_at = ?
                WHERE id = ?
                """,
                (
                    model,
                    now,
                    now,
                    model,
                    source["script_updated_at"],
                    source["production_updated_at"],
                    now,
                    storyboard_id,
                ),
            )
            conn.execute(
                """
                UPDATE projects
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, project_id),
            )
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="storyboard_generation",
                title="Storyboard saved",
                status="completed",
                description=(
                    f"Saved {len(normalized['shots'])} storyboard shots and "
                    f"{len(normalized['assets'])} story assets."
                ),
                details={
                    "storyboard_id": storyboard_id,
                    "model": model,
                    "shot_count": len(normalized["shots"]),
                    "asset_count": len(normalized["assets"]),
                    "relationship_count": len(normalized["relationships"]),
                },
                created_at=now,
            )
        return self.get_project_storyboard(project_id)

    def get_project_storyboard(self, project_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
            if project is None:
                raise LookupError(f"Project {project_id} was not found.")
            storyboard_row = conn.execute(
                """
                SELECT
                    id, project_id, status, model, generation_status, generation_started_at,
                    generation_finished_at, generation_error_message, last_completed_at,
                    last_completed_model, source_script_updated_at,
                    source_production_updated_at, error_message, created_at, updated_at
                FROM storyboards
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
            if storyboard_row is None:
                return None
            shot_rows = conn.execute(
                """
                SELECT
                    id, storyboard_id, sequence_index, review_status, beat_ref, scene_ref,
                    characters_json, scene, props_json, visual_description, action_focus,
                    dialogue_or_sound, duration_seconds, aspect_ratio, visual_style,
                    image_prompt, prompt_ready, created_at, updated_at
                FROM storyboard_shots
                WHERE storyboard_id = ?
                ORDER BY sequence_index, id
                """,
                (storyboard_row["id"],),
            ).fetchall()
            asset_rows = conn.execute(
                """
                SELECT
                    id, project_id, asset_type, name, description, reference_prompt,
                    consistency_notes, created_at, updated_at
                FROM project_story_assets
                WHERE project_id = ?
                ORDER BY asset_type, name, id
                """,
                (project_id,),
            ).fetchall()
            relationship_rows = conn.execute(
                """
                SELECT
                    s.id AS shot_id, s.sequence_index, a.id AS asset_id, a.asset_type,
                    a.name AS asset_name, rsa.role
                FROM storyboard_shot_assets rsa
                JOIN storyboard_shots s ON s.id = rsa.shot_id
                JOIN project_story_assets a ON a.id = rsa.asset_id
                WHERE s.storyboard_id = ?
                ORDER BY s.sequence_index, a.asset_type, a.name, rsa.role
                """,
                (storyboard_row["id"],),
            ).fetchall()
            image_link_rows = conn.execute(
                """
                SELECT
                    s.id AS shot_id, s.sequence_index, gia.id AS image_asset_id,
                    gia.project_id, gia.prompt, gia.model, gia.status, gia.artifact_url,
                    gia.revised_prompt, gia.error_message, sil.link_type, sil.created_at
                FROM storyboard_shot_image_assets sil
                JOIN storyboard_shots s ON s.id = sil.shot_id
                JOIN generated_image_assets gia ON gia.id = sil.image_asset_id
                WHERE s.storyboard_id = ?
                ORDER BY s.sequence_index, sil.created_at, gia.id
                """,
                (storyboard_row["id"],),
            ).fetchall()
        shots = [_storyboard_shot_row(row) for row in shot_rows]
        assets = [_story_asset_row(row) for row in asset_rows]
        relationships = [_storyboard_relationship_row(row) for row in relationship_rows]
        image_links = [_storyboard_image_link_row(row) for row in image_link_rows]
        readiness = derive_storyboard_readiness(
            shots=shots,
            assets=assets,
            relationships=relationships,
            image_links=image_links,
        )
        blockers_by_shot_id = {
            item["shot_id"]: item["blockers"] for item in readiness["shot_blockers"]
        }
        for shot in shots:
            shot["blockers"] = blockers_by_shot_id.get(shot["id"], [])

        return {
            "storyboard": _storyboard_row(storyboard_row).__dict__,
            "shots": shots,
            "assets": assets,
            "relationships": relationships,
            "image_links": image_links,
            "readiness_summary": readiness["readiness_summary"],
            "shot_blockers": readiness["shot_blockers"],
            "has_completed_result": storyboard_row["last_completed_at"] is not None
            and len(shot_rows) > 0,
            "latest_attempt_failed": storyboard_row["generation_status"] == "failed",
            "latest_attempt_interrupted": storyboard_row["generation_status"] == "interrupted",
            "result_source": "last_completed_result"
            if storyboard_row["last_completed_at"] is not None and len(shot_rows) > 0
            else None,
        }

    def update_storyboard_shot(
        self,
        project_id: int,
        shot_id: int,
        fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        clean_fields = _clean_storyboard_shot_update(fields)
        if not clean_fields:
            raise ValueError("Provide at least one storyboard shot field.")
        now = utc_now()
        with self.connect() as conn:
            storyboard = _completed_storyboard_row(conn, project_id)
            shot = _project_storyboard_shot(conn, project_id, shot_id)
            if shot is None:
                raise LookupError(
                    f"Storyboard shot {shot_id} was not found in project {project_id}."
                )
            prompt_affecting = any(
                field in STORYBOARD_SHOT_PRODUCTION_FIELDS for field in clean_fields
            )
            next_prompt_ready = clean_fields.get("prompt_ready")
            if prompt_affecting:
                clean_fields["prompt_ready"] = False
            elif next_prompt_ready and not str(
                clean_fields.get("image_prompt", shot["image_prompt"])
            ).strip():
                raise ValueError("Prompt ready requires a non-empty image prompt.")

            assignments: list[str] = []
            params: list[Any] = []
            for field in sorted(clean_fields):
                column, value = _storyboard_shot_column_value(field, clean_fields[field])
                assignments.append(f"{column} = ?")
                params.append(value)
            assignments.append("updated_at = ?")
            params.append(now)
            params.append(shot_id)
            conn.execute(
                f"""
                UPDATE storyboard_shots
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                params,
            )
            _touch_storyboard_project(conn, project_id, int(storyboard["id"]), now)
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="storyboard_edit",
                title="Storyboard shot updated",
                status="completed",
                description=f"Updated storyboard shot #{shot['sequence_index']}.",
                details={
                    "storyboard_id": int(storyboard["id"]),
                    "shot_id": shot_id,
                    "sequence_index": shot["sequence_index"],
                    "fields": sorted(clean_fields),
                    "prompt_ready_reset": prompt_affecting,
                },
                created_at=now,
            )
        return self.get_project_storyboard(project_id)

    def create_storyboard_shot(
        self,
        project_id: int,
        fields: dict[str, Any],
        *,
        sequence_index: int | None = None,
    ) -> dict[str, Any] | None:
        clean_fields = _clean_storyboard_shot_create(fields)
        now = utc_now()
        with self.connect() as conn:
            storyboard = _completed_storyboard_row(conn, project_id)
            current_rows = _storyboard_shot_order_rows(conn, int(storyboard["id"]))
            insert_position = len(current_rows) + 1 if sequence_index is None else sequence_index
            if insert_position < 1 or insert_position > len(current_rows) + 1:
                raise ValueError("Storyboard shot insert position is out of range.")
            cursor = conn.execute(
                """
                INSERT INTO storyboard_shots(
                    storyboard_id, sequence_index, review_status, beat_ref, scene_ref,
                    characters_json, scene, props_json, visual_description, action_focus,
                    dialogue_or_sound, duration_seconds, aspect_ratio, visual_style,
                    image_prompt, prompt_ready, created_at, updated_at
                )
                VALUES (?, -1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    int(storyboard["id"]),
                    clean_fields["review_status"],
                    clean_fields["beat_ref"],
                    clean_fields["scene_ref"],
                    _json_or_none({"items": clean_fields["characters"]}),
                    clean_fields["scene"],
                    _json_or_none({"items": clean_fields["props"]}),
                    clean_fields["visual_description"],
                    clean_fields["action_focus"],
                    clean_fields["dialogue_or_sound"],
                    clean_fields["duration_seconds"],
                    clean_fields["aspect_ratio"],
                    clean_fields["visual_style"],
                    clean_fields["image_prompt"],
                    now,
                    now,
                ),
            )
            new_shot_id = int(cursor.lastrowid)
            ordered_ids = [int(row["id"]) for row in current_rows]
            ordered_ids.insert(insert_position - 1, new_shot_id)
            _safe_resequence_storyboard_shots(conn, ordered_ids, now, reset_prompt_ready=True)
            _touch_storyboard_project(conn, project_id, int(storyboard["id"]), now)
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="storyboard_edit",
                title="Storyboard shot created",
                status="completed",
                description=f"Inserted storyboard shot at position {insert_position}.",
                details={
                    "storyboard_id": int(storyboard["id"]),
                    "shot_id": new_shot_id,
                    "sequence_index": insert_position,
                    "prompt_ready_reset": True,
                },
                created_at=now,
            )
        return self.get_project_storyboard(project_id)

    def delete_storyboard_shot(
        self,
        project_id: int,
        shot_id: int,
    ) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as conn:
            storyboard = _completed_storyboard_row(conn, project_id)
            shot = _project_storyboard_shot(conn, project_id, shot_id)
            if shot is None:
                raise LookupError(
                    f"Storyboard shot {shot_id} was not found in project {project_id}."
                )
            current_rows = _storyboard_shot_order_rows(conn, int(storyboard["id"]))
            if len(current_rows) <= 1:
                raise ValueError("Cannot delete the final storyboard shot.")
            conn.execute("DELETE FROM storyboard_shot_assets WHERE shot_id = ?", (shot_id,))
            conn.execute("DELETE FROM storyboard_shot_image_assets WHERE shot_id = ?", (shot_id,))
            conn.execute("DELETE FROM storyboard_shots WHERE id = ?", (shot_id,))
            remaining_ids = [
                int(row["id"])
                for row in _storyboard_shot_order_rows(conn, int(storyboard["id"]))
            ]
            if remaining_ids:
                _safe_resequence_storyboard_shots(conn, remaining_ids, now, reset_prompt_ready=True)
            _touch_storyboard_project(conn, project_id, int(storyboard["id"]), now)
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="storyboard_edit",
                title="Storyboard shot deleted",
                status="completed",
                description=f"Deleted storyboard shot #{shot['sequence_index']}.",
                details={
                    "storyboard_id": int(storyboard["id"]),
                    "shot_id": shot_id,
                    "sequence_index": shot["sequence_index"],
                    "remaining_shot_count": len(remaining_ids),
                    "prompt_ready_reset": bool(remaining_ids),
                },
                created_at=now,
            )
        return self.get_project_storyboard(project_id)

    def reorder_storyboard_shots(
        self,
        project_id: int,
        shot_ids: Iterable[int],
    ) -> dict[str, Any] | None:
        ordered_ids = [int(shot_id) for shot_id in shot_ids]
        if not ordered_ids:
            raise ValueError("Provide at least one storyboard shot id.")
        if len(set(ordered_ids)) != len(ordered_ids):
            raise ValueError("Storyboard shot reorder contains duplicate shot ids.")
        now = utc_now()
        with self.connect() as conn:
            storyboard = _completed_storyboard_row(conn, project_id)
            current_ids = [
                int(row["id"])
                for row in _storyboard_shot_order_rows(conn, int(storyboard["id"]))
            ]
            if set(ordered_ids) != set(current_ids):
                raise ValueError("Storyboard shot reorder must include every current shot.")
            _safe_resequence_storyboard_shots(conn, ordered_ids, now, reset_prompt_ready=True)
            _touch_storyboard_project(conn, project_id, int(storyboard["id"]), now)
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="storyboard_edit",
                title="Storyboard shots reordered",
                status="completed",
                description=f"Reordered {len(ordered_ids)} storyboard shots.",
                details={
                    "storyboard_id": int(storyboard["id"]),
                    "shot_ids": ordered_ids,
                    "prompt_ready_reset": True,
                },
                created_at=now,
            )
        return self.get_project_storyboard(project_id)

    def link_storyboard_shot_image_asset(
        self,
        project_id: int,
        shot_id: int,
        image_asset_id: int,
        *,
        link_type: str = "reference",
    ) -> None:
        if link_type not in STORYBOARD_IMAGE_LINK_TYPES:
            raise ValueError(f"Unsupported storyboard image link type: {link_type}")
        now = utc_now()
        with self.connect() as conn:
            shot = _project_storyboard_shot(conn, project_id, shot_id)
            if shot is None:
                raise LookupError(
                    f"Storyboard shot {shot_id} was not found in project {project_id}."
                )
            image_asset = conn.execute(
                """
                SELECT id
                FROM generated_image_assets
                WHERE id = ? AND project_id = ?
                """,
                (image_asset_id, project_id),
            ).fetchone()
            if image_asset is None:
                raise LookupError(
                    f"Image asset {image_asset_id} was not found in project {project_id}."
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO storyboard_shot_image_assets(
                    shot_id, image_asset_id, link_type, created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (shot_id, image_asset_id, link_type, now),
            )
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="storyboard_image_link",
                title="Storyboard image linked",
                status="completed",
                description=f"Linked image asset {image_asset_id} to storyboard shot.",
                details={
                    "shot_id": shot_id,
                    "sequence_index": shot["sequence_index"],
                    "image_asset_id": image_asset_id,
                    "link_type": link_type,
                },
                created_at=now,
            )

    def delete_storyboard_shot_image_asset(
        self,
        project_id: int,
        shot_id: int,
        image_asset_id: int,
        *,
        link_type: str = "reference",
    ) -> None:
        if link_type not in STORYBOARD_IMAGE_LINK_TYPES:
            raise ValueError(f"Unsupported storyboard image link type: {link_type}")
        now = utc_now()
        with self.connect() as conn:
            shot = _project_storyboard_shot(conn, project_id, shot_id)
            if shot is None:
                raise LookupError(
                    f"Storyboard shot {shot_id} was not found in project {project_id}."
                )
            conn.execute(
                """
                DELETE FROM storyboard_shot_image_assets
                WHERE shot_id = ? AND image_asset_id = ? AND link_type = ?
                """,
                (shot_id, image_asset_id, link_type),
            )
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="storyboard_image_link",
                title="Storyboard image unlinked",
                status="completed",
                description=f"Removed image asset {image_asset_id} from storyboard shot.",
                details={
                    "shot_id": shot_id,
                    "sequence_index": shot["sequence_index"],
                    "image_asset_id": image_asset_id,
                    "link_type": link_type,
                },
                created_at=now,
            )

    def update_storyboard_shot_reviews(
        self,
        project_id: int,
        reviews: Iterable[dict[str, Any]],
    ) -> dict[str, Any] | None:
        now = utc_now()
        rows = list(reviews)
        if not rows:
            raise ValueError("Provide at least one storyboard shot review.")
        with self.connect() as conn:
            for review in rows:
                shot_id = int(review["shot_id"])
                review_status = str(review["review_status"])
                prompt_ready = bool(review["prompt_ready"])
                if review_status not in STORYBOARD_REVIEW_STATUSES:
                    raise ValueError(f"Unsupported storyboard review status: {review_status}")
                shot = conn.execute(
                    """
                    SELECT s.id, s.sequence_index, s.image_prompt
                    FROM storyboard_shots s
                    JOIN storyboards sb ON sb.id = s.storyboard_id
                    WHERE s.id = ? AND sb.project_id = ?
                    """,
                    (shot_id, project_id),
                ).fetchone()
                if shot is None:
                    raise LookupError(
                        f"Storyboard shot {shot_id} was not found in project {project_id}."
                    )
                if prompt_ready and not str(shot["image_prompt"]).strip():
                    raise ValueError("Prompt ready requires a non-empty image prompt.")
                conn.execute(
                    """
                    UPDATE storyboard_shots
                    SET review_status = ?, prompt_ready = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (review_status, 1 if prompt_ready else 0, now, shot_id),
                )
            conn.execute(
                """
                UPDATE projects
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, project_id),
            )
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="storyboard_review",
                title="Storyboard reviews saved",
                status="completed",
                description=f"Updated {len(rows)} storyboard shot review states.",
                details={"shot_ids": [int(review["shot_id"]) for review in rows]},
                created_at=now,
            )
        return self.get_project_storyboard(project_id)

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

        deliverables = {
            "script": script,
            "production_pack": production,
            "review_notes": project["review_notes"],
            "image_assets": project["image_assets"],
        }
        storyboard = self.get_project_storyboard(project_id)
        if storyboard is not None and storyboard["has_completed_result"]:
            deliverables["storyboard"] = storyboard

        return {
            "project": {
                "id": project["id"],
                "title": project["title"],
                "status": project["status"],
                "seed_text": project["seed_text"],
                "brief": project["brief"],
                "review_notes": project["review_notes"],
                "agent_instructions": {
                    key: node["instructions"]
                    for key, node in nodes.items()
                    if node["instructions"] is not None
                },
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
            },
            "deliverables": deliverables,
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
                    status, output_json, instruction_json, error, updated_at
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

    def update_canvas_node_instructions(
        self, project_id: int, node_key: str, instructions: dict[str, Any] | None
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

            node = conn.execute(
                """
                SELECT node_key, title, kind, status
                FROM canvas_nodes
                WHERE project_id = ? AND node_key = ?
                """,
                (project_id, node_key),
            ).fetchone()
            if node is None:
                raise LookupError(f"Node {node_key!r} was not found in project {project_id}.")
            if node["kind"] != "agent":
                raise RuntimeError("Only agent nodes can have generation instructions.")
            if project["status"] == "running" and node["status"] != "pending":
                raise RuntimeError("Only pending nodes can be edited while a project is running.")

            conn.execute(
                """
                UPDATE canvas_nodes
                SET instruction_json = ?, updated_at = ?
                WHERE project_id = ? AND node_key = ?
                """,
                (_json_or_none(instructions), now, project_id, node_key),
            )
            conn.execute(
                """
                UPDATE projects
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, project_id),
            )
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="node_instruction",
                title="Node instructions saved",
                status="completed",
                description=_node_instruction_description(str(node["title"]), instructions),
                details={
                    "node_key": node_key,
                    "node_title": node["title"],
                    "instructions": instructions,
                },
                created_at=now,
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

    def create_generated_image_asset(
        self,
        *,
        project_id: int,
        prompt: str,
        model: str,
        status: str,
        artifact_url: str | None = None,
        b64_json: str | None = None,
        revised_prompt: str | None = None,
        provider_response: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> int:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("Image prompt cannot be empty.")
        if status not in {"completed", "failed"}:
            raise ValueError("Image asset status must be completed or failed.")
        now = utc_now()
        with self.connect() as conn:
            project = conn.execute(
                """
                SELECT id
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError(f"Project {project_id} was not found.")
            cursor = conn.execute(
                """
                INSERT INTO generated_image_assets(
                    project_id, prompt, model, status, artifact_url, b64_json, revised_prompt,
                    provider_response_json, error_message, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    clean_prompt,
                    model,
                    status,
                    artifact_url,
                    b64_json,
                    revised_prompt,
                    _json_or_none(provider_response),
                    error_message[:2000] if error_message else None,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE projects
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, project_id),
            )
            _insert_project_event(
                conn=conn,
                project_id=project_id,
                event_type="image_generation",
                title="Image generation completed"
                if status == "completed"
                else "Image generation failed",
                status=status,
                description=clean_prompt[:200]
                if status == "completed"
                else (error_message or "Image generation failed.")[:2000],
                details={"asset_id": int(cursor.lastrowid), "model": model, "prompt": clean_prompt},
                created_at=now,
            )
            return int(cursor.lastrowid)

    def list_generated_image_assets(self, project_id: int) -> list[GeneratedImageAsset]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id, project_id, prompt, model, status, artifact_url, b64_json,
                    revised_prompt, provider_response_json, error_message, created_at
                FROM generated_image_assets
                WHERE project_id = ?
                ORDER BY id DESC
                """,
                (project_id,),
            ).fetchall()
        return [
            GeneratedImageAsset(
                id=row["id"],
                project_id=row["project_id"],
                prompt=row["prompt"],
                model=row["model"],
                status=row["status"],
                artifact_url=row["artifact_url"],
                b64_json=row["b64_json"],
                revised_prompt=row["revised_prompt"],
                provider_response=_json_from_column(row["provider_response_json"]),
                error_message=row["error_message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


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
        "instructions": _json_from_column(row["instruction_json"]),
        "error": row["error"],
        "updated_at": row["updated_at"],
    }


def _image_asset_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "prompt": row["prompt"],
        "model": row["model"],
        "status": row["status"],
        "artifact_url": row["artifact_url"],
        "b64_json": row["b64_json"],
        "revised_prompt": row["revised_prompt"],
        "provider_response": _json_from_column(row["provider_response_json"]),
        "error_message": row["error_message"],
        "created_at": row["created_at"],
    }


def _storyboard_row(row: sqlite3.Row) -> Storyboard:
    return Storyboard(
        id=row["id"],
        project_id=row["project_id"],
        status=row["status"],
        model=row["model"],
        generation_status=row["generation_status"],
        generation_started_at=row["generation_started_at"],
        generation_finished_at=row["generation_finished_at"],
        generation_error_message=row["generation_error_message"],
        last_completed_at=row["last_completed_at"],
        last_completed_model=row["last_completed_model"],
        source_script_updated_at=row["source_script_updated_at"],
        source_production_updated_at=row["source_production_updated_at"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _storyboard_shot_row(row: sqlite3.Row) -> dict[str, Any]:
    characters = _json_from_column(row["characters_json"]) or {"items": []}
    props = _json_from_column(row["props_json"]) or {"items": []}
    return {
        "id": row["id"],
        "storyboard_id": row["storyboard_id"],
        "sequence_index": row["sequence_index"],
        "review_status": row["review_status"],
        "beat_ref": row["beat_ref"],
        "scene_ref": row["scene_ref"],
        "characters": characters.get("items", []),
        "scene": row["scene"],
        "props": props.get("items", []),
        "visual_description": row["visual_description"],
        "action_focus": row["action_focus"],
        "dialogue_or_sound": row["dialogue_or_sound"],
        "duration_seconds": row["duration_seconds"],
        "aspect_ratio": row["aspect_ratio"],
        "visual_style": row["visual_style"],
        "image_prompt": row["image_prompt"],
        "prompt_ready": bool(row["prompt_ready"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _story_asset_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "asset_type": row["asset_type"],
        "name": row["name"],
        "description": row["description"],
        "reference_prompt": row["reference_prompt"],
        "consistency_notes": row["consistency_notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _storyboard_relationship_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "shot_id": row["shot_id"],
        "shot_sequence_index": row["sequence_index"],
        "asset_id": row["asset_id"],
        "asset_type": row["asset_type"],
        "asset_name": row["asset_name"],
        "role": row["role"],
    }


def _storyboard_image_link_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "shot_id": row["shot_id"],
        "shot_sequence_index": row["sequence_index"],
        "image_asset": {
            "id": row["image_asset_id"],
            "project_id": row["project_id"],
            "prompt": row["prompt"],
            "model": row["model"],
            "status": row["status"],
            "artifact_url": row["artifact_url"],
            "revised_prompt": row["revised_prompt"],
            "error_message": row["error_message"],
        },
        "link_type": row["link_type"],
        "created_at": row["created_at"],
    }


def _clean_storyboard_shot_update(fields: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(fields) - STORYBOARD_SHOT_EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"Unsupported storyboard shot fields: {unknown}")
    return {
        field: _clean_storyboard_shot_field(field, value)
        for field, value in fields.items()
        if value is not None
    }


def _clean_storyboard_shot_create(fields: dict[str, Any]) -> dict[str, Any]:
    required = STORYBOARD_SHOT_EDITABLE_FIELDS - {"prompt_ready"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"Storyboard shot is missing required fields: {missing}")
    clean = _clean_storyboard_shot_update(fields)
    clean["prompt_ready"] = False
    return clean


def _clean_storyboard_shot_field(field: str, value: Any) -> Any:
    if field in {
        "beat_ref",
        "scene_ref",
        "scene",
        "visual_description",
        "action_focus",
        "dialogue_or_sound",
        "aspect_ratio",
        "visual_style",
        "image_prompt",
    }:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Storyboard shot {field} cannot be empty.")
        return value.strip()
    if field in {"characters", "props"}:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"Storyboard shot {field} must be a string list.")
        return [item.strip() for item in value if item.strip()]
    if field == "duration_seconds":
        if not isinstance(value, int) or value < 1 or value > 120:
            raise ValueError("Storyboard shot duration must be 1-120 seconds.")
        return value
    if field == "review_status":
        if value not in STORYBOARD_REVIEW_STATUSES:
            raise ValueError(f"Unsupported storyboard review status: {value}")
        return value
    if field == "prompt_ready":
        if not isinstance(value, bool):
            raise ValueError("Storyboard shot prompt_ready must be a boolean.")
        return value
    raise ValueError(f"Unsupported storyboard shot field: {field}")


def _storyboard_shot_column_value(field: str, value: Any) -> tuple[str, Any]:
    if field == "characters":
        return "characters_json", _json_or_none({"items": value})
    if field == "props":
        return "props_json", _json_or_none({"items": value})
    if field == "prompt_ready":
        return "prompt_ready", 1 if value else 0
    return field, value


def _storyboard_source_row(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    script = conn.execute(
        """
        SELECT updated_at
        FROM canvas_nodes
        WHERE project_id = ? AND node_key = 'script'
        """,
        (project_id,),
    ).fetchone()
    production = conn.execute(
        """
        SELECT updated_at
        FROM canvas_nodes
        WHERE project_id = ? AND node_key = 'production'
        """,
        (project_id,),
    ).fetchone()
    return {
        "project": project,
        "script_updated_at": script["updated_at"] if script is not None else None,
        "production_updated_at": production["updated_at"] if production is not None else None,
    }


def _ensure_storyboard_row(
    *,
    conn: sqlite3.Connection,
    project_id: int,
    status: str,
    model: str | None,
    source_script_updated_at: str | None,
    source_production_updated_at: str | None,
    error_message: str | None,
    now: str,
) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT
            id, project_id, status, model, generation_status, generation_started_at,
            generation_finished_at, generation_error_message, last_completed_at,
            last_completed_model, source_script_updated_at,
            source_production_updated_at, error_message, created_at, updated_at
        FROM storyboards
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if row is not None:
        return row
    cursor = conn.execute(
        """
        INSERT INTO storyboards(
            project_id, status, model, generation_status, generation_started_at,
            generation_finished_at, generation_error_message, last_completed_at,
            last_completed_model, source_script_updated_at, source_production_updated_at,
            error_message, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            status,
            model,
            status,
            now if status == "generating" else None,
            now if status in {"completed", "failed", "interrupted"} else None,
            error_message[:2000] if error_message else None,
            now if status == "completed" else None,
            model if status == "completed" else None,
            source_script_updated_at,
            source_production_updated_at,
            error_message[:2000] if error_message else None,
            now,
            now,
        ),
    )
    row = conn.execute(
        """
        SELECT
            id, project_id, status, model, generation_status, generation_started_at,
            generation_finished_at, generation_error_message, last_completed_at,
            last_completed_model, source_script_updated_at,
            source_production_updated_at, error_message, created_at, updated_at
        FROM storyboards
        WHERE id = ?
        """,
        (int(cursor.lastrowid),),
    ).fetchone()
    if row is None:
        raise RuntimeError("Storyboard could not be created.")
    return row


def _completed_storyboard_row(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row:
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
        raise RuntimeError("Storyboard shot editing requires a completed project.")
    row = conn.execute(
        """
        SELECT
            id, project_id, status, model, generation_status, generation_started_at,
            generation_finished_at, generation_error_message, last_completed_at,
            last_completed_model, source_script_updated_at,
            source_production_updated_at, error_message, created_at, updated_at
        FROM storyboards
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if row is None or row["last_completed_at"] is None:
        raise RuntimeError("Storyboard shot editing requires a completed storyboard.")
    shot_count = conn.execute(
        """
        SELECT COUNT(*) AS shot_count
        FROM storyboard_shots
        WHERE storyboard_id = ?
        """,
        (row["id"],),
    ).fetchone()
    if shot_count is None or int(shot_count["shot_count"]) == 0:
        raise RuntimeError("Storyboard shot editing requires completed storyboard shots.")
    return row


def _project_storyboard_shot(
    conn: sqlite3.Connection,
    project_id: int,
    shot_id: int,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT s.id, s.sequence_index, s.image_prompt
        FROM storyboard_shots s
        JOIN storyboards sb ON sb.id = s.storyboard_id
        WHERE s.id = ? AND sb.project_id = ?
        """,
        (shot_id, project_id),
    ).fetchone()


def _storyboard_shot_order_rows(
    conn: sqlite3.Connection,
    storyboard_id: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, sequence_index
        FROM storyboard_shots
        WHERE storyboard_id = ?
        ORDER BY sequence_index, id
        """,
        (storyboard_id,),
    ).fetchall()


def _safe_resequence_storyboard_shots(
    conn: sqlite3.Connection,
    shot_ids: list[int],
    now: str,
    *,
    reset_prompt_ready: bool,
) -> None:
    temp_offset = len(shot_ids)
    for offset, shot_id in enumerate(shot_ids, start=1):
        conn.execute(
            """
            UPDATE storyboard_shots
            SET sequence_index = ?, updated_at = ?
            WHERE id = ?
            """,
            (-(temp_offset + offset), now, shot_id),
        )
    for sequence_index, shot_id in enumerate(shot_ids, start=1):
        conn.execute(
            """
            UPDATE storyboard_shots
            SET sequence_index = ?,
                prompt_ready = CASE WHEN ? THEN 0 ELSE prompt_ready END,
                updated_at = ?
            WHERE id = ?
            """,
            (sequence_index, 1 if reset_prompt_ready else 0, now, shot_id),
        )


def _touch_storyboard_project(
    conn: sqlite3.Connection,
    project_id: int,
    storyboard_id: int,
    now: str,
) -> None:
    conn.execute(
        """
        UPDATE storyboards
        SET updated_at = ?
        WHERE id = ?
        """,
        (now, storyboard_id),
    )
    conn.execute(
        """
        UPDATE projects
        SET updated_at = ?
        WHERE id = ?
        """,
        (now, project_id),
    )


def _storyboard_status_title(status: str) -> str:
    titles = {
        "not_started": "Storyboard initialized",
        "generating": "Storyboard generation started",
        "completed": "Storyboard generation completed",
        "failed": "Storyboard generation failed",
        "interrupted": "Storyboard generation interrupted",
    }
    return titles[status]


def _storyboard_status_description(status: str) -> str:
    descriptions = {
        "not_started": "Storyboard is ready for generation.",
        "generating": "Storyboard generation is running.",
        "completed": "Storyboard generation completed.",
        "failed": "Storyboard generation failed.",
        "interrupted": "Storyboard generation was interrupted before completion.",
    }
    return descriptions[status]


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


def _node_instruction_description(
    node_title: str, instructions: dict[str, Any] | None
) -> str:
    guidance = str((instructions or {}).get("guidance", "")).strip()
    if not guidance:
        return f"Cleared custom guidance for {node_title}."
    return f"Saved custom guidance for {node_title}: {guidance[:180]}"


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
