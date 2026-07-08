from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .canvas import OpenAICanvasAgent, create_canvas_project, run_canvas_project
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
def list_projects(storage: Annotated[Storage, Depends(get_storage)], limit: int = 20) -> dict:
    return {"projects": storage.list_projects(limit=limit)}


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
    storage: Annotated[Storage, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        project = run_canvas_project(
            storage=storage,
            project_id=project_id,
            agent=OpenAICanvasAgent(settings.openai_model),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"project": project, "activity": storage.get_project_activity(project_id)}


def _project_response(storage: Storage, project_id: int) -> dict:
    return {
        "project": storage.get_project(project_id),
        "activity": storage.get_project_activity(project_id),
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
