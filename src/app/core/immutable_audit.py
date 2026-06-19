from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any


GENESIS_HASH = "0" * 64


class ImmutableAuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImmutableAuditVerification:
    ok: bool
    total_events: int
    broken_at: int | None = None
    reason: str = ""


class ImmutableAuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        previous_hash = self.last_hash()
        base_record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "previous_hash": previous_hash,
            "event": event,
        }
        event_hash = self._hash_record(base_record)
        record = {**base_record, "event_hash": event_hash}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def last_hash(self) -> str:
        if not self.path.exists():
            return GENESIS_HASH
        last_line = ""
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last_line = line
        if not last_line:
            return GENESIS_HASH
        try:
            record = json.loads(last_line)
        except json.JSONDecodeError as exc:
            raise ImmutableAuditError("Ultimo registro de auditoria imutavel esta corrompido.") from exc
        event_hash = str(record.get("event_hash") or "")
        if len(event_hash) != 64:
            raise ImmutableAuditError("Ultimo registro nao contem event_hash valido.")
        return event_hash

    def verify(self) -> ImmutableAuditVerification:
        if not self.path.exists():
            return ImmutableAuditVerification(ok=True, total_events=0)
        previous_hash = GENESIS_HASH
        total = 0
        with self.path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    return ImmutableAuditVerification(ok=False, total_events=total, broken_at=index, reason="invalid_json")

                expected_previous = str(record.get("previous_hash") or "")
                if expected_previous != previous_hash:
                    return ImmutableAuditVerification(ok=False, total_events=total, broken_at=index, reason="previous_hash_mismatch")

                stored_hash = str(record.get("event_hash") or "")
                base_record = {key: record[key] for key in ("timestamp", "previous_hash", "event") if key in record}
                calculated_hash = self._hash_record(base_record)
                if stored_hash != calculated_hash:
                    return ImmutableAuditVerification(ok=False, total_events=total, broken_at=index, reason="event_hash_mismatch")

                previous_hash = stored_hash
                total += 1
        return ImmutableAuditVerification(ok=True, total_events=total)

    @staticmethod
    def _hash_record(record: dict[str, Any]) -> str:
        canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

