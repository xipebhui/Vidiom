from __future__ import annotations

from typing import Protocol

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .providers import LanguageJSONClient, OpenAICompatibleLanguageClient
from .schema import SHORT_DRAMA_SCHEMA, validate_short_drama


class ShortDramaGenerator(Protocol):
    def generate(self, inspiration_text: str) -> dict:
        ...


class OpenAIShortDramaGenerator:
    def __init__(self, model: str, client: LanguageJSONClient | None = None) -> None:
        self.model = model
        self.client = client

    def generate(self, inspiration_text: str) -> dict:
        client = self.client or OpenAICompatibleLanguageClient.from_env()
        payload = client.generate_json(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input_payload=build_user_prompt(inspiration_text),
            schema_name="short_drama",
            schema=SHORT_DRAMA_SCHEMA,
        )
        validate_short_drama(payload)
        return payload
