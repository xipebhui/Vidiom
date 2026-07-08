from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .canvas import OpenAICanvasAgent, create_canvas_project, run_canvas_project
from .config import Settings
from .storage import Storage

load_dotenv()

STATIC_DIR = Path(__file__).parent / "static"


class CreateProjectRequest(BaseModel):
    seed_text: str = Field(min_length=2, max_length=2000)


class UpdateProjectRequest(BaseModel):
    seed_text: str | None = Field(default=None, min_length=2, max_length=2000)
    title: str | None = Field(default=None, max_length=120)


class RunProjectResponse(BaseModel):
    project: dict


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
    project_id = create_canvas_project(storage, request.seed_text)
    return {"project": storage.get_project(project_id)}


@app.get("/api/projects/{project_id}")
def get_project(project_id: int, storage: Annotated[Storage, Depends(get_storage)]) -> dict:
    try:
        return {"project": storage.get_project(project_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/api/projects/{project_id}")
def update_project(
    project_id: int,
    request: UpdateProjectRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    if request.seed_text is None and request.title is None:
        raise HTTPException(status_code=400, detail="Provide seed_text or title.")
    try:
        storage.update_draft_project(
            project_id=project_id,
            seed_text=request.seed_text,
            title=request.title,
        )
        return {"project": storage.get_project(project_id)}
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
    return {"project": project}
