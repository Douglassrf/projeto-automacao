from app.schemas.ads import AdAnalysisResponse
from app.schemas.decision_logs import DecisionLogCreate


class DecisionFeedService:
    """Registers human-readable decisions for the dashboard timeline."""

    def __init__(self, repository):
        self.repository = repository

    def register_analysis_decisions(self, analysis: AdAnalysisResponse | object, user_id: int | None = None):
        decisions = self._build_analysis_decisions(analysis, user_id=user_id)
        return [self.repository.create(item) for item in decisions]

    def register_manual_decision(self, payload: DecisionLogCreate):
        return self.repository.create(payload)

    def _build_analysis_decisions(self, analysis, user_id: int | None = None) -> list[DecisionLogCreate]:
        campaign_id = f"analysis-{analysis.id}"
        product_name = analysis.product_name
        decisions: list[DecisionLogCreate] = []

        if analysis.connect_rate < 50:
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="CONNECT_RATE_CRITICAL",
                metric_name="Connect Rate",
                metric_value=analysis.connect_rate,
                threshold_value=75,
                severity="danger",
                tag_label="Atenção urgente",
                action_taken="parar_escala_e_corrigir_pagina",
                reasoning="Connect Rate crítico. Não escale: corrija link, velocidade, hospedagem ou redirecionamento.",
            ))
        elif analysis.connect_rate < 75:
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="CONNECT_RATE_LOW",
                metric_name="Connect Rate",
                metric_value=analysis.connect_rate,
                threshold_value=75,
                severity="warning",
                tag_label="Atenção necessária",
                action_taken="revisar_pagina_antes_de_escalar",
                reasoning="Connect Rate abaixo de 75%. Revise página, domínio e rastreamento antes de culpar o criativo.",
            ))
        else:
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="CONNECT_RATE_HEALTHY",
                metric_name="Connect Rate",
                metric_value=analysis.connect_rate,
                threshold_value=75,
                severity="success",
                tag_label="Bom/otimizado",
                action_taken="manter_monitoramento",
                reasoning="Connect Rate saudável. Agora avalie oferta, checkout, compra e ROAS antes de mexer no orçamento.",
            ))

        if analysis.active_ads >= 15:
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="THRESHOLD_WINNER",
                metric_name="Anúncios ativos",
                metric_value=analysis.active_ads,
                threshold_value=15,
                severity="success",
                tag_label="Otimização realizada",
                action_taken="mark_as_validated",
                reasoning="Produto passou de 15 anúncios ativos. Pode entrar na fila V1/V2/V3 se o funil também estiver saudável.",
            ))
        else:
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="THRESHOLD_NOT_MET",
                metric_name="Anúncios ativos",
                metric_value=analysis.active_ads,
                threshold_value=15,
                severity="info",
                tag_label="Observação",
                action_taken="do_not_scale_yet",
                reasoning="Ainda não bateu 15 anúncios ativos. Monitore mais dados antes de escalar.",
            ))

        if analysis.purchase_rate >= 2:
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="PURCHASE_RATE_SIGNAL",
                metric_name="Taxa de compra por página",
                metric_value=analysis.purchase_rate,
                threshold_value=2,
                severity="success",
                tag_label="Otimização realizada",
                action_taken="candidate_for_scaling",
                reasoning="Taxa de compra positiva. Candidato para V2/V3 ou novas variações.",
            ))
        elif analysis.checkout_rate >= 20 and analysis.purchases == 0:
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="CHECKOUT_WITHOUT_PURCHASE",
                metric_name="Compras",
                metric_value=analysis.purchases,
                threshold_value=1,
                severity="warning",
                tag_label="Atenção necessária",
                action_taken="review_checkout_trust",
                reasoning="Tem checkout, mas não tem compra. Revise preço, confiança, forma de pagamento e fricção.",
            ))

        return decisions
