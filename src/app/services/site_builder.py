from __future__ import annotations

from pathlib import Path
from typing import Any


def load_template(template_name: str) -> str:
    return f"Template base carregado: {template_name}"


def inject_dynamic_content(
    template: str,
    creative_data: Any,
    sub_niche_offers: list[Any],
) -> str:
    site_content = f"{template}\nAnuncio principal inserido: {creative_data}"
    for index, offer in enumerate(sub_niche_offers[:5], start=1):
        site_content += f"\nBloco de sub-nicho {index}: {offer}"
    return site_content


def save_to_deploy_folder(site_content: str, output_dir: str | Path = "deploy") -> Path:
    deploy_dir = Path(output_dir)
    deploy_dir.mkdir(parents=True, exist_ok=True)
    output_path = deploy_dir / "index.html"
    output_path.write_text(site_content, encoding="utf-8")
    return output_path


def trigger_deploy(dry_run: bool = True) -> dict[str, Any]:
    return {
        "status": "dry_run" if dry_run else "ready_for_manual_deploy",
        "deploy_real": False,
        "message": "Deploy real bloqueado; arquivo local gerado para revisao.",
    }


def deploy_conversion_site(
    creative_data: Any,
    sub_niche_offers: list[Any],
    output_dir: str | Path = "deploy",
) -> dict[str, Any]:
    template = load_template("high_conversion_v1")
    site_content = inject_dynamic_content(template, creative_data, sub_niche_offers)
    output_path = save_to_deploy_folder(site_content, output_dir=output_dir)
    deploy_result = trigger_deploy(dry_run=True)
    return {
        "status": "ok",
        "module": "site_builder",
        "output_path": str(output_path),
        "deploy": deploy_result,
    }


class SiteBuilder:
    def build(
        self,
        creative_data: Any | None = None,
        sub_niche_offers: list[Any] | None = None,
        output_dir: str | Path = "deploy",
    ) -> dict[str, Any]:
        if creative_data is None:
            return {"status": "ok", "module": "site_builder"}
        return deploy_conversion_site(
            creative_data=creative_data,
            sub_niche_offers=sub_niche_offers or [],
            output_dir=output_dir,
        )


StaticSiteBuilder = SiteBuilder
