from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from .config import Settings
from .generator import OpenAIShortDramaGenerator
from .pipeline import run_once
from .storage import Storage


def start_scheduler(settings: Settings) -> None:
    logging.basicConfig(level=settings.log_level)
    storage = Storage(settings.database_path)
    storage.migrate()
    generator = OpenAIShortDramaGenerator(settings.openai_model)

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: run_once(storage, generator, settings.batch_size),
        trigger="cron",
        minute=settings.schedule_minute,
        id="vidiom-hourly-generation",
        replace_existing=True,
    )
    scheduler.start()

