from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .canvas import OpenAICanvasAgent, create_canvas_project, run_canvas_project
from .config import Settings
from .providers import (
    ImageGenerationClient,
    LanguageJSONClient,
    OpenAICompatibleImageClient,
    OpenAICompatibleLanguageClient,
)
from .storage import Storage
from .storyboard import generate_project_storyboard

SMOKE_STAGE_STATUSES = {
    "not_started",
    "running",
    "completed",
    "failed",
    "interrupted",
    "incomplete",
}

SMOKE_STAGES = (
    "agent_project",
    "storyboard_generation",
    "project_image_generation",
    "export_package",
)

DEFAULT_SMOKE_RESULT_PATH = Path("docs/real-model-smoke-result.md")

SMOKE_SEED_TEXT = (
    "一个剪辑师在客户素材里发现明早会发生的街口事故，必须在交片前决定是否公开素材救人。"
)

SMOKE_BRIEF = {
    "duration_minutes": 5,
    "aspect_ratio": "9:16 vertical",
    "tone": "强钩子、快反转、现实悬疑",
    "target_audience": "18-35 岁短剧用户",
    "must_include": "前三秒出现异常素材；结尾保留下一次倒计时。",
}

SMOKE_ACCEPTANCE_PRODUCT_REQUIREMENT = (
    "`docs/next-product-requirement.md` Real Model End-to-End Acceptance Gate, "
    "updated 2026-07-10 CST"
)

SMOKE_ACCEPTANCE_ARCHITECTURE_TASK = (
    "`docs/development-task-breakdown.md` Task 1 强化真实 smoke 发布门禁"
)


class SmokeStageError(RuntimeError):
    pass


@dataclass
class SmokeStageRecord:
    stage: str
    status: str = "not_started"
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    model: str | None = None
    summary: str = ""
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "model": self.model,
            "summary": self.summary,
            "error_message": self.error_message,
            "details": self.details,
        }


