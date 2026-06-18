from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = PROJECT_ROOT / "logs"
AFFILIATE_ACTIVITY_LOG = LOG_DIR / "affiliate_activity.log"
_LOG_LOCK = threading.Lock()


def ensure_log_file() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    AFFILIATE_ACTIVITY_LOG.touch(exist_ok=True)


def write_affiliate_activity(ad_id: int | str | None, original_link: str, affiliate_link: str) -> dict[str, Any]:
    ensure_log_file()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ad_id": ad_id if ad_id is not None else "manual",
        "original_link": original_link,
        "affiliate_link": affiliate_link,
    }
    with _LOG_LOCK:
        with AFFILIATE_ACTIVITY_LOG.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_latest_affiliate_activity(limit: int = 10) -> list[dict[str, Any]]:
    ensure_log_file()
    limit = max(1, min(limit, 100))
    with _LOG_LOCK:
        lines = AFFILIATE_ACTIVITY_LOG.read_text(encoding="utf-8").splitlines()

    activities: list[dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            activities.append(json.loads(line))
        except json.JSONDecodeError:
            activities.append({
                "timestamp": "invalid",
                "ad_id": "unknown",
                "original_link": "log_line_invalid",
                "affiliate_link": line,
            })
        if len(activities) >= limit:
            break
    return activities
