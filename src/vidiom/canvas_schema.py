from __future__ import annotations

PREMISE_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "one_sentence_pitch",
        "genre",
        "target_audience",
        "emotional_hook",
        "story_promise",
        "risk_flags",
    ],
    "properties": {
        "one_sentence_pitch": {"type": "string"},
        "genre": {"type": "string"},
        "target_audience": {"type": "string"},
        "emotional_hook": {"type": "string"},
        "story_promise": {"type": "string"},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
    },
}

CHARACTER_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["protagonist", "pressure", "relationship_map", "character_arcs"],
    "properties": {
        "protagonist": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "age", "desire", "wound", "choice"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 1, "maximum": 100},
                "desire": {"type": "string"},
                "wound": {"type": "string"},
                "choice": {"type": "string"},
            },
        },
        "pressure": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "form", "threat", "human_reason"],
            "properties": {
                "name": {"type": "string"},
                "form": {"type": "string"},
                "threat": {"type": "string"},
                "human_reason": {"type": "string"},
            },
        },
        "relationship_map": {"type": "array", "items": {"type": "string"}, "minItems": 3},
        "character_arcs": {"type": "array", "items": {"type": "string"}, "minItems": 3},
    },
}

BEAT_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["episode_title", "logline", "beats", "reversal", "cliffhanger"],
    "properties": {
        "episode_title": {"type": "string"},
        "logline": {"type": "string"},
        "beats": {
            "type": "array",
            "minItems": 6,
            "maxItems": 9,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["index", "beat", "screen_purpose"],
                "properties": {
                    "index": {"type": "integer", "minimum": 1},
                    "beat": {"type": "string"},
                    "screen_purpose": {"type": "string"},
                },
            },
        },
        "reversal": {"type": "string"},
        "cliffhanger": {"type": "string"},
    },
}

PRODUCTION_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["visual_style", "locations", "props", "shot_plan", "edit_notes"],
    "properties": {
        "visual_style": {"type": "string"},
        "locations": {"type": "array", "items": {"type": "string"}, "minItems": 2},
        "props": {"type": "array", "items": {"type": "string"}, "minItems": 3},
        "shot_plan": {
            "type": "array",
            "minItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["shot", "purpose", "duration_seconds"],
                "properties": {
                    "shot": {"type": "string"},
                    "purpose": {"type": "string"},
                    "duration_seconds": {"type": "integer", "minimum": 1, "maximum": 60},
                },
            },
        },
        "edit_notes": {"type": "array", "items": {"type": "string"}, "minItems": 3},
    },
}

