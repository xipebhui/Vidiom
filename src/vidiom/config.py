from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LANGUAGE_MODEL = "gpt-5.5"
IMAGE_MODEL = "gpt-image-2"


@dataclass(frozen=True)
class Settings:
    database_path: Path
    model_base_url: str | None
    language_model: str
    image_model: str
    batch_size: int
    schedule_minute: int
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_path=Path(os.getenv("VIDIOM_DATABASE_PATH", "./data/vidiom.sqlite3")),
            model_base_url=os.getenv("HM_BASE_URL"),
            language_model=LANGUAGE_MODEL,
            image_model=IMAGE_MODEL,
            batch_size=_int_env("VIDIOM_BATCH_SIZE", 3),
            schedule_minute=_int_env("VIDIOM_SCHEDULE_MINUTE", 0),
            log_level=os.getenv("VIDIOM_LOG_LEVEL", "INFO"),
        )


def require_model_base_url() -> str:
    value = os.getenv("HM_BASE_URL")
    if not value:
        raise RuntimeError("HM_BASE_URL is required before calling the model provider.")
    return value


def require_language_api_key() -> str:
    value = os.getenv("HM_LLM_APIKEY")
    if not value:
        raise RuntimeError("HM_LLM_APIKEY is required before running language agents.")
    return value


def require_image_api_key() -> str:
    value = os.getenv("HM_IMG_APIKEY")
    if not value:
        raise RuntimeError("HM_IMG_APIKEY is required before generating project images.")
    return value


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}.") from exc
