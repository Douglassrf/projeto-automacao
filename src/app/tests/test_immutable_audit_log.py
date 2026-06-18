from app.core.immutable_audit import GENESIS_HASH, ImmutableAuditLog
from app.services.observability import immutable_audit_event, immutable_audit_health


def test_immutable_audit_log_appends_hash_chain(tmp_path):
    audit = ImmutableAuditLog(tmp_path / "immutable.jsonl")

    first = audit.append({"actor": "Brain", "action": "decision.create"})
    second = audit.append({"actor": "Brian", "action": "learning.record"})

    assert first["previous_hash"] == GENESIS_HASH
    assert second["previous_hash"] == first["event_hash"]
    assert audit.verify().ok is True
    assert audit.verify().total_events == 2


def test_immutable_audit_log_detects_tampering(tmp_path):
    path = tmp_path / "immutable.jsonl"
    audit = ImmutableAuditLog(path)
    audit.append({"actor": "Brain", "action": "decision.create"})

    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("decision.create", "decision.delete"), encoding="utf-8")

    result = audit.verify()

    assert result.ok is False
    assert result.reason == "event_hash_mismatch"
    assert result.broken_at == 1


def test_observability_immutable_audit_event_records_chain():
    record = immutable_audit_event(
        actor="Mission35E",
        action="immutable.audit.test",
        resource_type="audit",
        resource_id="test",
        mission_id="35E",
        correlation_id="REQ-2026-35E",
        execution_id="exec-35E",
        details={"purpose": "hash_chain"},
    )

    health = immutable_audit_health()

    assert len(record["event_hash"]) == 64
    assert health["hash_chain_ok"] is True
    assert health["total_events"] >= 1
