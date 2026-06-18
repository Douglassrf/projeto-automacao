from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import httpx
from datetime import date

from app.core.config import get_settings
from app.schemas.facebook_marketing import CampaignPlanItem


class MetaMarketingError(RuntimeError):
    pass


@dataclass(frozen=True)
class MetaCredentials:
    access_token: str | None
    ad_account_id: str | None
    page_id: str | None
    instagram_actor_id: str | None
    api_version: str
    dry_run: bool

    @property
    def configured(self) -> bool:
        return bool(self.access_token and self.ad_account_id and self.page_id)


class MetaMarketingClient:
    """Adapter seguro para Meta Marketing API.

    Por padrão roda em dry-run. Publicação real exige META_DRY_RUN=false,
    META_ACCESS_TOKEN, META_AD_ACCOUNT_ID e META_PAGE_ID no backend.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.credentials = MetaCredentials(
            access_token=settings.meta_access_token,
            ad_account_id=settings.meta_ad_account_id,
            page_id=settings.meta_page_id,
            instagram_actor_id=settings.meta_instagram_actor_id,
            api_version=settings.meta_api_version,
            dry_run=settings.meta_dry_run,
        )
        self.base_url = f"https://graph.facebook.com/{self.credentials.api_version}"

    @property
    def dry_run(self) -> bool:
        return self.credentials.dry_run or not self.credentials.configured

    def publish_campaign_plan(self, plan: CampaignPlanItem) -> dict[str, Any]:
        if self.dry_run:
            suffix = hashlib.sha1(plan.campaign_name.encode("utf-8")).hexdigest()[:10]
            return {
                "dry_run": True,
                "campaign_id": plan.existing_campaign_id or f"dry_campaign_{suffix}",
                "adset_id": f"dry_adset_{suffix}",
                "creative_id": f"dry_creative_{suffix}",
                "ad_id": f"dry_ad_{suffix}",
                "messages": [
                    "Dry-run ativo: campanha simulada sem publicar no Facebook Ads.",
                    "Configure META_DRY_RUN=false e credenciais oficiais para publicação real.",
                ],
            }

        if not self.credentials.configured:
            raise MetaMarketingError("Credenciais Meta incompletas no backend.")

        campaign = self._post(
            f"/act_{self.credentials.ad_account_id}/campaigns",
            {
                "name": plan.campaign_name,
                "objective": plan.objective,
                "status": plan.campaign_status,
                "special_ad_categories": json.dumps([]),
                "is_adset_budget_sharing_enabled": "False",
            },
        )
        campaign_id = campaign.get("id")
        if not campaign_id:
            raise MetaMarketingError("Meta não retornou campaign_id.")

        adset = self._post(
            f"/act_{self.credentials.ad_account_id}/adsets",
            {
                "name": plan.adset_name,
                "campaign_id": campaign_id,
                "daily_budget": int(plan.daily_budget_brl * 100),
                "is_adset_budget_sharing_enabled": "False",
                "billing_event": "IMPRESSIONS",
                "optimization_goal": plan.optimization_goal,
                "status": plan.adset_status,
                "promoted_object": json.dumps({"pixel_id": plan.promoted_object.split(":")[1], "custom_event_type": "PURCHASE"}),
                "targeting": json.dumps(plan.targeting or {"geo_locations": {"countries": ["BR"]}}),
            },
        )
        adset_id = adset.get("id")
        if not adset_id:
            raise MetaMarketingError("Meta não retornou adset_id.")

        creative_body = plan.copy_variations[0] if plan.copy_variations else plan.product_name
        link_url = plan.affiliate.affiliate_link if plan.affiliate else "https://example.com"
        creative_payload: dict[str, Any] = {
            "name": f"Creative - {plan.product_name}",
            "object_story_spec": {
                "page_id": self.credentials.page_id,
                "link_data": {
                    "link": link_url,
                    "message": creative_body,
                    "name": plan.product_name,
                    "call_to_action": {"type": "LEARN_MORE", "value": {"link": link_url}},
                },
            },
        }
        if self.credentials.instagram_actor_id:
            creative_payload["object_story_spec"]["instagram_actor_id"] = self.credentials.instagram_actor_id

        creative = self._post(f"/act_{self.credentials.ad_account_id}/adcreatives", creative_payload)
        creative_id = creative.get("id")
        if not creative_id:
            raise MetaMarketingError("Meta não retornou creative_id.")

        ad = self._post(
            f"/act_{self.credentials.ad_account_id}/ads",
            {
                "name": plan.ad_name,
                "adset_id": adset_id,
                "creative": {"creative_id": creative_id},
                "status": plan.ad_status,
            },
        )
        ad_id = ad.get("id")
        if not ad_id:
            raise MetaMarketingError("Meta não retornou ad_id.")

        return {
            "dry_run": False,
            "campaign_id": campaign_id,
            "adset_id": adset_id,
            "creative_id": creative_id,
            "ad_id": ad_id,
            "messages": [f"Campanha criada na Meta com status {plan.campaign_status} usando modelo {plan.campaign_model}."] ,
        }




    def publish_plan_to_existing_campaign(self, plan: CampaignPlanItem) -> dict[str, Any]:
        if not plan.existing_campaign_id:
            raise MetaMarketingError("existing_campaign_id obrigatorio para reutilizar campanha.")
        if self.dry_run:
            suffix = hashlib.sha1(f"{plan.existing_campaign_id}:{plan.adset_name}".encode("utf-8")).hexdigest()[:10]
            return {
                "dry_run": True,
                "campaign_id": plan.existing_campaign_id,
                "adset_id": f"dry_adset_{suffix}",
                "creative_id": f"dry_creative_{suffix}",
                "ad_id": f"dry_ad_{suffix}",
                "messages": ["Dry-run ativo: conjunto/anuncio simulados dentro de campanha existente."],
            }
        if not self.credentials.configured:
            raise MetaMarketingError("Credenciais Meta incompletas no backend.")

        campaign_id = plan.existing_campaign_id
        adset = self._post(
            f"/act_{self.credentials.ad_account_id}/adsets",
            {
                "name": plan.adset_name,
                "campaign_id": campaign_id,
                "daily_budget": int(plan.daily_budget_brl * 100),
                "is_adset_budget_sharing_enabled": "False",
                "billing_event": "IMPRESSIONS",
                "optimization_goal": plan.optimization_goal,
                "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                "status": plan.adset_status,
                "promoted_object": json.dumps({"pixel_id": plan.promoted_object.split(":")[1], "custom_event_type": "PURCHASE"}),
                "targeting": json.dumps(plan.targeting or {"geo_locations": {"countries": ["BR"]}}),
            },
        )
        adset_id = adset.get("id")
        if not adset_id:
            raise MetaMarketingError("Meta nao retornou adset_id.")

        creative_body = plan.copy_variations[0] if plan.copy_variations else plan.product_name
        link_url = plan.affiliate.affiliate_link if plan.affiliate else "https://example.com"
        creative_payload: dict[str, Any] = {
            "name": f"Creative - {plan.product_name}",
            "object_story_spec": {
                "page_id": self.credentials.page_id,
                "link_data": {
                    "link": link_url,
                    "message": creative_body,
                    "name": plan.product_name,
                    "call_to_action": {"type": "LEARN_MORE", "value": {"link": link_url}},
                },
            },
        }
        if self.credentials.instagram_actor_id:
            creative_payload["object_story_spec"]["instagram_actor_id"] = self.credentials.instagram_actor_id

        creative = self._post(f"/act_{self.credentials.ad_account_id}/adcreatives", creative_payload)
        creative_id = creative.get("id")
        if not creative_id:
            raise MetaMarketingError("Meta nao retornou creative_id.")

        ad = self._post(
            f"/act_{self.credentials.ad_account_id}/ads",
            {
                "name": plan.ad_name,
                "adset_id": adset_id,
                "creative": {"creative_id": creative_id},
                "status": plan.ad_status,
            },
        )
        ad_id = ad.get("id")
        if not ad_id:
            raise MetaMarketingError("Meta nao retornou ad_id.")

        return {
            "dry_run": False,
            "campaign_id": campaign_id,
            "adset_id": adset_id,
            "creative_id": creative_id,
            "ad_id": ad_id,
            "messages": [f"Campanha existente reutilizada com status {plan.campaign_status}."],
        }

    def get_campaign_status(self, campaign_id: str) -> str:
        """Return the current campaign status from Meta, or simulated ACTIVE.

        Used by CampaignState to detect drift between desired and real status.
        """
        if self.dry_run or not campaign_id:
            return "ACTIVE"
        data = self._get(f"/{campaign_id}", {"fields": "status,effective_status"})
        return str(data.get("status") or data.get("effective_status") or "UNKNOWN")

    def get_campaign_spend(self, campaign_id: str) -> float:
        """Return today's spend for a single campaign_id from Meta Insights.

        In dry-run or without credentials, returns 0. The decision loop can
        safely fall back to the latest locally ingested spend.
        """
        if self.dry_run:
            return 0.0
        today = date.today().isoformat()
        data = self._get(
            f"/{campaign_id}/insights",
            {
                "fields": "spend",
                "time_range": json.dumps({"since": today, "until": today}),
                "level": "campaign",
            },
        )
        rows = data.get("data") or []
        if not rows:
            return 0.0
        try:
            return float(rows[0].get("spend") or 0)
        except (TypeError, ValueError):
            return 0.0


    def get_ad_account_spend_today_brl(self) -> float:
        """Return today's ad account spend according to Meta insights.

        In dry-run or without credentials, returns 0. This is a production
        guardrail, not a reporting source of truth.
        """
        if self.dry_run:
            return 0.0
        today = date.today().isoformat()
        data = self._get(
            f"/act_{self.credentials.ad_account_id}/insights",
            {
                "fields": "spend",
                "time_range": json.dumps({"since": today, "until": today}),
                "level": "account",
            },
        )
        rows = data.get("data") or []
        if not rows:
            return 0.0
        try:
            return float(rows[0].get("spend") or 0)
        except (TypeError, ValueError):
            return 0.0

    def remove_campaign(self, campaign_id: str, action: str = "pause", dry_run: bool | None = None) -> dict[str, Any]:
        effective_dry_run = self.dry_run if dry_run is None else dry_run or self.dry_run
        if effective_dry_run:
            return {"dry_run": True, "status": "simulated", "campaign_id": campaign_id, "action": action}
        if action == "delete":
            return self._delete(f"/{campaign_id}")
        return self._post(f"/{campaign_id}", {"status": "PAUSED"})

    def apply_campaign_action(
        self,
        action: str,
        campaign_id: str,
        adset_id: str | None = None,
        target: str = "campaign",
        new_daily_budget_brl: float | None = None,
        dry_run: bool | None = None,
    ) -> dict[str, Any]:
        """Apply a small operational action to Meta Ads with dry-run support.

        This powers Level 1/2 automation. It intentionally supports only a
        narrow safe action set: notify, pause campaign/adset and budget update.
        """
        effective_dry_run = self.dry_run if dry_run is None else dry_run or self.dry_run
        target_id = adset_id if target == "adset" and adset_id else campaign_id
        suffix = hashlib.sha1(f"{action}:{target_id}".encode("utf-8")).hexdigest()[:10]
        if effective_dry_run:
            return {
                "dry_run": True,
                "status": "simulated",
                "action": action,
                "target": target,
                "target_id": target_id,
                "simulation_id": f"dry_action_{suffix}",
                "messages": ["Dry-run ativo: nenhuma alteração real foi enviada à Meta."],
            }

        if not self.credentials.configured:
            raise MetaMarketingError("Credenciais Meta incompletas no backend.")

        if action == "pause_campaign":
            response = self._post(f"/{campaign_id}", {"status": "PAUSED"})
        elif action == "pause_adset":
            if not adset_id:
                raise MetaMarketingError("pause_adset exige adset_id.")
            response = self._post(f"/{adset_id}", {"status": "PAUSED"})
        elif action == "scale_budget":
            if not adset_id:
                raise MetaMarketingError("scale_budget exige adset_id para alterar orçamento do conjunto.")
            if not new_daily_budget_brl:
                raise MetaMarketingError("scale_budget exige new_daily_budget_brl.")
            response = self._post(f"/{adset_id}", {"daily_budget": int(new_daily_budget_brl * 100)})
        elif action == "decrease_bid":
            if not adset_id:
                raise MetaMarketingError("decrease_bid exige adset_id para ajustar orçamento/bid do conjunto.")
            if not new_daily_budget_brl:
                raise MetaMarketingError("decrease_bid exige new_daily_budget_brl calculado pelo agente.")
            response = self._post(f"/{adset_id}", {"daily_budget": int(new_daily_budget_brl * 100)})
        elif action == "notify_only":
            response = {"success": True, "message": "notify_only não altera a Meta."}
        else:
            raise MetaMarketingError(f"Ação não suportada: {action}")

        return {
            "dry_run": False,
            "status": "executed",
            "action": action,
            "target": target,
            "target_id": target_id,
            "meta_response": response,
            "messages": [f"Ação {action} enviada para Meta."],
        }

    def list_campaigns_with_metrics_today(self, limit: int = 100) -> list[dict[str, Any]]:
        """List active/paused campaigns with today's basic metrics.

        This powers the Campaign Sync Worker. In dry-run it returns a stable
        sample so smoke tests and the dashboard can validate the flow without
        touching a real ad account. In production it uses Graph API pagination
        and per-campaign insights with date_preset=today.
        """
        if self.dry_run:
            return [
                {
                    "meta_campaign_id": "dry_meta_campaign_v2",
                    "name": "Dry Run V2 Produto Teste",
                    "status_real": "ACTIVE",
                    "daily_budget": 50.0,
                    "spend_today": 18.75,
                    "reach": 1200,
                    "ctr": 1.85,
                },
                {
                    "meta_campaign_id": "dry_meta_campaign_guard",
                    "name": "Dry Run Guardrail",
                    "status_real": "ACTIVE",
                    "daily_budget": 25.0,
                    "spend_today": 32.10,
                    "reach": 800,
                    "ctr": 0.72,
                },
            ][:limit]

        rows: list[dict[str, Any]] = []
        after: str | None = None
        while len(rows) < limit:
            params: dict[str, Any] = {
                "fields": "id,name,status,daily_budget",
                "limit": min(100, limit - len(rows)),
                "effective_status": json.dumps(["ACTIVE", "PAUSED"]),
            }
            if after:
                params["after"] = after
            data = self._get(f"/act_{self.credentials.ad_account_id}/campaigns", params)
            for campaign in data.get("data") or []:
                campaign_id = str(campaign.get("id") or "")
                insights = self._get(
                    f"/{campaign_id}/insights",
                    {
                        "fields": "spend,reach,inline_link_click_ctr",
                        "date_preset": "today",
                    },
                ) if campaign_id else {"data": []}
                insight_rows = insights.get("data") or []
                insight = insight_rows[0] if insight_rows else {}
                try:
                    budget = float(campaign.get("daily_budget") or 0) / 100
                except (TypeError, ValueError):
                    budget = 0.0
                try:
                    spend = float(insight.get("spend") or 0)
                except (TypeError, ValueError):
                    spend = 0.0
                try:
                    reach = int(float(insight.get("reach") or 0))
                except (TypeError, ValueError):
                    reach = 0
                try:
                    ctr = float(insight.get("inline_link_click_ctr") or 0)
                except (TypeError, ValueError):
                    ctr = 0.0
                rows.append({
                    "meta_campaign_id": campaign_id,
                    "name": str(campaign.get("name") or campaign_id),
                    "status_real": str(campaign.get("status") or "UNKNOWN"),
                    "daily_budget": budget,
                    "spend_today": spend,
                    "reach": reach,
                    "ctr": ctr,
                })
                if len(rows) >= limit:
                    break
            paging = data.get("paging") or {}
            cursors = paging.get("cursors") or {}
            next_after = cursors.get("after")
            if not paging.get("next") or not next_after or next_after == after:
                break
            after = next_after
        return rows

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "access_token": self.credentials.access_token}
        try:
            response = httpx.get(f"{self.base_url}{path}", params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise MetaMarketingError(f"Erro da Meta API: {detail}") from exc
        except httpx.HTTPError as exc:
            raise MetaMarketingError("Falha de conexão com a Meta API.") from exc

    def _delete(self, path: str) -> dict[str, Any]:
        payload = {"access_token": self.credentials.access_token}
        try:
            response = httpx.delete(f"{self.base_url}{path}", data=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise MetaMarketingError(f"Erro da Meta API: {detail}") from exc
        except httpx.HTTPError as exc:
            raise MetaMarketingError("Falha de conexão com a Meta API.") from exc

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = {**payload, "access_token": self.credentials.access_token}
        try:
            response = httpx.post(f"{self.base_url}{path}", data=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise MetaMarketingError(f"Erro da Meta API: {detail}") from exc
        except httpx.HTTPError as exc:
            raise MetaMarketingError("Falha de conexão com a Meta API.") from exc
