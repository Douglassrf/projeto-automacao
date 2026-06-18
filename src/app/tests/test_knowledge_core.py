from app.services.knowledge_engine import KnowledgeEngine


def test_knowledge_core_loads_v1_v2_v3():
    engine = KnowledgeEngine()
    context = engine.marketing_context()

    assert context["v1"]["campaign_structure"]["subniches"] == 5
    assert context["v2"]["campaign_structure"]["creatives"] == 4
    assert context["v3"]["campaign_structure"]["recommended_creatives"] == "4 a 6"
    assert engine.connect_rate_warning_below() == 75
    assert "pixel_rules" in engine.load_all()


def test_knowledge_core_guardrails_are_editable_files():
    engine = KnowledgeEngine()
    guardrails = engine.guardrails()

    assert any("Purchase" in item for item in guardrails)
    assert any("midia flexivel" in item.lower() for item in guardrails)
