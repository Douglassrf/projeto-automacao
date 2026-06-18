from datetime import UTC, datetime

from app.integrations.affiliate_provider import AffiliateProvider
from app.repositories.ad_repository import AdRepository
from app.schemas.ads import AdAnalysisRequest
from app.schemas.affiliate import AffiliateReplaceRequest
from app.schemas.automation import BatchProcessItemResult, BatchProcessRequest, BatchProcessResponse
from app.services.ad_processor import AdProcessor


class AutomationProcessor:
    """Runs the full collection -> batch analysis -> threshold decision -> affiliate optimization pipeline."""

    def __init__(self, repository: AdRepository, affiliate_provider: AffiliateProvider | None = None):
        self.repository = repository
        self.ad_processor = AdProcessor(repository)
        self.affiliate_provider = affiliate_provider or AffiliateProvider()

    def process_feed(self, payload: BatchProcessRequest, user_id: int | None = None) -> BatchProcessResponse:
        started_at = datetime.now(UTC)
        results: list[BatchProcessItemResult] = []
        winners = 0
        optimized = 0
        rejected = 0

        for item in payload.items:
            analysis = self.ad_processor.process(
                AdAnalysisRequest(
                    product_name=item.product_name,
                    active_ads=item.active_ads,
                    cpc=item.cpc,
                    link_clicks=item.link_clicks,
                    landing_page_views=item.landing_page_views,
                    checkout_starts=item.checkout_starts,
                    purchases=item.purchases,
                ),
                user_id=user_id,
            )

            is_winner = payload.threshold_min <= item.active_ads <= payload.threshold_max
            decision = "winner" if is_winner else "rejected"
            reason = (
                f"Aprovado: {item.active_ads} anúncios ativos dentro do threshold {payload.threshold_min}-{payload.threshold_max}."
                if is_winner
                else f"Rejeitado: {item.active_ads} anúncios ativos fora do threshold {payload.threshold_min}-{payload.threshold_max}."
            )

            affiliate_result = None
            if is_winner:
                winners += 1
                base_link = str(item.destination_url) if item.destination_url else analysis.edited_link
                creative = item.creative_original
                if base_link not in creative:
                    creative = f"{creative.rstrip()}\n\nAcesse: {base_link}"

                affiliate_result = self.affiliate_provider.replace_link(
                    AffiliateReplaceRequest(
                        ad_id=analysis.id,
                        creative_original=creative,
                        network=payload.affiliate.network,
                        user_affiliate_id=payload.affiliate.user_affiliate_id,
                        destination_url=item.destination_url,
                        fallback_affiliate_link=payload.affiliate.fallback_affiliate_link,
                    )
                )
                optimized += 1
            else:
                rejected += 1

            results.append(
                BatchProcessItemResult(
                    external_id=item.external_id,
                    product_name=item.product_name,
                    active_ads=item.active_ads,
                    decision=decision,
                    reason=reason,
                    analysis=analysis,
                    affiliate=affiliate_result,
                )
            )

        finished_at = datetime.now(UTC)
        return BatchProcessResponse(
            started_at=started_at,
            finished_at=finished_at,
            total_received=len(payload.items),
            analyzed=len(results),
            winners=winners,
            optimized=optimized,
            rejected=rejected,
            threshold_min=payload.threshold_min,
            threshold_max=payload.threshold_max,
            results=results,
        )
