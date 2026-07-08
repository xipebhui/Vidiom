from __future__ import annotations

import json
from typing import Protocol

from .config import require_openai_api_key
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schema import SHORT_DRAMA_SCHEMA, validate_short_drama


class ShortDramaGenerator(Protocol):
    def generate(self, inspiration_text: str) -> dict:
        ...


class OpenAIShortDramaGenerator:
    def __init__(self, model: str) -> None:
        self.model = model

    def generate(self, inspiration_text: str) -> dict:
        from openai import OpenAI

        client = OpenAI(api_key=require_openai_api_key())
        response = client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=build_user_prompt(inspiration_text),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "short_drama",
                    "strict": True,
                    "schema": SHORT_DRAMA_SCHEMA,
                }
            },
        )
        payload = json.loads(response.output_text)
        validate_short_drama(payload)
        return payload
