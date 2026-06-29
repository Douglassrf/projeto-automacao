"""Missao 73 - Technical Knowledge Base."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.main import app
from app.services.technical_knowledge_service import (
    ARCHITECTURAL_DECISIONS,
    LESSONS_LEARNED,
    MODULE_CATALOG,
    TechnicalKnowledgeService,
)


def test_knowledge_base_returns_expected_shape():
    db = SessionLocal()
    try:
        report = TechnicalKnowledgeService(db).knowledge_base()
        assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
        assert len(report["module_catalog"]) >= 1
        assert len(report["architectural_decisions"]) >= 1
        assert len(report["lessons_learned"]) == len(LESSONS_LEARNED)
        assert len(report["cross_references"]) >= len(MODULE_CATALOG)
    finally:
        db.close()


def test_module_catalog_lists_operational_modules():
    assert len(MODULE_CATALOG) >= 10
    modules = [m["module"] for m in MODULE_CATALOG]
    assert "certification" in modules
    assert "predictive_health" in modules


def test_cross_references_suppressed_when_flag_disabled():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.technical_knowledge_include_cross_references
    try:
        settings.technical_knowledge_include_cross_references = False
        report = TechnicalKnowledgeService(db).knowledge_base()
        assert report["cross_references"] == []
    finally:
        settings.technical_knowledge_include_cross_references = previous
        db.close()


def test_draft_adrs_filtered_when_flag_disabled():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.technical_knowledge_include_draft_adrs
    try:
        settings.technical_knowledge_include_draft_adrs = False
        report = TechnicalKnowledgeService(db).knowledge_base()
        assert all(a["status"] == "accepted" for a in report["architectural_decisions"])
    finally:
        settings.technical_knowledge_include_draft_adrs = previous
        db.close()


def test_render_markdown_contains_sections():
    db = SessionLocal()
    try:
        md = TechnicalKnowledgeService(db).render_markdown()
        assert "# Technical Knowledge Base" in md
        assert "## Catalogo de modulos" in md
        assert "## Decisoes arquiteturais" in md
        assert "## Licoes aprendidas" in md
        assert "## Referencias cruzadas" in md
    finally:
        db.close()


def test_base_live_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/technical-knowledge/base/live")
    assert response.status_code == 200
    body = response.json()
    assert "module_catalog" in body
    assert "cross_references" in body


def test_base_markdown_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/technical-knowledge/base/markdown")
    assert response.status_code == 200
    assert "# Technical Knowledge Base" in response.text


def test_config_schema_version_bumped_for_mission_73():
    current = tuple(int(part) for part in CONFIG_SCHEMA_VERSION.split("."))
    assert current >= (2, 2, 0)


def test_validate_settings_rejects_disabled_cross_refs_in_production():
    settings = get_settings()
    previous = settings.technical_knowledge_include_cross_references
    try:
        settings.technical_knowledge_include_cross_references = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("technical_knowledge_include_cross_references" in i for i in issues)
    finally:
        settings.technical_knowledge_include_cross_references = previous


def test_architectural_decisions_catalog_not_empty():
    assert len(ARCHITECTURAL_DECISIONS) >= 3
