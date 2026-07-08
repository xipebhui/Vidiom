from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    openai_model: str
    batch_size: int
    schedule_minute: int
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_path=Path(os.getenv("VIDIOM_DATABASE_PATH", "./data/vidiom.sqlite3")),
            openai_model=os.getenv("VIDIOM_OPENAI_MODEL", "gpt-5.5"),
            batch_size=_int_env("VIDIOM_BATCH_SIZE", 3),
            schedule_minute=_int_env("VIDIOM_SCHEDULE_MINUTE", 0),
            log_level=os.getenv("VIDIOM_LOG_LEVEL", "INFO"),
        )


def require_openai_api_key() -> str:
    value = os.getenv("OPENAI_API_KEY")
    if not value:
        raise RuntimeError("OPENAI_API_KEY is required before generating short dramas.")
    return value


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}.") from exc
