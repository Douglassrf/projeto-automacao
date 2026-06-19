from __future__ import annotations

from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)

from app.integrations.affiliate_provider import AffiliateProvider
from app.integrations.meta_marketing import MetaMarketingClient, MetaMarketingError
from app.schemas.affiliate import AffiliateReplaceRequest
from app.schemas.facebook_marketing import (
    CampaignPlanItem,
    CampaignPlanRequest,
    CampaignPlanResponse,
    FacebookAdSignal,
    MetaExecutionResult,
    V1ItemDecision,
    V1MarketingRequest,
    V1MarketingResponse,
    V3ExecutionRequest,
    V3ExecutionResponse,
    V2DedicatedSimulationRequest,
    V2DedicatedSimulationResponse,
    V2AdSimulationItem,
    ProductCampaignSuiteRequest,
    ProductCampaignSuiteResponse,
    ProductCampaignCategoryPlan,
    CampaignAdUnitPlan,
    GeneratedAssetBlueprint,
)


class FacebookMarketingAutomationEngine:
    """Motor V1/V2/V3 de automação de campanhas Meta Ads.

    V1 = validação/diagnóstico. V2 = plano de campanha. V3 = execução automática
    com três modelos de campanha, sempre via API oficial e com guardrails.
    """

    def __init__(self, affiliate_provider: AffiliateProvider | None = None, meta_client: MetaMarketingClient | None = None):
        self.affiliate_provider = affiliate_provider or AffiliateProvider()
        self.meta_client = meta_client or MetaMarketingClient()

    def v1_strategy(self, payload: V1MarketingRequest) -> V1MarketingResponse:
        decisions = [self._decide(item, payload.threshold_min, payload.threshold_max) for item in payload.items]
        winners = sum(1 for item in decisions if item.decision == "winner")
        return V1MarketingResponse(total_received=len(payload.items), winners=winners, rejected=len(payload.items) - winners, decisions=decisions)

    def v2_campaign_plan(self, payload: CampaignPlanRequest) -> CampaignPlanResponse:
        decisions = self.v1_strategy(V1MarketingRequest(threshold_min=payload.threshold_min, threshold_max=payload.threshold_max, items=payload.items))
        approved_ids = {d.external_id for d in decisions.decisions if d.decision == "winner"}
        approved_names = {d.product_name for d in decisions.decisions if d.decision == "winner"}
        approved = [item for item in payload.items if (item.external_id in approved_ids or item.product_name in approved_names)]
        approved = approved[: payload.budget.max_campaigns_per_run]
        plans: list[CampaignPlanItem] = []
        for index, item in enumerate(approved, start=1):
            plans.extend(self._build_three_model_plan(item, payload, index))
        return CampaignPlanResponse(
            generated_at=datetime.now(UTC),
            mode="automatic_v3_ready" if not payload.budget.require_manual_review else "review_required",
            total_items=len(payload.items),
            approved_for_plan=len(plans),
            plans=plans,
        )


    def v2_dedicated_simulation(self, payload: V2DedicatedSimulationRequest) -> V2DedicatedSimulationResponse:
        """Simula a V2 real definida para performance: 1 campanha, 1 conjunto e 4 criativos.

        Guardrail: não publica na Meta. Serve para validar estrutura, nomes, targeting e
        consistência operacional antes da criação real via operador.
        """
        safe_name = self._safe_name(payload.product_name)
        campaign_name = f"{safe_name} V2"
        adset_name = f"{safe_name} V2 | OPEN | MOBILE WIFI | {payload.language}"
        warnings: list[str] = []

        if payload.daily_budget_brl < 50:
            warnings.append("Orçamento abaixo de R$50/dia: pode gerar gargalo de dados para 4 criativos em 3 dias.")
        if len(payload.included_countries) > 6 and payload.daily_budget_brl <= 50:
            warnings.append("Muitos países para R$50/dia: o algoritmo pode concentrar verba e deixar países sem leitura.")
        if not payload.mobile_only:
            warnings.append("V2 definida pede somente celular; mobile_only está desativado.")
        if not payload.wifi_only:
            warnings.append("V2 definida pede somente Wi-Fi; wifi_only está desativado.")
        if payload.conversion_event != "Purchase":
            warnings.append("Evento diferente de Purchase: risco de otimizar para público desqualificado.")
        if not payload.flexible_media_disabled:
            warnings.append("Mídia flexível ativa pode alterar criativo e contaminar o teste.")
        if not payload.auto_creative_optimizations_disabled:
            warnings.append("Sugestões automáticas ativas podem alterar copy/mídia e contaminar o teste.")

        ads = []
        for index, creative in enumerate(payload.creatives, start=1):
            ad_name = creative.ad_name or f"AD{index:02d}"
            ads.append(V2AdSimulationItem(
                ad_name=ad_name,
                media_name=creative.media_name,
                media_type=creative.media_type,
                simulated_ad_id=f"dry_v2_ad_{index:02d}_{abs(hash((campaign_name, ad_name))) % 100000}",
                same_copy=True,
                same_link=True,
                media_original_format=True,
                status="ready_for_publish_simulation",
            ))

        targeting = {
            "geo_locations": {"countries": payload.included_countries},
            "excluded_geo_locations": {"countries": payload.excluded_countries},
            "locales": [payload.language],
            "age_min": payload.age_min,
            "genders": payload.genders,
            "publisher_platforms": payload.publisher_platforms,
            "device_platforms": ["mobile"] if payload.mobile_only else ["mobile", "desktop"],
            "user_device_connection": "wifi_only" if payload.wifi_only else "all",
            "removed_placements": payload.removed_placements,
            "detailed_targeting": "open_no_interests",
        }

        checklist = [
            "Objetivo Vendas configurado.",
            "Destino Site configurado.",
            "Evento Purchase configurado no pixel informado.",
            "1 campanha, 1 conjunto e 4 anúncios no mesmo conjunto.",
            "Todos os anúncios usam a mesma copy e o mesmo link.",
            "Somente a mídia muda entre AD01, AD02, AD03 e AD04.",
            "Brasil excluído e países LATAM espanhol incluídos.",
            "Facebook e Instagram mantidos; Threads, Audience Network e Messenger removidos.",
            "Somente celular e Wi-Fi configurados.",
            "Mídia flexível e otimizações automáticas de criativo desativadas.",
            "Sem data de término; análise mínima de 3 dias.",
        ]

        return V2DedicatedSimulationResponse(
            campaign_name=campaign_name,
            adset_name=adset_name,
            objective=payload.objective,
            destination=payload.destination,
            conversion_event=payload.conversion_event,
            pixel_id=payload.pixel_id,
            daily_budget_brl=payload.daily_budget_brl,
            analysis_window_days=3,
            structure_valid=(len(payload.creatives) == 4 and payload.conversion_event == "Purchase" and payload.flexible_media_disabled and payload.auto_creative_optimizations_disabled),
            campaign_status="SIMULATED_READY",
            targeting=targeting,
            ads=ads,
            checklist=checklist,
            warnings=warnings,
            simulated=True,
        )

    def v3_execute(self, payload: V3ExecutionRequest) -> V3ExecutionResponse:
        started = datetime.now(UTC)
        plan_response = self.v2_campaign_plan(payload)
        results: list[MetaExecutionResult] = []
        published = 0
        blocked = 0

        for plan in plan_response.plans:
            if payload.budget.require_manual_review or payload.execution_mode == "review_only" or not payload.publish_to_meta:
                blocked += 1
                results.append(MetaExecutionResult(
                    dry_run=True,
                    product_name=plan.product_name,
                    campaign_model=plan.campaign_model,
                    campaign_name=plan.campaign_name,
                    status="blocked_for_manual_review",
                    messages=["Plano gerado, mas publicação bloqueada por revisão manual/configuração."],
                ))
                continue
            try:
                meta_result = self.meta_client.publish_campaign_plan(plan)
                if not meta_result["dry_run"]:
                    published += 1
                results.append(MetaExecutionResult(
                    dry_run=meta_result["dry_run"],
                    product_name=plan.product_name,
                    campaign_model=plan.campaign_model,
                    campaign_name=plan.campaign_name,
                    meta_campaign_id=meta_result.get("campaign_id"),
                    meta_adset_id=meta_result.get("adset_id"),
                    meta_creative_id=meta_result.get("creative_id"),
                    meta_ad_id=meta_result.get("ad_id"),
                    status="published" if not meta_result["dry_run"] else "simulated",
                    messages=meta_result.get("messages", []),
                ))
            except MetaMarketingError as exc:
                results.append(MetaExecutionResult(
                    dry_run=self.meta_client.dry_run,
                    product_name=plan.product_name,
                    campaign_model=plan.campaign_model,
                    campaign_name=plan.campaign_name,
                    status="meta_error",
                    messages=[str(exc)],
                ))

        return V3ExecutionResponse(
            started_at=started,
            finished_at=datetime.now(UTC),
            dry_run=self.meta_client.dry_run or not payload.publish_to_meta,
            attempted=len(plan_response.plans),
            published=published,
            blocked_for_review=blocked,
            results=results,
        )

    def _decide(self, item: FacebookAdSignal, threshold_min: int, threshold_max: int) -> V1ItemDecision:
        connect_rate = self._percent(item.landing_page_views, item.link_clicks)
        checkout_rate = self._percent(item.checkout_starts, item.landing_page_views)
        purchase_rate = self._percent(item.purchases, item.landing_page_views)
        roas = (item.revenue / item.spend) if item.spend else 0
        frequency_power = 25 if threshold_min <= item.active_ads <= threshold_max else (18 if item.active_ads > threshold_max else 0)
        score = min(100, round(frequency_power + (connect_rate * 0.22) + (checkout_rate * 0.18) + (purchase_rate * 2.8) + (min(roas, 6) * 5) + min(item.ctr * 3, 12), 2))
        reasons: list[str] = []
        if threshold_min <= item.active_ads <= threshold_max:
            reasons.append(f"Frequência validada: {item.active_ads} anúncios ativos dentro do threshold {threshold_min}-{threshold_max}.")
        elif item.active_ads > threshold_max:
            reasons.append(f"Volume acima de {threshold_max}: possível vencedor saturado; usar V3 com orçamento controlado e criativo renovado.")
        else:
            reasons.append(f"Volume insuficiente: {item.active_ads} anúncios ativos.")
        reasons.append(f"Connect Rate calculado: {connect_rate}%.")
        reasons.append(f"Checkout Rate calculado: {checkout_rate}% | Purchase Rate: {purchase_rate}% | ROAS: {round(roas, 2)}.")
        if connect_rate < 55:
            reasons.append("Bloqueio: clique não está virando visualização de página com força suficiente.")
        if purchase_rate >= 2 or roas >= 1.5:
            reasons.append("Sinal de conversão favorável para automação V3.")
        winner = item.active_ads >= threshold_min and connect_rate >= 55 and score >= 45
        if item.active_ads > threshold_max and score < 70:
            winner = False
        return V1ItemDecision(
            external_id=item.external_id,
            product_name=item.product_name,
            active_ads=item.active_ads,
            status=self._status(item.active_ads),
            marketing_stage="V1-Inteligência Avançada",
            score=score,
            decision="winner" if winner else "rejected",
            recommended_action="Executar V2/V3: criar 3 modelos de campanha com afiliado aplicado." if winner else "Não publicar; manter no radar e coletar mais dados.",
            reasons=reasons,
            generated_angles=self._angles(item),
        )

    def _build_three_model_plan(self, item: FacebookAdSignal, payload: CampaignPlanRequest, position: int) -> list[CampaignPlanItem]:
        affiliate_result = self.affiliate_provider.replace_link(AffiliateReplaceRequest(
            ad_id=item.external_id or f"auto-{position}",
            creative_original=item.creative_original,
            network=payload.network,
            user_affiliate_id=payload.affiliate_id,
            destination_url=item.destination_url,
        ))
        base_budget = min(payload.budget.daily_budget_brl, payload.budget.max_daily_budget_brl)
        status = "ACTIVE" if payload.budget.allow_active_launch else "PAUSED"
        models = [
            ("V1_VALIDACAO", 1, 0.6, "OUTCOME_TRAFFIC", "LINK_CLICKS", "Teste barato de validação do ângulo vencedor", self._broad_targeting()),
            ("V2_ESCALA_CONTROLADA", 2, 1.0, "OUTCOME_TRAFFIC", "LANDING_PAGE_VIEWS", "Escala controlada com variações de copy e criativo", self._interest_targeting()),
            ("V3_AUTOMACAO_PRINCIPAL", 3, 1.4, "OUTCOME_SALES", "OFFSITE_CONVERSIONS", "Campanha principal otimizada para conversão/venda", self._conversion_targeting()),
        ]
        safe_name = self._safe_name(item.product_name)
        plans = []
        for model, priority, mult, objective, optimization, action, targeting in models:
            budget = min(round(base_budget * mult, 2), payload.budget.max_daily_budget_brl)
            plans.append(CampaignPlanItem(
                external_id=item.external_id,
                product_name=item.product_name,
                campaign_model=model,
                priority=priority,
                action=action,
                campaign_name=f"ADI {model} | {safe_name} | Auto",
                adset_name=f"ADI {model} | {safe_name} | BR | Auto",
                ad_name=f"ADI {model} | {safe_name} | Criativo 01",
                objective=objective,
                daily_budget_brl=budget,
                optimization_goal=optimization,
                billing_event="IMPRESSIONS",
                campaign_status=status,
                adset_status=status,
                ad_status=status,
                promoted_object="link_click_to_affiliate_or_landing_page" if model != "V3_AUTOMACAO_PRINCIPAL" else "purchase_or_checkout_conversion",
                audience_notes=self._audience_notes(model),
                targeting=targeting,
                creative_variations=self._creative_variations(item, model),
                copy_variations=self._copy_variations(item, affiliate_result.affiliate_link, model),
                affiliate=affiliate_result,
                manual_review_required=payload.budget.require_manual_review,
                automation_notes=self._automation_notes(model),
            ))
        return plans


    def build_product_campaign_suite(self, payload: ProductCampaignSuiteRequest) -> ProductCampaignSuiteResponse:
        """Gera a arquitetura correta: V1, V2 e V3 são 3 campanhas diferentes.

        Cada campanha tem subnichos próprios e material próprio para PDF, imagem,
        vídeo e conteúdo. O retorno é dry-run por padrão para revisão antes da Meta API.
        """
        safe_product = self._safe_name(payload.product_name)
        final_link = str(payload.material.affiliate_link or payload.material.checkout_url or payload.material.landing_page_url)
        warnings: list[str] = []
        if payload.language == "auto_by_winning_ad":
            warnings.append("Idioma em modo automático: usar o idioma do anúncio campeão encontrado antes da publicação real.")
        if payload.device != "mobile_only":
            warnings.append("A estrutura ensinada recomenda somente celular para estes testes.")
        if payload.connection != "wifi_only":
            warnings.append("A estrutura ensinada recomenda somente Wi-Fi para reduzir perda por carregamento.")

        campaign_specs = [
            ("V1", f"{safe_product} V1", payload.v1_daily_budget_brl, payload.v1_subniches, "Campanha V1 independente: validação inicial por 5 subnichos, sem misturar com V2/V3."),
            ("V2", f"{safe_product} V2", payload.v2_daily_budget_brl, payload.v2_subniches, "Campanha V2 independente: performance com 4 subnichos/criativos no mesmo conceito estratégico."),
            ("V3", f"{safe_product} V3", payload.v3_daily_budget_brl, payload.v3_subniches, "Campanha V3 independente: validação avançada com 5 subnichos e orçamento/controlador próprio."),
        ]
        campaigns: list[ProductCampaignCategoryPlan] = []
        for campaign_type, campaign_name, budget, subniches, rule in campaign_specs:
            adsets: list[CampaignAdUnitPlan] = []
            for idx, sub in enumerate(subniches, start=1):
                code = f"SN{idx:02d}"
                adsets.append(CampaignAdUnitPlan(
                    adset_name=f"{campaign_name} | {code} | {sub.name}",
                    ad_name=f"{campaign_name} | {code} | AD01",
                    subniche=sub.name,
                    pixel_id=payload.pixel_id,
                    audience_type="open_with_subniche_angle_no_detailed_interests",
                    countries=payload.countries,
                    excluded_countries=payload.excluded_countries,
                    language=payload.language,
                    placements=payload.publisher_platforms,
                    removed_placements=payload.removed_placements,
                    device=payload.device,
                    connection=payload.connection,
                    primary_text=self._suite_copy(payload, sub, campaign_type),
                    final_link=final_link,
                    assets=self._suite_assets(payload, sub, campaign_type, code),
                    rules=self._suite_rules(campaign_type),
                ))
            campaigns.append(ProductCampaignCategoryPlan(
                campaign_type=campaign_type,
                campaign_name=campaign_name,
                daily_budget_brl=budget,
                structural_rule=rule,
                total_adsets=len(adsets),
                total_ads=len(adsets),
                adsets=adsets,
            ))

        checklist = [
            "V1, V2 e V3 foram separados em campanhas independentes do mesmo produto.",
            "V1 contém exatamente 5 subnichos.",
            "V2 contém exatamente 4 subnichos.",
            "V3 contém exatamente 5 subnichos.",
            "Cada subnicho gera 1 conjunto de anúncios e 1 anúncio principal.",
            "Pixel, evento Purchase, link final e idioma seguem o material do produto/anúncio campeão.",
            "A ferramenta gera briefing de PDF, imagem, vídeo e copy antes da publicação.",
            "Publicação real deve passar pelo Meta AI Campaign Operator com dry-run revisado.",
        ]
        return ProductCampaignSuiteResponse(
            product_name=payload.product_name,
            generated_at=datetime.now(UTC),
            dry_run=payload.dry_run,
            total_campaigns=len(campaigns),
            total_adsets=sum(c.total_adsets for c in campaigns),
            total_ads=sum(c.total_ads for c in campaigns),
            campaigns=campaigns,
            validation_checklist=checklist,
            warnings=warnings,
        )

    def _suite_copy(self, payload: ProductCampaignSuiteRequest, sub, campaign_type: str) -> str:
        prefix = {
            "V1": "Validação direta",
            "V2": "Performance controlada",
            "V3": "Ângulo campeão avançado",
        }[campaign_type]
        return (
            f"{prefix}: {sub.promise_angle}. "
            f"Se você sofre com {sub.audience_pain}, veja o material {payload.material.pdf_title}. "
            f"{payload.material.main_copy}"
        )[:2000]

    def _suite_assets(self, payload: ProductCampaignSuiteRequest, sub, campaign_type: str, code: str) -> list[GeneratedAssetBlueprint]:
        base = f"{payload.product_name} | {campaign_type} | {code} | {sub.name}"
        return [
            GeneratedAssetBlueprint(
                asset_type="pdf_content",
                name=f"{base} | PDF roteiro",
                prompt_or_brief=(
                    f"Criar conteúdo do PDF '{payload.material.pdf_title}' para o subnicho '{sub.name}'. "
                    f"Dor: {sub.audience_pain}. Promessa: {sub.promise_angle}. "
                    f"Descrição do produto: {payload.material.product_description}."
                ),
                format_rule="PDF vertical, linguagem do anúncio campeão, sem promessas proibidas, CTA para checkout.",
            ),
            GeneratedAssetBlueprint(
                asset_type="image",
                name=f"{base} | Imagem principal",
                prompt_or_brief=f"Imagem para Meta Ads com foco em {sub.promise_angle}. Direção visual: {sub.media_direction}.",
                format_rule="Manter formato original do criativo validado; sem mídia flexível.",
            ),
            GeneratedAssetBlueprint(
                asset_type="video",
                name=f"{base} | Vídeo principal",
                prompt_or_brief=f"Vídeo 15-30s: hook de 3s sobre {sub.audience_pain}, prova, solução e CTA para compra.",
                format_rule="Usar proporção original do modelo campeão; não permitir cortes automáticos.",
            ),
            GeneratedAssetBlueprint(
                asset_type="ad_copy",
                name=f"{base} | Copy",
                prompt_or_brief=f"Copy persuasiva no idioma correto para {sub.name}, com CTA direto e link final único.",
                format_rule="Mesma promessa central do subnicho; sem descrição se não for necessária.",
            ),
        ]

    @staticmethod
    def _suite_rules(campaign_type: str) -> list[str]:
        common = [
            "Objetivo: Vendas.",
            "Destino: Site.",
            "Evento: Purchase.",
            "Público aberto; sem interesses detalhados.",
            "Facebook e Instagram; remover Threads, Audience Network e Messenger.",
            "Somente celular e Wi-Fi.",
            "Não pausar antes de 3 dias, salvo erro técnico grave.",
        ]
        if campaign_type == "V1":
            return common + ["Usar 5 subnichos para validar ângulos iniciais do produto."]
        if campaign_type == "V2":
            return common + ["Usar 4 subnichos/criativos para performance controlada."]
        return common + ["Usar 5 subnichos avançados; escalar apenas os campeões com regras de proteção."]

    @staticmethod
    def _percent(part: int, total: int) -> float:
        return round((part / total) * 100, 2) if total else 0.0

    @staticmethod
    def _status(active_ads: int) -> str:
        if active_ads >= 40:
            return "TRICAMPEÃO"
        if active_ads >= 30:
            return "SUPER CAMPEÃO"
        if active_ads >= 20:
            return "CAMPEÃO"
        if active_ads >= 15:
            return "VALIDADO"
        return "TESTE"

    @staticmethod
    def _safe_name(value: str) -> str:
        return " ".join(value.strip().split())[:80]

    def _angles(self, item: FacebookAdSignal) -> list[str]:
        return [
            f"Dor direta: {item.lesson_profile.pain_point} ligada ao produto {item.product_name}.",
            f"Prova: usar {item.lesson_profile.proof_element} sem promessas proibidas.",
            f"Oferta: {item.lesson_profile.offer_angle}; CTA simples para ação imediata.",
        ]

    def _creative_variations(self, item: FacebookAdSignal, model: str) -> list[str]:
        if model == "V3_AUTOMACAO_PRINCIPAL":
            return [
                "Vídeo UGC 20-30s: hook nos 3s iniciais, dor, prova, solução e CTA.",
                "Imagem forte com headline de benefício + contraste antes/depois permitido pela política.",
                "Criativo de prova: demonstração do método, bastidores ou resultado sem promessa absoluta.",
            ]
        return [
            f"Criativo {item.lesson_profile.creative_style} explicando a dor principal.",
            "Imagem estática com promessa específica, benefício e CTA.",
            "Vídeo curto 15-25s com hook direto e prova simples.",
        ]

    def _copy_variations(self, item: FacebookAdSignal, affiliate_link: str, model: str) -> list[str]:
        if model == "V3_AUTOMACAO_PRINCIPAL":
            return [
                f"Você ainda tenta resolver {item.lesson_profile.pain_point} do jeito difícil? Veja esse método simples e direto: {affiliate_link}",
                f"O material de {item.product_name} foi estruturado para uma ação rápida: entenda a dor, aplique o passo a passo e avance hoje. {affiliate_link}",
                f"Se esse problema está travando seu resultado, comece pelo guia prático e veja a solução por dentro: {affiliate_link}",
            ]
        return [
            f"Novo teste validado para {item.product_name}: solução simples, explicada passo a passo. {affiliate_link}",
            f"Esse material mostra um caminho prático para resolver {item.lesson_profile.pain_point}. Acesse: {affiliate_link}",
        ]

    @staticmethod
    def _broad_targeting() -> dict:
        return {"geo_locations": {"countries": ["BR"]}, "age_min": 24, "age_max": 55}

    @staticmethod
    def _interest_targeting() -> dict:
        return {"geo_locations": {"countries": ["BR"]}, "age_min": 24, "age_max": 60, "publisher_platforms": ["facebook", "instagram"]}

    @staticmethod
    def _conversion_targeting() -> dict:
        return {"geo_locations": {"countries": ["BR"]}, "age_min": 25, "age_max": 60, "publisher_platforms": ["facebook", "instagram"], "facebook_positions": ["feed", "video_feeds", "marketplace"]}

    @staticmethod
    def _audience_notes(model: str) -> list[str]:
        if model == "V3_AUTOMACAO_PRINCIPAL":
            return ["Principal campanha de conversão.", "Usar criativos renovados para evitar saturação.", "Escalar somente após validar custo por checkout/compra."]
        if model == "V2_ESCALA_CONTROLADA":
            return ["Testar 2-3 ângulos por conjunto.", "Monitorar Connect Rate e Checkout antes de aumentar verba."]
        return ["Validação rápida de criativo e oferta.", "Verificar se cliques viram visualização de página."]

    @staticmethod
    def _automation_notes(model: str) -> list[str]:
        if model == "V3_AUTOMACAO_PRINCIPAL":
            return ["Modelo principal do robô.", "Publicação real depende de META_DRY_RUN=false e credenciais oficiais.", "Por padrão cria PAUSED; ACTIVE só com allow_active_launch=true e backend liberado."]
        return ["Modelo auxiliar para teste/escala controlada."]
