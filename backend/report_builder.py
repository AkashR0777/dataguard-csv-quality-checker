"""Report construction helpers shared by the validator Lambda and tests."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def build_report(
    *,
    file_name: str,
    job_id: str,
    validation: dict[str, Any],
    processed_at: str | None = None,
) -> dict[str, Any]:
    report = {
        "job_id": job_id,
        "file_name": file_name,
        "processed_at": processed_at or datetime.now(timezone.utc).isoformat(),
        "processing_id": str(uuid4()),
    }
    report.update(validation)
    return report
