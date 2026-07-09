from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .canvas import (
    OpenAICanvasAgent,
    create_canvas_project,
    create_revision_project,
    run_canvas_project,
)
from .config import Settings
from .storage import Storage

load_dotenv()

STATIC_DIR = Path(__file__).parent / "static"


class CreativeBriefRequest(BaseModel):
    duration_minutes: int | None = Field(default=None, ge=1, le=15)
    aspect_ratio: str | None = Field(default=None, max_length=32)
    tone: str | None = Field(default=None, max_length=80)
    target_audience: str | None = Field(default=None, max_length=120)
    must_include: str | None = Field(default=None, max_length=500)


class CreateProjectRequest(BaseModel):
    seed_text: str = Field(min_length=2, max_length=2000)
    brief: CreativeBriefRequest | None = None


class UpdateProjectRequest(BaseModel):
    seed_text: str | None = Field(default=None, min_length=2, max_length=2000)
    title: str | None = Field(default=None, max_length=120)
    brief: CreativeBriefRequest | None = None


class RunProjectResponse(BaseModel):
    project: dict
    activity: list[dict]
    progress: dict


ProjectStatusFilter = Literal["draft", "running", "paused", "completed", "failed"]
RevisionStartNode = Literal["premise", "characters", "beats", "script", "production"]


class ReviseProjectRequest(BaseModel):
    start_node: RevisionStartNode


def get_settings() -> Settings:
    return Settings.from_env()


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> Storage:
    storage = Storage(settings.database_path)
    storage.migrate()
    return storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = Storage(Settings.from_env().database_path)
    storage.migrate()
    yield


app = FastAPI(title="Vidiom Studio", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    return {"status": "ok", "database_path": str(settings.database_path)}


@app.get("/api/projects")
def list_projects(
    storage: Annotated[Storage, Depends(get_storage)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    status: ProjectStatusFilter | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> dict:
    return {"projects": storage.list_projects(limit=limit, status=status, search=q)}


@app.post("/api/projects")
def create_project(
    request: CreateProjectRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    project_id = create_canvas_project(storage, request.seed_text, _brief_payload(request.brief))
    return _project_response(storage, project_id)


@app.get("/api/projects/{project_id}")
def get_project(project_id: int, storage: Annotated[Storage, Depends(get_storage)]) -> dict:
    try:
        return _project_response(storage, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/export")
def export_project(project_id: int, storage: Annotated[Storage, Depends(get_storage)]) -> Response:
    try:
        payload = storage.export_project_package(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    filename = _export_filename(payload)
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@app.post("/api/projects/{project_id}/duplicate")
def duplicate_project(
    project_id: int,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    try:
        source = storage.get_project(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    duplicate_id = create_canvas_project(
        storage=storage,
        seed_text=str(source["seed_text"]),
        brief=source["brief"],
    )
    duplicate_title = _duplicate_title(source["title"])
    if duplicate_title is not None:
        storage.update_project_title(duplicate_id, duplicate_title)
    return _project_response(storage, duplicate_id)


@app.post("/api/projects/{project_id}/revise")
def revise_project(
    project_id: int,
    request: ReviseProjectRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    try:
        source = storage.get_project(project_id)
        revision_id = create_revision_project(storage, project_id, request.start_node)
        storage.update_project_title(
            revision_id,
            _revision_title(source["title"], request.start_node),
        )
        return _project_response(storage, revision_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/reset")
def reset_project(
    project_id: int,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    try:
        storage.reset_failed_project(project_id)
        return _project_response(storage, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/pause")
def pause_project(
    project_id: int,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    try:
        storage.pause_running_project(project_id)
        return _project_response(storage, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/projects/{project_id}")
def update_project(
    project_id: int,
    request: UpdateProjectRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    if request.seed_text is None and request.title is None and request.brief is None:
        raise HTTPException(status_code=400, detail="Provide seed_text, title, or brief.")
    try:
        storage.update_draft_project(
            project_id=project_id,
            seed_text=request.seed_text,
            title=request.title,
            brief=_brief_payload(request.brief),
        )
        return _project_response(storage, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/run", response_model=RunProjectResponse)
def run_project(
    project_id: int,
    background_tasks: BackgroundTasks,
    storage: Annotated[Storage, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        project = storage.get_project(project_id)
        if project["status"] == "running":
            raise RuntimeError("Project is already running.")
        if project["status"] == "paused" and _project_progress(project)["active_key"] is not None:
            raise RuntimeError("Project is still pausing after the active node.")
        storage.update_project_status(project_id, "running")
        background_tasks.add_task(
            _run_project_job,
            settings.database_path,
            project_id,
            settings.openai_model,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _project_response(storage, project_id)


def _project_response(storage: Storage, project_id: int) -> dict:
    project = storage.get_project(project_id)
    return {
        "project": project,
        "activity": storage.get_project_activity(project_id),
        "progress": _project_progress(project),
    }


def _run_project_job(database_path: Path, project_id: int, model: str) -> None:
    storage = Storage(database_path)
    storage.migrate()
    run_canvas_project(
        storage=storage,
        project_id=project_id,
        agent=OpenAICanvasAgent(model),
    )


def _project_progress(project: dict) -> dict:
    agent_nodes = [node for node in project["nodes"] if node["kind"] == "agent"]
    active = next((node for node in agent_nodes if node["status"] == "running"), None)
    completed_count = sum(1 for node in agent_nodes if node["status"] == "completed")
    failed = next((node for node in agent_nodes if node["status"] == "failed"), None)
    return {
        "completed": completed_count,
        "total": len(agent_nodes),
        "active_key": active["key"] if active is not None else None,
        "active_title": active["title"] if active is not None else None,
        "failed_key": failed["key"] if failed is not None else None,
        "failed_title": failed["title"] if failed is not None else None,
    }


def _brief_payload(brief: CreativeBriefRequest | None) -> dict | None:
    if brief is None:
        return None
    payload: dict = {}
    for key, value in brief.model_dump(exclude_none=True).items():
        if isinstance(value, str):
            clean_value = value.strip()
            if clean_value:
                payload[key] = clean_value
        else:
            payload[key] = value
    return payload or None


def _export_filename(payload: dict) -> str:
    project = payload["project"]
    raw_title = str(project["title"])
    safe_title = "".join(
        character.lower() if character.isalnum() else "-"
        for character in raw_title.strip()
    ).strip("-")
    return f"vidiom-{safe_title}.json"


def _duplicate_title(title: str | None) -> str | None:
    if title is None:
        return None
    clean_title = title.strip()
    if not clean_title:
        return None
    suffix = " Copy"
    return f"{clean_title[: 120 - len(suffix)]}{suffix}"


def _revision_title(title: str | None, start_node: str) -> str:
    clean_title = title.strip() if title else "Untitled"
    label = start_node.replace("_", " ").title()
    suffix = f" {label} Revision"
    return f"{clean_title[: 120 - len(suffix)]}{suffix}"
