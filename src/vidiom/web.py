from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
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
from .providers import (
    ImageGenerationClient,
    LanguageJSONClient,
    OpenAICompatibleImageClient,
    OpenAICompatibleLanguageClient,
)
from .schema import validate_short_drama
from .storage import Storage
from .storyboard import (
    generate_project_storyboard,
    sanitize_storyboard_error,
    validate_project_ready_for_storyboard,
)

load_dotenv()

STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger(__name__)


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
    runtime: dict


ProjectStatusFilter = Literal["draft", "running", "paused", "completed", "failed"]
RevisionStartNode = Literal["premise", "characters", "beats", "script", "production"]
AgentNodeKey = Literal["premise", "characters", "beats", "script", "production"]
ReleaseStatus = Literal["ready", "needs_edits", "blocked"]
ReviewActionStatus = Literal["open", "done", "blocked"]
StoryboardReviewStatus = Literal["pending", "needs_changes", "approved"]
StoryboardImageLinkType = Literal["reference", "storyboard_frame"]


class ReviseProjectRequest(BaseModel):
    start_node: RevisionStartNode


class UpdateScriptRequest(BaseModel):
    script: dict


class UpdateNodeInstructionsRequest(BaseModel):
    guidance: str = Field(default="", max_length=1000)


class ProductionShotRequest(BaseModel):
    shot: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=300)
    duration_seconds: int = Field(ge=1, le=60)


class UpdateProductionRequest(BaseModel):
    visual_style: str = Field(min_length=1, max_length=300)
    locations: list[str] = Field(min_length=2, max_length=20)
    props: list[str] = Field(min_length=3, max_length=30)
    shot_plan: list[ProductionShotRequest] = Field(min_length=5, max_length=40)
    edit_notes: list[str] = Field(min_length=3, max_length=30)


class ReviewActionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    status: ReviewActionStatus = "open"


class UpdateReviewNotesRequest(BaseModel):
    release_status: ReleaseStatus
    summary: str = Field(min_length=1, max_length=500)
    next_actions: list[str] = Field(default_factory=list, max_length=10)
    approval_notes: list[str] = Field(default_factory=list, max_length=10)
    action_items: list[ReviewActionRequest] = Field(default_factory=list, max_length=20)


class GenerateImageRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=2000)


class StoryboardShotReviewItem(BaseModel):
    shot_id: int
    review_status: StoryboardReviewStatus
    prompt_ready: bool


class StoryboardShotReviewRequest(BaseModel):
    reviews: list[StoryboardShotReviewItem] = Field(min_length=1, max_length=100)


class StoryboardGenerateResponse(BaseModel):
    storyboard: dict


def get_settings() -> Settings:
    return Settings.from_env()


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> Storage:
    storage = Storage(settings.database_path)
    storage.migrate()
    return storage


def get_image_client() -> ImageGenerationClient:
    return OpenAICompatibleImageClient.from_env()


def get_language_client() -> LanguageJSONClient:
    return OpenAICompatibleLanguageClient.from_env()


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


