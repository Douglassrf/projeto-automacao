"""Cliente opcional da Ad Library via Apify, com limites para o plano gratuito."""

from __future__ import annotations

import os
from typing import Any

import httpx


DEFAULT_ACTOR = "automation-lab/facebook-ads-library"
FREE_MAX_ADS_PER_RUN = 50


def _enabled(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def token() -> str | None:
    value = (os.getenv("APIFY_TOKEN") or "").strip()
    return value or None


def free_mode() -> bool:
    return _enabled(os.getenv("APIFY_FREE_MODE"), default=True)


def actor_id() -> str:
    return (os.getenv("APIFY_META_ADS_ACTOR") or DEFAULT_ACTOR).strip()


def status() -> dict[str, Any]:
    configured = token() is not None
    return {
        "provider": "apify",
        "configured": configured,
        "free_mode": free_mode(),
        "actor": actor_id(),
        "max_ads_per_run": FREE_MAX_ADS_PER_RUN if free_mode() else 500,
        "cron_allowed": _enabled(os.getenv("APIFY_ALLOW_CRON"), default=False),
        "message": (
            "Apify gratuito configurado." if configured
            else "Defina APIFY_TOKEN na Vercel para ativar o provedor gratuito."
        ),
    }


def _actor_api_id(value: str) -> str:
    return value.replace("/", "~", 1)


def _normalize(item: dict[str, Any]) -> dict[str, Any]:
    body = item.get("bodyText") or item.get("body") or item.get("adText")
    title = item.get("title") or item.get("headline")
    archive_id = item.get("adArchiveId") or item.get("adArchiveID") or item.get("adId")
    page_id = item.get("pageId") or item.get("page_id")
    page_name = item.get("pageName") or item.get("page_name")
    snapshot = item.get("adLibraryUrl")
    if not snapshot and archive_id:
        snapshot = f"https://www.facebook.com/ads/library/?id={archive_id}"
    return {
        "id": str(archive_id) if archive_id is not None else None,
        "page_id": str(page_id) if page_id is not None else None,
        "page_name": page_name,
        "ad_creative_bodies": [body] if body else [],
        "ad_creative_link_titles": [title] if title else [],
        "ad_creative_link_descriptions": [item.get("linkDescription")]
        if item.get("linkDescription") else [],
        "ad_snapshot_url": snapshot,
        "ad_delivery_start_time": item.get("startDateFormatted") or item.get("startDate"),
        "currency": item.get("currency"),
        "languages": item.get("languages") or [],
        "publisher_platforms": item.get("platforms") or item.get("publisherPlatform") or [],
    }


def fetch_ads(
    search_terms: str,
    *,
    country: str,
    limit: int,
) -> dict[str, Any]:
    api_token = token()
    if not api_token:
        return {
            "status": "error",
            "error": "missing_apify_token",
            "message": "Defina APIFY_TOKEN na Vercel. Nao envie o token pelo chat.",
        }

    requested = max(1, int(limit))
    hard_limit = FREE_MAX_ADS_PER_RUN if free_mode() else 500
    capped_limit = min(requested, hard_limit)
    actor = actor_id()
    url = (
        "https://api.apify.com/v2/acts/"
        f"{_actor_api_id(actor)}/run-sync-get-dataset-items"
    )
    payload = {
        "searchQueries": [search_terms],
        "country": country,
        "activeStatus": "active",
        "maxAds": capped_limit,
    }
    try:
        with httpx.Client(timeout=120) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {api_token}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "status": "error",
            "error": "apify_http_error",
            "code": exc.response.status_code,
            "message": "O Apify recusou a execucao. Verifique token, saldo gratuito e Actor.",
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "status": "error",
            "error": "apify_network_error",
            "message": str(exc),
        }

    if not isinstance(data, list):
        return {
            "status": "error",
            "error": "apify_invalid_response",
            "message": "O Actor nao devolveu uma lista de anuncios.",
        }
    ads = [_normalize(item) for item in data if isinstance(item, dict)]
    ads = [ad for ad in ads if ad.get("page_id")]
    return {
        "status": "ok",
        "provider": "apify",
        "actor": actor,
        "free_mode": free_mode(),
        "requested_limit": requested,
        "applied_limit": capped_limit,
        "ads": ads,
    }
