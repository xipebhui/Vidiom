from __future__ import annotations

from typing import Any

from .storyboard_schema import validate_storyboard_payload


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