@dataclass
class RealModelSmokeRun:
    run_started_at: str
    result_path: str
    database_path: str
    language_model: str
    image_model: str
    run_finished_at: str | None = None
    duration_seconds: float | None = None
    overall_status: str = "running"
    project_id: int | None = None
    stages: dict[str, SmokeStageRecord] = field(
        default_factory=lambda: {stage: SmokeStageRecord(stage=stage) for stage in SMOKE_STAGES}
    )

    def start_stage(self, stage: str, *, model: str | None = None) -> None:
        record = self.stages[stage]
        record.status = "running"
        record.model = model
        record.started_at = utc_now()
        record.finished_at = None
        record.duration_seconds = None
        record.summary = ""
        record.error_message = None
        record.details = {}

    def complete_stage(
        self,
        stage: str,
        *,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._finish_stage(stage, status="completed", summary=summary, details=details)

    def fail_stage(
        self,
        stage: str,
        *,
        error: BaseException | str,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._finish_stage(
            stage,
            status="failed",
            summary=summary,
            error_message=sanitize_smoke_error(error),
            details=details,
        )

    def interrupt_stage(self, stage: str) -> None:
        self._finish_stage(
            stage,
            status="interrupted",
            summary="Smoke run was interrupted before this stage completed.",
            error_message="Interrupted by user or external process.",
        )

    def mark_remaining_incomplete(self, after_stage: str, reason: str) -> None:
        should_mark = False
        for stage in SMOKE_STAGES:
            if should_mark and self.stages[stage].status == "not_started":
                self.stages[stage].status = "incomplete"
                self.stages[stage].summary = reason
            if stage == after_stage:
                should_mark = True

    def finish(self, status: str) -> None:
        now = utc_now()
        self.run_finished_at = now
        self.duration_seconds = duration_seconds(self.run_started_at, now)
        self.overall_status = status

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_started_at": self.run_started_at,
            "run_finished_at": self.run_finished_at,
            "duration_seconds": self.duration_seconds,
            "overall_status": self.overall_status,
            "project_id": self.project_id,
            "database_path": self.database_path,
            "result_path": self.result_path,
            "models": {
                "language": self.language_model,
                "image": self.image_model,
            },
            "stages": [self.stages[stage].as_dict() for stage in SMOKE_STAGES],
        }

    def _finish_stage(
        self,
        stage: str,
        *,
        status: str,
        summary: str,
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if status not in SMOKE_STAGE_STATUSES:
            raise ValueError(f"Unsupported smoke status: {status}")
        record = self.stages[stage]
        now = utc_now()
        record.status = status
        record.finished_at = now
        record.duration_seconds = (
            duration_seconds(record.started_at, now) if record.started_at is not None else None
        )
        record.summary = summary
        record.error_message = error_message
        record.details = details or {}


def run_real_model_storyboard_smoke(
    *,
    result_path: Path = DEFAULT_SMOKE_RESULT_PATH,
    database_path: Path | None = None,
    settings: Settings | None = None,
    language_client: LanguageJSONClient | None = None,
    image_client: ImageGenerationClient | None = None,
    language_client_factory: Callable[[], LanguageJSONClient] | None = None,
    image_client_factory: Callable[[], ImageGenerationClient] | None = None,
) -> dict[str, Any]:
    settings = settings or Settings.from_env()
    resolved_database_path = database_path or _temporary_database_path()
    result = RealModelSmokeRun(
        run_started_at=utc_now(),
        result_path=str(result_path),
        database_path=str(resolved_database_path),
        language_model=settings.language_model,
        image_model=settings.image_model,
    )
    storage = Storage(resolved_database_path)
    storage.migrate()
    active_stage = SMOKE_STAGES[0]

    try:
        active_stage = "agent_project"
        result.start_stage(active_stage, model=settings.language_model)
        language = language_client or _build_language_client(language_client_factory)
        project_id = create_canvas_project(storage, SMOKE_SEED_TEXT, SMOKE_BRIEF)
        result.project_id = project_id
        project = run_canvas_project(
            storage=storage,
            project_id=project_id,
            agent=OpenAICanvasAgent(settings.language_model, language),
        )
        _ensure_agent_project_completed(project)
        agent_counts = _agent_node_counts(project)
        result.complete_stage(
            active_stage,
            summary=(
                f"Agent project completed {agent_counts['completed']}/"
                f"{agent_counts['total']} nodes."
            ),
            details={
                "project_id": project_id,
                "title": project["title"],
                "agent_nodes": agent_counts,
            },
        )

        active_stage = "storyboard_generation"
        result.start_stage(active_stage, model=settings.language_model)
        storage.update_project_storyboard_status(
            project_id,
            status="generating",
            model=settings.language_model,
        )
        storyboard = generate_project_storyboard(
            storage=storage,
            project_id=project_id,
            model=settings.language_model,
            client=language,
        )
        _ensure_storyboard_completed(storyboard)
        storyboard_counts = _storyboard_counts(storyboard)
        result.complete_stage(
            active_stage,
            summary=(
                f"Storyboard completed with {storyboard_counts['shot_count']} shots and "
                f"{storyboard_counts['asset_count']} assets."
            ),
            details=storyboard_counts,
        )

        active_stage = "project_image_generation"
        result.start_stage(active_stage, model=settings.image_model)
        prompt = _image_prompt_from_storyboard(storyboard)
        try:
            image = image_client or _build_image_client(image_client_factory)
            image_result = image.generate_image(model=settings.image_model, prompt=prompt)
            image_asset_id = storage.create_generated_image_asset(
                project_id=project_id,
                prompt=prompt,
                model=settings.image_model,
                status="completed",
                artifact_url=image_result.artifact_url,
                b64_json=image_result.b64_json,
                revised_prompt=image_result.revised_prompt,
                provider_response=image_result.provider_response,
            )
        except Exception as exc:
            storage.create_generated_image_asset(
                project_id=project_id,
                prompt=prompt,
                model=settings.image_model,
                status="failed",
                error_message=sanitize_smoke_error(exc),
            )
            raise
        result.complete_stage(
            active_stage,
            summary="Project image asset completed with gpt-image-2.",
            details={
                "image_asset_id": image_asset_id,
                "artifact_url_present": image_result.artifact_url is not None,
                "b64_json_present": image_result.b64_json is not None,
                "revised_prompt_present": image_result.revised_prompt is not None,
            },
        )

        active_stage = "export_package"
        result.start_stage(active_stage)
        package = storage.export_project_package(project_id)
        export_details = _validate_export_package(package)
        result.complete_stage(
            active_stage,
            summary="Export package contains completed storyboard and project image assets.",
            details=export_details,
        )
        result.finish("completed")
    except KeyboardInterrupt:
        if result.stages[active_stage].status == "running":
            result.interrupt_stage(active_stage)
        result.mark_remaining_incomplete(
            active_stage,
            "Not completed because the smoke run was interrupted.",
        )
        result.finish("interrupted")
    except Exception as exc:
        if result.stages[active_stage].status == "running":
            result.fail_stage(
                active_stage,
                error=exc,
                summary=f"{active_stage} failed before completion.",
            )
        result.mark_remaining_incomplete(
            active_stage,
            f"Not run because {active_stage} did not complete.",
        )
        result.finish("failed")
    finally:
        write_smoke_result_markdown(result.as_dict(), result_path)

    return result.as_dict()


def write_smoke_result_markdown(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stage_rows = "\n".join(_stage_table_row(stage) for stage in result["stages"])
    path.write_text(
        "\n".join(
            [
                "# Real Model Smoke Result",
                "",
                f"- Run started at: `{result['run_started_at']}`",
                f"- Run finished at: `{result['run_finished_at']}`",
                f"- Overall status: `{result['overall_status']}`",
                f"- Product requirement: {SMOKE_ACCEPTANCE_PRODUCT_REQUIREMENT}",
                f"- Architecture task: {SMOKE_ACCEPTANCE_ARCHITECTURE_TASK}",
                "- Acceptance scope: `smoke-real-model-storyboard` covers agent, Storyboard, "
                "project image and export package stages in one real end-to-end gate.",
                f"- Database path: `{result['database_path']}`",
                f"- Project ID: `{result['project_id']}`",
                f"- Language model: `{result['models']['language']}`",
                f"- Image model: `{result['models']['image']}`",
                "- Secret handling: `HM_BASE_URL`, `HM_LLM_APIKEY` and `HM_IMG_APIKEY` "
                "values are not written to this file.",
                "",
                "## Stage Results",
                "",
                "| Stage | Status | Model | Duration | Summary | Error |",
                "| --- | --- | --- | ---: | --- | --- |",
                stage_rows,
                "",
                "## Structured Result",
                "",
                "```json",
                json.dumps(result, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def smoke_gate_completed(result: dict[str, Any]) -> bool:
    if result.get("overall_status") != "completed":
        return False
    stages = {stage.get("stage"): stage for stage in result.get("stages", [])}
    return all(stages.get(stage, {}).get("status") == "completed" for stage in SMOKE_STAGES)


def sanitize_smoke_error(error: BaseException | str) -> str:
    message = str(error).strip() or error.__class__.__name__
    for env_name in ("HM_LLM_APIKEY", "HM_IMG_APIKEY", "HM_BASE_URL"):
        value = os.getenv(env_name)
        if value:
            message = message.replace(value, f"<{env_name}>")
    return message[:2000]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def duration_seconds(started_at: str, finished_at: str) -> float:
    started = datetime.fromisoformat(started_at)
    finished = datetime.fromisoformat(finished_at)
    return round((finished - started).total_seconds(), 3)


def _temporary_database_path() -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="vidiom-real-smoke-"))
    return temp_dir / "vidiom.sqlite3"


def _build_language_client(factory: Callable[[], LanguageJSONClient] | None) -> LanguageJSONClient:
    if factory is not None:
        return factory()
    return OpenAICompatibleLanguageClient.from_env()


def _build_image_client(
    factory: Callable[[], ImageGenerationClient] | None,
) -> ImageGenerationClient:
    if factory is not None:
        return factory()
    return OpenAICompatibleImageClient.from_env()


def _ensure_agent_project_completed(project: dict[str, Any]) -> None:
    if project["status"] != "completed":
        raise SmokeStageError(f"Agent project ended with status {project['status']}.")
    counts = _agent_node_counts(project)
    if counts["completed"] != counts["total"]:
        raise SmokeStageError(
            f"Agent project completed {counts['completed']}/{counts['total']} nodes."
        )


def _agent_node_counts(project: dict[str, Any]) -> dict[str, int]:
    agent_nodes = [node for node in project["nodes"] if node["kind"] == "agent"]
    return {
        "total": len(agent_nodes),
        "completed": sum(1 for node in agent_nodes if node["status"] == "completed"),
        "failed": sum(1 for node in agent_nodes if node["status"] == "failed"),
        "running": sum(1 for node in agent_nodes if node["status"] == "running"),
        "pending": sum(1 for node in agent_nodes if node["status"] == "pending"),
    }


def _ensure_storyboard_completed(storyboard: dict[str, Any] | None) -> None:
    if storyboard is None:
        raise SmokeStageError("Storyboard generation did not produce a persisted record.")
    metadata = storyboard["storyboard"]
    if metadata["generation_status"] != "completed" or not storyboard["has_completed_result"]:
        error = metadata.get("generation_error_message") or "Storyboard did not complete."
        raise SmokeStageError(error)
    if not storyboard["shots"]:
        raise SmokeStageError("Storyboard completed without shots.")


def _storyboard_counts(storyboard: dict[str, Any]) -> dict[str, Any]:
    return {
        "shot_count": len(storyboard["shots"]),
        "asset_count": len(storyboard["assets"]),
        "relationship_count": len(storyboard["relationships"]),
        "image_link_count": len(storyboard["image_links"]),
        "has_completed_result": storyboard["has_completed_result"],
        "latest_attempt_failed": storyboard["latest_attempt_failed"],
        "result_source": storyboard["result_source"],
    }


def _image_prompt_from_storyboard(storyboard: dict[str, Any]) -> str:
    first_shot = storyboard["shots"][0]
    prompt = str(first_shot["image_prompt"]).strip()
    if not prompt:
        raise SmokeStageError("First storyboard shot does not have an image prompt.")
    return prompt


def _validate_export_package(package: dict[str, Any]) -> dict[str, Any]:
    deliverables = package["deliverables"]
    storyboard = deliverables.get("storyboard")
    if storyboard is None:
        raise SmokeStageError("Export package does not contain a completed storyboard.")
    if not storyboard["has_completed_result"]:
        raise SmokeStageError("Export storyboard is not marked as a completed result.")
    if not storyboard["shots"]:
        raise SmokeStageError("Export storyboard does not contain shots.")
    if not storyboard["assets"]:
        raise SmokeStageError("Export storyboard does not contain story assets.")
    image_assets = deliverables.get("image_assets") or []
    if not image_assets:
        raise SmokeStageError("Export package does not contain project image assets.")
    return {
        "storyboard_generation_status": storyboard["storyboard"]["generation_status"],
        "storyboard_shot_count": len(storyboard["shots"]),
        "storyboard_asset_count": len(storyboard["assets"]),
        "storyboard_relationship_count": len(storyboard["relationships"]),
        "storyboard_image_link_count": len(storyboard["image_links"]),
        "project_image_asset_count": len(image_assets),
        "completed_project_image_asset_count": sum(
            1 for asset in image_assets if asset["status"] == "completed"
        ),
    }


def _stage_table_row(stage: dict[str, Any]) -> str:
    duration = "" if stage["duration_seconds"] is None else str(stage["duration_seconds"])
    return (
        f"| `{stage['stage']}` | `{stage['status']}` | "
        f"`{stage['model'] or ''}` | {duration} | "
        f"{_markdown_cell(stage['summary'])} | {_markdown_cell(stage['error_message'] or '')} |"
    )


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
