from __future__ import annotations

import json
import os
from typing import Any

from .providers import LanguageJSONClient
from .storyboard_schema import STORYBOARD_SCHEMA, validate_storyboard_payload

STORYBOARD_GENERATION_INSTRUCTIONS = """
You are Vidiom's storyboard generation agent.
Generate a production storyboard from the provided project context.
Return only JSON that matches the supplied schema.
Every shot must be a concrete filming unit with beat linkage, characters, scene, props,
visual description, action focus, dialogue or sound, duration, aspect ratio, visual style,
an image generation prompt, and prompt readiness.
Assets must summarize reusable project characters, scenes, and props.
Relationships must connect shots to those assets.
Do not invent placeholder shots. Do not return prose outside the JSON object.
""".strip()


def normalize_storyboard_payload(payload: dict[str, Any]) -> dict[str, Any]:
    validate_storyboard_payload(payload)
    return {
        "shots": [_normalized_shot(shot) for shot in payload["shots"]],
        "assets": [_normalized_asset(asset) for asset in payload["assets"]],
        "relationships": [
            {
                "shot_sequence_index": int(relationship["shot_sequence_index"]),
                "asset_type": relationship["asset_type"],
                "asset_name": str(relationship["asset_name"]).strip(),
                "role": str(relationship["role"]).strip(),
            }
            for relationship in payload["relationships"]
        ],
    }


def _normalized_shot(shot: dict[str, Any]) -> dict[str, Any]:
    return {
        "sequence_index": int(shot["sequence_index"]),
        "review_status": str(shot.get("review_status", "pending")).strip() or "pending",
        "beat_ref": str(shot["beat_ref"]).strip(),
        "scene_ref": str(shot["scene_ref"]).strip(),
        "characters": _clean_string_list(shot["characters"]),
        "scene": str(shot["scene"]).strip(),
        "props": _clean_string_list(shot["props"]),
        "visual_description": str(shot["visual_description"]).strip(),
        "action_focus": str(shot["action_focus"]).strip(),
        "dialogue_or_sound": str(shot["dialogue_or_sound"]).strip(),
        "duration_seconds": int(shot["duration_seconds"]),
        "aspect_ratio": str(shot["aspect_ratio"]).strip(),
        "visual_style": str(shot["visual_style"]).strip(),
        "image_prompt": str(shot["image_prompt"]).strip(),
        "prompt_ready": bool(shot["prompt_ready"]),
    }


def _normalized_asset(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_type": str(asset["asset_type"]).strip(),
        "name": str(asset["name"]).strip(),
        "description": str(asset["description"]).strip(),
        "reference_prompt": str(asset["reference_prompt"]).strip(),
        "consistency_notes": str(asset["consistency_notes"]).strip(),
    }


def _clean_string_list(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


class StoryboardContextBuilder:
    def __init__(self, storage: Any) -> None:
        self.storage = storage

    def build(self, project_id: int) -> dict[str, Any]:
        project = self.storage.get_project(project_id)
        _ensure_project_ready_for_storyboard(project)
        nodes = {node["key"]: node for node in project["nodes"]}
        script = nodes["script"]["output"]
        production = nodes["production"]["output"]
        return {
            "project": {
                "id": project["id"],
                "title": project["title"],
                "seed_text": project["seed_text"],
                "brief": project["brief"],
                "status": project["status"],
            },
            "agent_outputs": {
                key: node["output"]
                for key, node in nodes.items()
                if node["kind"] == "agent" and node["output"] is not None
            },
            "reviewed_script": script,
            "reviewed_production_pack": production,
            "image_assets": [_image_asset_summary(asset) for asset in project["image_assets"]],
        }


class OpenAIStoryboardGenerator:
    def __init__(self, *, client: LanguageJSONClient, model: str) -> None:
        self.client = client
        self.model = model

    def generate(self, context: dict[str, Any]) -> dict[str, Any]:
        payload = self.client.generate_json(
            model=self.model,
            instructions=STORYBOARD_GENERATION_INSTRUCTIONS,
            input_payload=json.dumps(context, ensure_ascii=False, indent=2),
            schema_name="storyboard",
            schema=STORYBOARD_SCHEMA,
        )
        return normalize_storyboard_payload(payload)


def validate_project_ready_for_storyboard(storage: Any, project_id: int) -> None:
    project = storage.get_project(project_id)
    _ensure_project_ready_for_storyboard(project)


def generate_project_storyboard(
    *,
    storage: Any,
    project_id: int,
    model: str,
    client: LanguageJSONClient,
) -> dict[str, Any] | None:
    try:
        context = StoryboardContextBuilder(storage).build(project_id)
        payload = OpenAIStoryboardGenerator(client=client, model=model).generate(context)
        return storage.replace_project_storyboard(project_id, payload, model=model)
    except Exception as exc:
        storage.update_project_storyboard_status(
            project_id,
            status="failed",
            model=model,
            error_message=sanitize_storyboard_error(exc),
        )
        return storage.get_project_storyboard(project_id)


def sanitize_storyboard_error(error: Exception) -> str:
    message = str(error).strip() or error.__class__.__name__
    for env_name in ("HM_LLM_APIKEY", "HM_IMG_APIKEY", "HM_BASE_URL"):
        value = os.getenv(env_name)
        if value:
            message = message.replace(value, f"<{env_name}>")
    return message[:2000]


def _ensure_project_ready_for_storyboard(project: dict[str, Any]) -> None:
    if project["status"] != "completed":
        raise RuntimeError("Storyboard generation requires a completed project.")
    nodes = {node["key"]: node for node in project["nodes"]}
    script = nodes.get("script")
    production = nodes.get("production")
    if script is None or script["status"] != "completed" or script["output"] is None:
        raise RuntimeError("Storyboard generation requires completed Script output.")
    if production is None or production["status"] != "completed" or production["output"] is None:
        raise RuntimeError("Storyboard generation requires completed Production output.")


def _image_asset_summary(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": asset["id"],
        "prompt": asset["prompt"],
        "model": asset["model"],
        "status": asset["status"],
        "artifact_url": asset["artifact_url"],
        "revised_prompt": asset["revised_prompt"],
        "error_message": asset["error_message"],
        "created_at": asset["created_at"],
    }
