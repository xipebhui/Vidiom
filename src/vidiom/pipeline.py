from __future__ import annotations

from dataclasses import dataclass

from .generator import ShortDramaGenerator
from .schema import validate_short_drama
from .storage import Storage, utc_now


@dataclass(frozen=True)
class RunResult:
    processed: int
    succeeded: int
    failed: int


def run_once(storage: Storage, generator: ShortDramaGenerator, limit: int) -> RunResult:
    if limit < 1:
        raise ValueError("limit must be at least 1.")

    started_at = utc_now()
    claimed = storage.claim_pending(limit)
    succeeded = 0
    failed = 0

    for inspiration in claimed:
        try:
            payload = generator.generate(inspiration.text)
            validate_short_drama(payload)
            storage.complete(inspiration.id, payload)
            succeeded += 1
        except Exception as exc:
            storage.fail(inspiration.id, str(exc))
            failed += 1

    storage.log_run(
        started_at=started_at,
        processed=len(claimed),
        succeeded=succeeded,
        failed=failed,
    )
    return RunResult(processed=len(claimed), succeeded=succeeded, failed=failed)

