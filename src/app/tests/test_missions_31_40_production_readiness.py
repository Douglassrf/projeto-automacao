from pathlib import Path
import sqlite3

from app.core.production_readiness import (
    backup_sqlite,
    disaster_recovery_drill,
    enterprise_observability_snapshot,
    environment_profile,
    gold_certification_snapshot,
    liveness_probe,
    performance_max_plan,
    readiness_probe,
    restore_sqlite,
    security_enterprise_snapshot,
    shutdown_coordinator,
)


def _sqlite_file(path: Path) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        con.execute("INSERT INTO sample (name) VALUES ('ok')")
        con.commit()
    finally:
        con.close()


def test_liveness_readiness_and_environment_profile():
    shutdown_coordinator.accepting_traffic = True
    shutdown_coordinator.shutdown_requested_at = None
    assert liveness_probe()["status"] == "alive"
    profile = environment_profile("prod")
    assert profile["profile"]["auth_required"] is True
    assert readiness_probe()["status"] in {"ready", "not_ready"}


def test_backup_compression_integrity_rotation_and_restore(tmp_path):
    db = tmp_path / "source.db"
    restored = tmp_path / "restored.db"
    _sqlite_file(db)
    result = backup_sqlite(database_url=f"sqlite:///{db}", backup_dir=tmp_path / "backups", retention=1)
    backup_file = Path(result["backup_file"])
    assert result["compressed"] is True
    assert result["integrity"]["ok"] is True
    assert backup_file.exists()
    restored_result = restore_sqlite(backup_file, restored)
    assert restored_result["integrity"]["ok"] is True
    con = sqlite3.connect(restored)
    try:
        assert con.execute("SELECT name FROM sample").fetchone()[0] == "ok"
    finally:
        con.close()


def test_enterprise_observability_security_dr_and_certification_snapshots():
    obs = enterprise_observability_snapshot()
    assert obs["status"] == "ok"
    assert "metrics" in obs
    security = security_enterprise_snapshot({"env": "test"})
    assert security["secrets_encryption"] is True
    assert len(security["digital_signature"]) == 64
    assert disaster_recovery_drill()["automatic_recovery"] is True
    assert performance_max_plan()["cpu_memory_tracked"] is True
    assert gold_certification_snapshot()["critical_errors"] == 0
