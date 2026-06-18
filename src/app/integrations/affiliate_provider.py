from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.core.config import get_settings
from app.integrations.activity_logger import write_affiliate_activity
from app.schemas.affiliate import AffiliateReplaceRequest, AffiliateReplaceResponse

URL_PATTERN = re.compile(r"https?://[^\s\)\]\}\'\"<>]+", re.IGNORECASE)


class AffiliateIntegrationError(RuntimeError):
    """Raised when an affiliate link cannot be created safely."""


@dataclass(frozen=True)
class AffiliateCredentials:
    provider: str
    api_key: str | None
    api_secret: str | None
    default_affiliate_id: str | None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)


class AffiliateProvider:
    """Provider adapter for affiliate networks.

    The first production version keeps credentials on the backend only and exposes a
    stable contract for real network adapters such as Hotmart, Kiwify, Eduzz or Braip.
    When no external API is configured, it can still generate a deterministic local
    tracking link using the affiliate id, which keeps local development functional.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.credentials = AffiliateCredentials(
            provider=settings.affiliate_network,
            api_key=settings.affiliate_api_key,
            api_secret=settings.affiliate_api_secret,
            default_affiliate_id=settings.affiliate_default_id,
        )
        self.mock_enabled = settings.affiliate_mock_enabled

    def replace_link(self, payload: AffiliateReplaceRequest) -> AffiliateReplaceResponse:
        original_link = str(payload.destination_url) if payload.destination_url else self.extract_first_link(payload.creative_original)

        if not original_link:
            raise AffiliateIntegrationError("Nenhum link de destino foi encontrado no criativo original.")

        affiliate_link = self.build_affiliate_link(
            original_link=original_link,
            fallback_affiliate_link=str(payload.fallback_affiliate_link) if payload.fallback_affiliate_link else None,
            affiliate_id=payload.user_affiliate_id or self.credentials.default_affiliate_id,
            network=payload.network or self.credentials.provider,
        )

        creative_updated = self.replace_first_occurrence(payload.creative_original, original_link, affiliate_link)

        write_affiliate_activity(payload.ad_id, original_link, affiliate_link)

        return AffiliateReplaceResponse(
            network=payload.network or self.credentials.provider,
            original_link=original_link,
            affiliate_link=affiliate_link,
            creative_updated=creative_updated,
            provider_status="configured" if self.credentials.configured else "local_mock",
            message="Link de afiliado aplicado com sucesso.",
        )

    def extract_first_link(self, creative: str) -> str:
        match = URL_PATTERN.search(creative)
        return match.group(0).rstrip(".,;") if match else ""

    def build_affiliate_link(
        self,
        original_link: str,
        fallback_affiliate_link: str | None,
        affiliate_id: str | None,
        network: str,
    ) -> str:
        if fallback_affiliate_link:
            return fallback_affiliate_link

        if self.credentials.configured:
            # Placeholder adapter point: real provider SDK/HTTP calls should be added here.
            # The safe default still returns a trackable link without exposing secrets.
            return self.append_tracking_params(original_link, affiliate_id, network)

        if not self.mock_enabled:
            raise AffiliateIntegrationError(
                "Integração de afiliados não configurada. Defina AFFILIATE_API_KEY e AFFILIATE_API_SECRET no backend."
            )

        return self.append_tracking_params(original_link, affiliate_id, network)

    def append_tracking_params(self, url: str, affiliate_id: str | None, network: str) -> str:
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.update(
            {
                "utm_source": "adintelligence_pro",
                "utm_medium": "affiliate",
                "utm_campaign": network.lower().strip() or "generic",
            }
        )
        if affiliate_id:
            query["aff_id"] = affiliate_id
        return urlunparse(parsed._replace(query=urlencode(query)))

    def replace_first_occurrence(self, creative: str, original_link: str, affiliate_link: str) -> str:
        if original_link in creative:
            return creative.replace(original_link, affiliate_link, 1)
        return f"{creative.rstrip()}\n\nLink de afiliado: {affiliate_link}"
