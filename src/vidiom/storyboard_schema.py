from __future__ import annotations

from typing import Any

STORYBOARD_ASSET_TYPES = {"character", "scene", "prop"}
STORYBOARD_REVIEW_STATUSES = {"pending", "needs_changes", "approved"}
STORYBOARD_STATUSES = {"not_started", "generating", "completed", "failed"}
STORYBOARD_IMAGE_LINK_TYPES = {"reference", "storyboard_frame"}

STORYBOARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["shots", "assets", "relationships"],
    "properties": {
        "shots": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "sequence_index",
                    "review_status",
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
                    "prompt_ready",
                ],
                "properties": {
                    "sequence_index": {"type": "integer", "minimum": 1},
                    "review_status": {
                        "type": "string",
                        "enum": sorted(STORYBOARD_REVIEW_STATUSES),
                    },
                    "beat_ref": {"type": "string"},
                    "scene_ref": {"type": "string"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "scene": {"type": "string"},
                    "props": {"type": "array", "items": {"type": "string"}},
                    "visual_description": {"type": "string"},
                    "action_focus": {"type": "string"},
                    "dialogue_or_sound": {"type": "string"},
                    "duration_seconds": {"type": "integer", "minimum": 1, "maximum": 120},
                    "aspect_ratio": {"type": "string"},
                    "visual_style": {"type": "string"},
                    "image_prompt": {"type": "string"},
                    "prompt_ready": {"type": "boolean"},
                },
            },
        },
        "assets": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "asset_type",
                    "name",
                    "description",
                    "reference_prompt",
                    "consistency_notes",
                ],
                "properties": {
                    "asset_type": {"type": "string", "enum": sorted(STORYBOARD_ASSET_TYPES)},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "reference_prompt": {"type": "string"},
                    "consistency_notes": {"type": "string"},
                },
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["shot_sequence_index", "asset_type", "asset_name", "role"],
                "properties": {
                    "shot_sequence_index": {"type": "integer", "minimum": 1},
                    "asset_type": {"type": "string", "enum": sorted(STORYBOARD_ASSET_TYPES)},
                    "asset_name": {"type": "string"},
                    "role": {"type": "string"},
                },
            },
        },
    },
}


def validate_storyboard_payload(payload: dict[str, Any]) -> None:
    missing = sorted({"shots", "assets", "relationships"} - set(payload))
    if missing:
        raise ValueError(f"Storyboard payload is missing required fields: {missing}")

    shots = payload.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("Storyboard payload must contain at least one shot.")
    sequence_indexes: set[int] = set()
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError("Each storyboard shot must be an object.")
        _validate_shot(shot)
        sequence_index = int(shot["sequence_index"])
        if sequence_index in sequence_indexes:
            raise ValueError("Storyboard shot sequence indexes must be unique.")
        sequence_indexes.add(sequence_index)

    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Storyboard assets must be a list.")
    asset_keys: set[tuple[str, str]] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise ValueError("Each storyboard asset must be an object.")
        _validate_asset(asset)
        asset_name = _clean_required_string(asset.get("name"), "asset name")
        asset_keys.add((asset["asset_type"], asset_name))

    relationships = payload.get("relationships")
    if not isinstance(relationships, list):
        raise ValueError("Storyboard relationships must be a list.")
    for relationship in relationships:
        if not isinstance(relationship, dict):
            raise ValueError("Each storyboard relationship must be an object.")
        sequence_index = relationship.get("shot_sequence_index")
        if not isinstance(sequence_index, int) or sequence_index not in sequence_indexes:
            raise ValueError("Storyboard relationship references an unknown shot.")
        asset_type = relationship.get("asset_type")
        if asset_type not in STORYBOARD_ASSET_TYPES:
            raise ValueError("Storyboard relationship contains an invalid asset type.")
        asset_name = _clean_required_string(relationship.get("asset_name"), "asset name")
        if (asset_type, asset_name) not in asset_keys:
            raise ValueError("Storyboard relationship references an unknown asset.")
        _clean_required_string(relationship.get("role"), "relationship role")


def _validate_shot(shot: dict[str, Any]) -> None:
    required = {
        "sequence_index",
        "review_status",
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
        "prompt_ready",
    }
    missing = sorted(required - set(shot))
    if missing:
        raise ValueError(f"Storyboard shot is missing required fields: {missing}")
    if not isinstance(shot["sequence_index"], int) or shot["sequence_index"] < 1:
        raise ValueError("Storyboard shot sequence_index must be a positive integer.")
    review_status = shot.get("review_status", "pending")
    if review_status not in STORYBOARD_REVIEW_STATUSES:
        raise ValueError("Storyboard shot contains an invalid review status.")
    _clean_required_string(shot.get("beat_ref"), "shot beat_ref")
    _clean_required_string(shot.get("scene_ref"), "shot scene_ref")
    _clean_required_string(shot.get("scene"), "shot scene")
    _clean_required_string(shot.get("visual_description"), "shot visual description")
    _clean_required_string(shot.get("action_focus"), "shot action focus")
    _clean_required_string(shot.get("dialogue_or_sound"), "shot dialogue or sound")
    _clean_required_string(shot.get("aspect_ratio"), "shot aspect ratio")
    _clean_required_string(shot.get("visual_style"), "shot visual style")
    _clean_required_string(shot.get("image_prompt"), "shot image prompt")
    _clean_string_list(shot.get("characters"), "shot characters")
    _clean_string_list(shot.get("props"), "shot props")
    duration = shot.get("duration_seconds")
    if not isinstance(duration, int) or duration < 1 or duration > 120:
        raise ValueError("Storyboard shot duration must be 1-120 seconds.")
    if not isinstance(shot.get("prompt_ready"), bool):
        raise ValueError("Storyboard shot prompt_ready must be a boolean.")


def _validate_asset(asset: dict[str, Any]) -> None:
    required = {"asset_type", "name", "description", "reference_prompt", "consistency_notes"}
    missing = sorted(required - set(asset))
    if missing:
        raise ValueError(f"Storyboard asset is missing required fields: {missing}")
    if asset.get("asset_type") not in STORYBOARD_ASSET_TYPES:
        raise ValueError("Storyboard asset contains an invalid asset type.")
    _clean_required_string(asset.get("name"), "asset name")
    _clean_required_string(asset.get("description"), "asset description")
    _clean_required_string(asset.get("reference_prompt"), "asset reference prompt")
    if not isinstance(asset.get("consistency_notes"), str):
        raise ValueError("Storyboard asset consistency notes must be a string.")


def _clean_required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Storyboard {label} cannot be empty.")
    return value.strip()


def _clean_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Storyboard {label} must be a string list.")
    return [item.strip() for item in value if item.strip()]
