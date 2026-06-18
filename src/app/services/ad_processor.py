from app.schemas.ads import AdAnalysisRequest


class AdProcessor:
    def __init__(self, repository):
        self.repository = repository

    def process(self, payload: AdAnalysisRequest, user_id: int | None = None):
        clicks = payload.link_clicks
        views = payload.landing_page_views
        checkouts = payload.checkout_starts
        purchases = payload.purchases

        connect_rate = self._percent(views, clicks)
        checkout_rate = self._percent(checkouts, views)
        purchase_rate = self._percent(purchases, views)
        checkout_to_purchase_rate = self._percent(purchases, checkouts)

        status = self._classify(payload.active_ads)
        score = self._score(payload.active_ads, connect_rate, checkout_rate, purchase_rate)
        insight = self._insight(connect_rate, checkout_rate, purchase_rate, checkout_to_purchase_rate, payload.active_ads)
        slug = self._slugify(payload.product_name)
        preview_url = f"/preview/{slug}"
        status_slug = self._slugify(status)
        edited_link = f"/lp/{slug}?utm_source=adintelligence&utm_status={status_slug}"

        return self.repository.save({
            "user_id": user_id if user_id is not None else payload.user_id,
            "product_name": payload.product_name,
            "active_ads": payload.active_ads,
            "cpc": payload.cpc,
            "link_clicks": clicks,
            "landing_page_views": views,
            "checkout_starts": checkouts,
            "purchases": purchases,
            "connect_rate": connect_rate,
            "checkout_rate": checkout_rate,
            "purchase_rate": purchase_rate,
            "score": score,
            "status": status,
            "preview_url": preview_url,
            "edited_link": edited_link,
            "insight": insight,
        })

    @staticmethod
    def _percent(part: int, total: int) -> float:
        return round((part / total) * 100, 2) if total > 0 else 0.0

    @staticmethod
    def _classify(active_ads: int) -> str:
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
    def _score(active_ads: int, connect_rate: float, checkout_rate: float, purchase_rate: float) -> float:
        score = (min(active_ads, 50) * 1.2) + (connect_rate * 0.25) + (checkout_rate * 0.2) + (purchase_rate * 2.2)
        return round(min(score, 100), 2)

    @staticmethod
    def _insight(connect_rate: float, checkout_rate: float, purchase_rate: float, checkout_to_purchase_rate: float, active_ads: int) -> str:
        alerts = []
        if active_ads >= 15:
            alerts.append("Produto com sinal de validação por volume de anúncios ativos.")
        else:
            alerts.append("Ainda não há volume suficiente de anúncios para considerar o produto validado.")

        if connect_rate < 75:
            alerts.append("Connect Rate abaixo de 75%; revise carregamento, domínio, velocidade e rastreamento da página.")
        else:
            alerts.append("Connect Rate saudável; a maioria dos cliques está chegando na página.")

        if checkout_rate < 20:
            alerts.append("Poucas pessoas avançam para checkout; revise promessa, preço, prova e CTA da página.")
        if purchase_rate >= 2:
            alerts.append("Taxa de compra com bom sinal inicial; vale testar novos criativos e remodelar a oferta.")
        elif checkout_to_purchase_rate < 20:
            alerts.append("Muitos chegam ao checkout, mas poucos compram; revise preço, confiança e meios de pagamento.")

        return " ".join(alerts)


    @staticmethod
    def _slugify(value: str) -> str:
        import re
        import unicodedata

        normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
        return slug or "produto"
