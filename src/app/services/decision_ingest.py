from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from app.schemas.decision_logs import DecisionLogCreate
from app.services.decision_feed import DecisionFeedService


@dataclass
class ImportResult:
    rows_read: int
    decisions_created: int
    campaigns_evaluated: int
    warnings: list[str]


class DecisionDataIngestService:
    """Converts real/dry-run Meta Ads exports into decision timeline events.

    The service accepts CSV exports from Ads Manager or internal dry-run reports. It
    intentionally keeps header matching flexible because Meta exports vary by UI
    language and account configuration.
    """

    HEADER_ALIASES = {
        "campaign_id": ["campaign_id", "campaign id", "id da campanha", "identificacao da campanha", "identificação da campanha"],
        "campaign_name": ["campaign_name", "campaign name", "nome da campanha", "campanha"],
        "product_name": ["product_name", "produto", "nome do produto"],
        "spend": ["spend", "amount spent", "valor gasto", "gasto", "valor usado"],
        "link_clicks": ["link clicks", "link_clicks", "cliques no link", "cliques"],
        "landing_page_views": ["landing page views", "landing_page_views", "visualizações da página de destino", "visualizacoes de pagina", "visualizações de página", "visualizacoes da pagina de destino"],
        "checkouts": ["checkouts", "checkout", "início de checkout", "inicio de checkout", "inicios de checkout", "inícios de checkout"],
        "purchases": ["purchases", "compras", "purchase"],
        "cost_per_purchase": ["cost per purchase", "custo por compra", "cpa"],
        "roas": ["roas", "purchase roas", "retorno sobre gasto com anuncios", "retorno sobre gasto com anúncios"],
    }

    def __init__(self, decision_feed: DecisionFeedService):
        self.decision_feed = decision_feed

    def import_csv_text(self, content: str, user_id: int | None = None) -> ImportResult:
        stream = io.StringIO(content.strip())
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            return ImportResult(rows_read=0, decisions_created=0, campaigns_evaluated=0, warnings=["CSV sem cabeçalho."])

        rows_read = 0
        decisions_created = 0
        campaigns_evaluated = 0
        warnings: list[str] = []

        for raw_row in reader:
            rows_read += 1
            normalized = self._normalize_row(raw_row)
            campaign_id = normalized.get("campaign_id") or normalized.get("campaign_name") or f"csv-row-{rows_read}"
            product_name = normalized.get("product_name") or normalized.get("campaign_name") or "Campanha importada"

            decisions = self._evaluate_campaign(normalized, campaign_id=campaign_id, product_name=product_name, user_id=user_id)
            if not decisions:
                warnings.append(f"Linha {rows_read}: dados insuficientes para decisão.")
                continue

            campaigns_evaluated += 1
            for decision in decisions:
                self.decision_feed.register_manual_decision(decision)
                decisions_created += 1

        return ImportResult(
            rows_read=rows_read,
            decisions_created=decisions_created,
            campaigns_evaluated=campaigns_evaluated,
            warnings=warnings[:20],
        )

    def create_crisis_scenario(self, user_id: int | None = None) -> list[Any]:
        """Creates intentionally bad metrics to validate the timeline response."""
        rows = [
            {
                "campaign_id": "CRISIS-V2-AD01",
                "campaign_name": "Crise V2 AD01",
                "spend": 62,
                "link_clicks": 320,
                "landing_page_views": 121,
                "checkouts": 4,
                "purchases": 0,
                "roas": 0,
            },
            {
                "campaign_id": "CRISIS-V3-AD03",
                "campaign_name": "Crise V3 AD03",
                "spend": 84,
                "link_clicks": 190,
                "landing_page_views": 160,
                "checkouts": 18,
                "purchases": 0,
                "roas": 0,
            },
            {
                "campaign_id": "HEALTHY-V3-AD02",
                "campaign_name": "Saudável V3 AD02",
                "spend": 45,
                "link_clicks": 210,
                "landing_page_views": 182,
                "checkouts": 22,
                "purchases": 4,
                "roas": 3.4,
            },
        ]
        created = []
        for row in rows:
            decisions = self._evaluate_campaign(row, campaign_id=row["campaign_id"], product_name=row["campaign_name"], user_id=user_id)
            for decision in decisions:
                created.append(self.decision_feed.register_manual_decision(decision))
        return created

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized_headers = {self._normalize_key(key): value for key, value in row.items()}
        output: dict[str, Any] = {}
        for canonical, aliases in self.HEADER_ALIASES.items():
            for alias in aliases:
                value = normalized_headers.get(self._normalize_key(alias))
                if value not in (None, ""):
                    output[canonical] = value
                    break
        return output

    def _evaluate_campaign(self, row: dict[str, Any], campaign_id: str, product_name: str, user_id: int | None) -> list[DecisionLogCreate]:
        spend = self._number(row.get("spend"))
        link_clicks = int(self._number(row.get("link_clicks")))
        lpv = int(self._number(row.get("landing_page_views")))
        checkouts = int(self._number(row.get("checkouts")))
        purchases = int(self._number(row.get("purchases")))
        roas = self._number(row.get("roas"))
        cpa = self._number(row.get("cost_per_purchase"))
        decisions: list[DecisionLogCreate] = []

        if link_clicks > 0:
            connect_rate = round((lpv / link_clicks) * 100, 2)
            if connect_rate < 50 and link_clicks >= 50:
                decisions.append(DecisionLogCreate(
                    user_id=user_id,
                    campaign_id=campaign_id,
                    product_name=product_name,
                    reason_code="CONNECT_RATE_CRITICAL",
                    metric_name="Connect Rate",
                    metric_value=connect_rate,
                    threshold_value=75,
                    severity="danger",
                    tag_label="Atenção urgente",
                    action_taken="parar_escala_e_corrigir_pagina",
                    reasoning="Connect Rate crítico. Não escale: o clique não está virando página carregada. Corrija link, velocidade, hospedagem ou redirecionamento.",
                ))
            elif connect_rate < 75:
                decisions.append(DecisionLogCreate(
                    user_id=user_id,
                    campaign_id=campaign_id,
                    product_name=product_name,
                    reason_code="CONNECT_RATE_LOW",
                    metric_name="Connect Rate",
                    metric_value=connect_rate,
                    threshold_value=75,
                    severity="warning",
                    tag_label="Atenção necessária",
                    action_taken="revisar_pagina_antes_de_escalar",
                    reasoning="Connect Rate abaixo de 75%. O gargalo provável está na página, carregamento ou rastreamento; ainda não culpe o criativo.",
                ))
            else:
                decisions.append(DecisionLogCreate(
                    user_id=user_id,
                    campaign_id=campaign_id,
                    product_name=product_name,
                    reason_code="CONNECT_RATE_HEALTHY",
                    metric_name="Connect Rate",
                    metric_value=connect_rate,
                    threshold_value=75,
                    severity="success",
                    tag_label="Bom/otimizado",
                    action_taken="manter_monitoramento",
                    reasoning="Connect Rate saudável. Agora avalie página, checkout, compra e ROAS antes de mexer no orçamento.",
                ))

        if spend >= 50 and purchases == 0:
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="SPEND_WITHOUT_PURCHASE_CRITICAL",
                metric_name="Gasto sem compra",
                metric_value=spend,
                threshold_value=50,
                severity="danger",
                tag_label="Atenção urgente",
                action_taken="pausar_conjunto_ou_campanha",
                reasoning="Gasto passou de R$50 sem compra. Proteja verba: pause ou revise oferta/checkout antes de continuar.",
            ))
        elif spend >= 25 and purchases == 0:
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="SPEND_WITHOUT_PURCHASE_WARNING",
                metric_name="Gasto sem compra",
                metric_value=spend,
                threshold_value=25,
                severity="warning",
                tag_label="Atenção necessária",
                action_taken="notificar_e_observar",
                reasoning="Gasto passou de R$25 sem compra. Ainda não é crise total, mas exige atenção antes de deixar consumir mais verba.",
            ))

        if checkouts >= 5 and purchases == 0:
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="CHECKOUT_WITHOUT_PURCHASE",
                metric_name="Checkout sem compra",
                metric_value=checkouts,
                threshold_value=1,
                severity="warning",
                tag_label="Atenção necessária",
                action_taken="revisar_checkout_preco_confianca",
                reasoning="Tem checkout, mas não tem compra. Revise preço, prova, confiança, forma de pagamento e fricção do checkout.",
            ))

        if purchases > 0 or roas > 0:
            if roas >= 2:
                decisions.append(DecisionLogCreate(
                    user_id=user_id,
                    campaign_id=campaign_id,
                    product_name=product_name,
                    reason_code="ROAS_HEALTHY",
                    metric_name="ROAS",
                    metric_value=roas,
                    threshold_value=2,
                    severity="success",
                    tag_label="Bom/otimizado",
                    action_taken="candidato_para_escala_controlada",
                    reasoning="ROAS acima de 2. Campanha candidata para escala controlada, sem mudança brusca de orçamento.",
                ))
            elif roas < 1:
                decisions.append(DecisionLogCreate(
                    user_id=user_id,
                    campaign_id=campaign_id,
                    product_name=product_name,
                    reason_code="ROAS_NEGATIVE",
                    metric_name="ROAS",
                    metric_value=roas,
                    threshold_value=1,
                    severity="danger",
                    tag_label="Atenção urgente",
                    action_taken="nao_escalar_revisar_funil",
                    reasoning="ROAS abaixo de 1. Não aumente verba; encontre o gargalo antes de continuar.",
                ))

        if cpa > 0 and purchases > 0:
            severity = "warning" if cpa >= 50 else "success"
            decisions.append(DecisionLogCreate(
                user_id=user_id,
                campaign_id=campaign_id,
                product_name=product_name,
                reason_code="CPA_REVIEW",
                metric_name="Custo por compra",
                metric_value=cpa,
                threshold_value=50,
                severity=severity,
                tag_label="Atenção necessária" if severity == "warning" else "Bom/otimizado",
                action_taken="comparar_com_margem_do_produto",
                reasoning="Compare o CPA com sua margem real. Escale somente se sobrar lucro depois da taxa da plataforma e reembolso.",
            ))

        return decisions

    @staticmethod
    def _normalize_key(value: str) -> str:
        import unicodedata

        normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
        return normalized.strip().lower().replace("_", " ")

    @staticmethod
    def _number(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        text = str(value).strip().replace("R$", "").replace("%", "").replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return 0.0