@app.patch("/api/projects/{project_id}/script")
def update_project_script(
    project_id: int,
    request: UpdateScriptRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    try:
        validate_short_drama(request.script)
        storage.update_completed_project_script(project_id, request.script)
        return _project_response(storage, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/projects/{project_id}/nodes/{node_key}/instructions")
def update_node_instructions(
    project_id: int,
    node_key: AgentNodeKey,
    request: UpdateNodeInstructionsRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    try:
        storage.update_canvas_node_instructions(
            project_id,
            node_key,
            _node_instructions_payload(request),
        )
        return _project_response(storage, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/projects/{project_id}/production")
def update_project_production(
    project_id: int,
    request: UpdateProductionRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    try:
        storage.update_completed_project_production(
            project_id,
            _production_payload(request),
        )
        return _project_response(storage, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/projects/{project_id}/review-notes")
def update_project_review_notes(
    project_id: int,
    request: UpdateReviewNotesRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    try:
        storage.update_completed_project_review_notes(
            project_id,
            _review_notes_payload(request),
        )
        return _project_response(storage, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/images")
def generate_project_image(
    project_id: int,
    request: GenerateImageRequest,
    storage: Annotated[Storage, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    image_client: Annotated[ImageGenerationClient, Depends(get_image_client)],
) -> dict:
    prompt = request.prompt.strip()
    try:
        storage.get_project(project_id)
        result = image_client.generate_image(model=settings.image_model, prompt=prompt)
        storage.create_generated_image_asset(
            project_id=project_id,
            prompt=prompt,
            model=settings.image_model,
            status="completed",
            artifact_url=result.artifact_url,
            b64_json=result.b64_json,
            revised_prompt=result.revised_prompt,
            provider_response=result.provider_response,
        )
        return _project_response(storage, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        try:
            storage.create_generated_image_asset(
                project_id=project_id,
                prompt=prompt,
                model=settings.image_model,
                status="failed",
                error_message=str(exc),
            )
            return _project_response(storage, project_id)
        except LookupError as lookup_exc:
            raise HTTPException(status_code=404, detail=str(lookup_exc)) from lookup_exc


@app.get("/api/projects/{project_id}/storyboard")
def get_project_storyboard(
    project_id: int,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    try:
        return _storyboard_response(storage, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/api/projects/{project_id}/storyboard/generate",
    response_model=StoryboardGenerateResponse,
)
def generate_storyboard(
    project_id: int,
    background_tasks: BackgroundTasks,
    storage: Annotated[Storage, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        validate_project_ready_for_storyboard(storage, project_id)
        storage.update_project_storyboard_status(
            project_id,
            status="generating",
            model=settings.language_model,
        )
        background_tasks.add_task(
            _generate_storyboard_job,
            settings.database_path,
            project_id,
            settings.language_model,
        )
        return {"storyboard": _storyboard_response(storage, project_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/projects/{project_id}/storyboard/shots/review")
def update_storyboard_shot_reviews(
    project_id: int,
    request: StoryboardShotReviewRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> dict:
    try:
        storage.update_storyboard_shot_reviews(
            project_id,
            [item.model_dump() for item in request.reviews],
        )
        return {"storyboard": _storyboard_response(storage, project_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/storyboard/shots/{shot_id}/image-assets/{asset_id}")
def link_storyboard_image_asset(
    project_id: int,
    shot_id: int,
    asset_id: int,
    storage: Annotated[Storage, Depends(get_storage)],
    link_type: StoryboardImageLinkType = "reference",
) -> dict:
    try:
        storage.link_storyboard_shot_image_asset(
            project_id,
            shot_id,
            asset_id,
            link_type=link_type,
        )
        return {"storyboard": _storyboard_response(storage, project_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/projects/{project_id}/storyboard/shots/{shot_id}/image-assets/{asset_id}")
def unlink_storyboard_image_asset(
    project_id: int,
    shot_id: int,
    asset_id: int,
    storage: Annotated[Storage, Depends(get_storage)],
    link_type: StoryboardImageLinkType = "reference",
) -> dict:
    try:
        storage.delete_storyboard_shot_image_asset(
            project_id,
            shot_id,
            asset_id,
            link_type=link_type,
        )
        return {"storyboard": _storyboard_response(storage, project_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
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
            settings.language_model,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _project_response(storage, project_id)


def _project_response(storage: Storage, project_id: int) -> dict:
    project = storage.get_project(project_id)
    activity = storage.get_project_activity(project_id)
    return {
        "project": project,
        "activity": activity,
        "progress": _project_progress(project),
        "runtime": _project_runtime(project, activity),
    }


def _storyboard_response(storage: Storage, project_id: int) -> dict:
    project = storage.get_project(project_id)
    storyboard = storage.get_project_storyboard(project_id)
    if storyboard is None:
        storyboard = {
            "storyboard": {
                "id": None,
                "project_id": project_id,
                "status": "not_started",
                "model": None,
                "generation_status": "not_started",
                "generation_started_at": None,
                "generation_finished_at": None,
                "generation_error_message": None,
                "last_completed_at": None,
                "last_completed_model": None,
                "source_script_updated_at": None,
                "source_production_updated_at": None,
                "error_message": None,
                "created_at": None,
                "updated_at": None,
            },
            "shots": [],
            "assets": [],
            "relationships": [],
            "image_links": [],
            "has_completed_result": False,
            "latest_attempt_failed": False,
            "latest_attempt_interrupted": False,
            "result_source": None,
        }
    storyboard["image_assets"] = [
        {
            "id": asset["id"],
            "prompt": asset["prompt"],
            "model": asset["model"],
            "status": asset["status"],
            "artifact_url": asset["artifact_url"],
            "revised_prompt": asset["revised_prompt"],
            "error_message": asset["error_message"],
            "created_at": asset["created_at"],
        }
        for asset in project["image_assets"]
    ]
    return storyboard


def _run_project_job(database_path: Path, project_id: int, model: str) -> None:
    storage = Storage(database_path)
    storage.migrate()
    try:
        run_canvas_project(
            storage=storage,
            project_id=project_id,
            agent=OpenAICanvasAgent(model),
        )
    except Exception:
        logger.exception("Canvas project %s background run failed.", project_id)


def _generate_storyboard_job(database_path: Path, project_id: int, model: str) -> None:
    storage = Storage(database_path)
    storage.migrate()
    try:
        generate_project_storyboard(
            storage=storage,
            project_id=project_id,
            model=model,
            client=get_language_client(),
        )
    except KeyboardInterrupt:
        storage.update_project_storyboard_status(
            project_id,
            status="interrupted",
            model=model,
            error_message="Interrupted by user or external process.",
        )
        logger.exception("Storyboard project %s background generation interrupted.", project_id)
    except Exception as exc:
        try:
            storage.update_project_storyboard_status(
                project_id,
                status="failed",
                model=model,
                error_message=sanitize_storyboard_error(exc),
            )
        except Exception:
            logger.exception("Storyboard project %s failure state could not be saved.", project_id)
        logger.exception("Storyboard project %s background generation failed.", project_id)


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


def _project_runtime(project: dict, activity: list[dict]) -> dict:
    now = datetime.now(UTC)
    status_events = [
        item
        for item in activity
        if item["type"] == "status_change" and item.get("details") is not None
    ]
    run_starts = [
        item["occurred_at"]
        for item in status_events
        if item["details"].get("status") == "running"
    ]
    started_at = run_starts[-1] if run_starts else None
    finished_at = (
        project["updated_at"]
        if project["status"] in {"completed", "failed", "paused"}
        else None
    )
    elapsed_seconds = None
    if started_at is not None:
        end_at = now if project["status"] == "running" else _parse_timestamp(finished_at)
        elapsed_seconds = max(0, round((end_at - _parse_timestamp(started_at)).total_seconds()))

    active_node = _runtime_active_node(project, now)
    last_activity = _last_activity(activity)
    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed_seconds,
        "active_node": active_node,
        "last_activity": last_activity,
    }


def _runtime_active_node(project: dict, now: datetime) -> dict | None:
    active = next(
        (
            node
            for node in project["nodes"]
            if node["kind"] == "agent" and node["status"] == "running"
        ),
        None,
    )
    if active is None:
        return None
    started_at = active["updated_at"]
    return {
        "key": active["key"],
        "title": active["title"],
        "started_at": started_at,
        "elapsed_seconds": max(0, round((now - _parse_timestamp(started_at)).total_seconds())),
    }


def _last_activity(activity: list[dict]) -> dict | None:
    if not activity:
        return None
    candidates = [
        item
        for item in activity
        if not (item["type"] == "node" and item["status"] == "pending")
    ]
    if not candidates:
        candidates = activity
    _, latest = max(
        enumerate(candidates),
        key=lambda indexed: (_parse_timestamp(indexed[1]["occurred_at"]), indexed[0]),
    )
    return {
        "type": latest["type"],
        "title": latest["title"],
        "status": latest["status"],
        "occurred_at": latest["occurred_at"],
    }


def _parse_timestamp(value: str | None) -> datetime:
    if value is None:
        raise ValueError("Timestamp is required.")
    return datetime.fromisoformat(value)


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


def _production_payload(request: UpdateProductionRequest) -> dict:
    payload = request.model_dump()
    payload["visual_style"] = payload["visual_style"].strip()
    payload["locations"] = _clean_string_list(payload["locations"])
    payload["props"] = _clean_string_list(payload["props"])
    payload["edit_notes"] = _clean_string_list(payload["edit_notes"])
    for shot in payload["shot_plan"]:
        shot["shot"] = shot["shot"].strip()
        shot["purpose"] = shot["purpose"].strip()
    return payload


def _review_notes_payload(request: UpdateReviewNotesRequest) -> dict:
    payload = request.model_dump()
    payload["summary"] = payload["summary"].strip()
    payload["next_actions"] = _clean_optional_string_list(payload["next_actions"])
    payload["approval_notes"] = _clean_optional_string_list(payload["approval_notes"])
    payload["action_items"] = _review_action_payloads(payload["action_items"])
    if not payload["summary"]:
        raise ValueError("Review summary cannot be empty.")
    return payload


def _node_instructions_payload(request: UpdateNodeInstructionsRequest) -> dict | None:
    guidance = request.guidance.strip()
    if not guidance:
        return None
    return {"guidance": guidance}


def _clean_string_list(values: list[str]) -> list[str]:
    cleaned = [value.strip() for value in values]
    if any(not value for value in cleaned):
        raise ValueError("Production pack lists cannot contain empty items.")
    return cleaned


def _clean_optional_string_list(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


def _review_action_payloads(values: list[dict]) -> list[dict]:
    actions = []
    for value in values:
        text = str(value["text"]).strip()
        if not text:
            raise ValueError("Review action text cannot be empty.")
        actions.append({"text": text, "status": value["status"]})
    return actions


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
