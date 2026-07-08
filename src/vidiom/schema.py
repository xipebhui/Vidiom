from __future__ import annotations

SHORT_DRAMA_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "title",
        "logline",
        "genre",
        "target_audience",
        "runtime_minutes",
        "content_rating",
        "tags",
        "characters",
        "story_engine",
        "episode_outline",
        "scenes",
        "production_notes",
    ],
    "properties": {
        "title": {"type": "string"},
        "logline": {"type": "string"},
        "genre": {"type": "string"},
        "target_audience": {"type": "string"},
        "runtime_minutes": {"type": "integer", "minimum": 1, "maximum": 12},
        "content_rating": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}, "minItems": 3},
        "characters": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "age", "role", "desire", "secret", "voice"],
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer", "minimum": 1, "maximum": 100},
                    "role": {"type": "string"},
                    "desire": {"type": "string"},
                    "secret": {"type": "string"},
                    "voice": {"type": "string"},
                },
            },
        },
        "story_engine": {
            "type": "object",
            "additionalProperties": False,
            "required": ["hook", "conflict", "turning_point", "climax", "ending"],
            "properties": {
                "hook": {"type": "string"},
                "conflict": {"type": "string"},
                "turning_point": {"type": "string"},
                "climax": {"type": "string"},
                "ending": {"type": "string"},
            },
        },
        "episode_outline": {
            "type": "array",
            "minItems": 5,
            "maxItems": 9,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["beat", "purpose"],
                "properties": {
                    "beat": {"type": "string"},
                    "purpose": {"type": "string"},
                },
            },
        },
        "scenes": {
            "type": "array",
            "minItems": 4,
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["scene_number", "setting", "time", "summary", "dialogue"],
                "properties": {
                    "scene_number": {"type": "integer", "minimum": 1},
                    "setting": {"type": "string"},
                    "time": {"type": "string"},
                    "summary": {"type": "string"},
                    "dialogue": {
                        "type": "array",
                        "minItems": 2,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["speaker", "line", "direction"],
                            "properties": {
                                "speaker": {"type": "string"},
                                "line": {"type": "string"},
                                "direction": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "production_notes": {
            "type": "object",
            "additionalProperties": False,
            "required": ["locations", "props", "shooting_style", "risk_flags"],
            "properties": {
                "locations": {"type": "array", "items": {"type": "string"}},
                "props": {"type": "array", "items": {"type": "string"}},
                "shooting_style": {"type": "string"},
                "risk_flags": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


def validate_short_drama(payload: dict) -> None:
    required = set(SHORT_DRAMA_SCHEMA["required"])
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"Generated short drama is missing required fields: {missing}")
    if not str(payload.get("title", "")).strip():
        raise ValueError("Generated short drama must contain a non-empty title.")
    if len(str(payload.get("logline", "")).strip()) < 10:
        raise ValueError("Generated short drama must contain a useful logline.")
    if not isinstance(payload.get("scenes"), list) or len(payload["scenes"]) < 4:
        raise ValueError("Generated short drama must contain at least 4 scenes.")
    if not isinstance(payload.get("characters"), list) or len(payload["characters"]) < 2:
        raise ValueError("Generated short drama must contain at least 2 characters.")
    for scene in payload["scenes"]:
        dialogue = scene.get("dialogue") if isinstance(scene, dict) else None
        if not isinstance(dialogue, list) or len(dialogue) < 2:
            raise ValueError("Each scene must contain at least 2 dialogue lines.")
