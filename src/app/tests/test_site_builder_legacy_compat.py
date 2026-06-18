from app.services.site_builder import SiteBuilder, StaticSiteBuilder, deploy_conversion_site


def test_site_builder_legacy_compatibility_generates_local_file(tmp_path):
    result = deploy_conversion_site(
        creative_data={"headline": "Oferta teste"},
        sub_niche_offers=["subnicho 1", "subnicho 2"],
        output_dir=tmp_path,
    )

    assert result["status"] == "ok"
    assert result["deploy"]["deploy_real"] is False
    output_path = tmp_path / "index.html"
    assert output_path.exists()
    assert "Oferta teste" in output_path.read_text(encoding="utf-8")


def test_static_site_builder_alias_keeps_old_imports_working():
    assert StaticSiteBuilder is SiteBuilder
    assert StaticSiteBuilder().build()["module"] == "site_builder"
