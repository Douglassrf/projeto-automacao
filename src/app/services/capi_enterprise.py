from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.schemas.capi_enterprise import (
    CapiBrowserPixelPayloadRequest,
    CapiBrowserPixelPayloadResponse,
    CapiEnterpriseEvent,
    CapiEnterpriseEventResult,
    CapiEnterpriseRequest,
    CapiEnterpriseResponse,
    CapiHealthResponse,
    CapiPreparedEvent,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = PROJECT_ROOT / "logs"
CAPI_ENTERPRISE_LOG = LOG_DIR / "capi_enterprise_events.log"
CAPI_DEDUP_LOG = LOG_DIR / "capi_event_ids.log"
_LOCK = threading.Lock()


class CapiEnterpriseService:
    """CAPI Enterprise: normalização, hashing, event_id e deduplicação Pixel+CAPI.

    Por padrão, opera em dry-run para evitar envio acidental. Quando CAPI_ENABLED=true,
    META_DRY_RUN=false, token e pixel estiverem configurados, envia para a Meta.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def ingest(self, payload: CapiEnterpriseRequest) -> CapiEnterpriseResponse:
        dry_run = self._resolve_dry_run(payload.dry_run)
        stored = 0
        forwarded = 0
        deduplicated = 0
        results: list[CapiEnterpriseEventResult] = []
        known_event_ids = self._load_event_ids()

        prepared_for_meta: list[dict[str, Any]] = []
        event_map: dict[str, CapiEnterpriseEvent] = {}
        for event in payload.events:
            prepared = self.prepare_event(event)
            event_map[prepared.event_id] = event
            warnings = self._validate_prepared_event(prepared)
            match_score = self._event_match_quality_score(prepared.user_data)

            if prepared.event_id in known_event_ids:
                deduplicated += 1
                results.append(
                    CapiEnterpriseEventResult(
                        event_id=prepared.event_id,
                        event_name=prepared.event_name,
                        status="deduplicated",
                        forwarded_to_meta=False,
                        deduplicated=True,
                        event_match_quality_score=match_score,
                        warnings=["Event ID já processado: bloqueado para evitar duplicidade de métricas."] + warnings,
                    )
                )
                continue

            record = {
                "received_at": datetime.now(UTC).isoformat(),
                "dry_run": dry_run,
                "prepared_event": prepared.model_dump(mode="json"),
                "event_match_quality_score": match_score,
                "warnings": warnings,
            }
            self._append_jsonl(CAPI_ENTERPRISE_LOG, record)
            self._append_jsonl(CAPI_DEDUP_LOG, {"event_id": prepared.event_id, "event_name": prepared.event_name, "stored_at": datetime.now(UTC).isoformat()})
            known_event_ids.add(prepared.event_id)
            stored += 1
            prepared_for_meta.append(prepared.model_dump(exclude_none=True))
            results.append(
                CapiEnterpriseEventResult(
                    event_id=prepared.event_id,
                    event_name=prepared.event_name,
                    status="stored",
                    forwarded_to_meta=False,
                    deduplicated=False,
                    event_match_quality_score=match_score,
                    warnings=warnings,
                )
            )

        if payload.forward_to_meta and prepared_for_meta:
            meta_response = self._send_to_meta(prepared_for_meta, payload.test_event_code, dry_run)
            for result in results:
                if result.status != "stored":
                    continue
                if meta_response.get("status") == "forwarded":
                    result.status = "forwarded"
                    result.forwarded_to_meta = True
                    result.meta_response = meta_response.get("response")
                    forwarded += 1
                elif meta_response.get("status") == "dry_run":
                    result.meta_response = meta_response
                else:
                    result.status = "blocked"
                    result.warnings.append(meta_response.get("message", "Envio CAPI bloqueado."))
                    result.meta_response = meta_response

        status = "ok" if not any(item.status == "error" for item in results) else "partial"
        return CapiEnterpriseResponse(
            status=status,
            received=len(payload.events),
            stored=stored,
            forwarded=forwarded,
            deduplicated=deduplicated,
            dry_run=dry_run,
            results=results,
            log_file=str(CAPI_ENTERPRISE_LOG),
        )

    def prepare_event(self, event: CapiEnterpriseEvent) -> CapiPreparedEvent:
        event_time = int((event.event_time or datetime.now(UTC)).timestamp())
        event_id = event.event_id or self._generate_event_id(event, event_time)
        user_data = self._build_user_data(event)
        custom_data: dict[str, Any] = {
            "currency": event.currency,
            "value": event.value,
            **event.custom_data,
        }
        if event.order_id:
            custom_data["order_id"] = event.order_id
        if event.product_name:
            custom_data["content_name"] = event.product_name
        if event.campaign_id:
            custom_data["campaign_id"] = event.campaign_id
        if event.ad_id:
            custom_data["ad_id"] = event.ad_id

        return CapiPreparedEvent(
            event_id=event_id,
            event_name=event.event_name,
            event_time=event_time,
            action_source=event.action_source,
            event_source_url=str(event.event_source_url) if event.event_source_url else None,
            user_data=user_data,
            custom_data=custom_data,
        )

    def browser_pixel_payload(self, payload: CapiBrowserPixelPayloadRequest) -> CapiBrowserPixelPayloadResponse:
        prepared = self.prepare_event(payload.event)
        browser_payload = {
            "eventID": prepared.event_id,
            "event": prepared.event_name,
            "value": prepared.custom_data.get("value", 0),
            "currency": prepared.custom_data.get("currency", "BRL"),
            "content_name": prepared.custom_data.get("content_name"),
        }
        return CapiBrowserPixelPayloadResponse(
            event_id=prepared.event_id,
            browser_payload=browser_payload,
            note="Use este mesmo eventID no fbq('track', ...) para a Meta deduplicar Browser Pixel + CAPI.",
        )

    def health(self) -> CapiHealthResponse:
        pixel_configured = bool(getattr(self.settings, "meta_pixel_id", None) or getattr(self.settings, "capi_pixel_id", None))
        token_configured = bool(self.settings.meta_access_token)
        dry_run = self._resolve_dry_run(None)
        production_ready = bool(self.settings.capi_enabled and token_configured and pixel_configured and not dry_run)
        recommendations: list[str] = []
        if not pixel_configured:
            recommendations.append("Configure META_PIXEL_ID ou CAPI_PIXEL_ID no .env.")
        if not token_configured:
            recommendations.append("Configure META_ACCESS_TOKEN com permissão para enviar eventos.")
        if dry_run:
            recommendations.append("CAPI está em dry-run; seguro para testes, mas não envia para a Meta.")
        if not self.settings.capi_enabled:
            recommendations.append("Defina CAPI_ENABLED=true para habilitar envio real quando estiver pronto.")
        recommendations.append("Envie o mesmo event_id no Pixel browser-side e na CAPI para deduplicação.")
        return CapiHealthResponse(
            capi_enabled=bool(self.settings.capi_enabled),
            dry_run=dry_run,
            pixel_configured=pixel_configured,
            token_configured=token_configured,
            test_event_code_configured=bool(self.settings.capi_test_event_code),
            production_ready=production_ready,
            recommendations=recommendations,
        )

    def _send_to_meta(self, data: list[dict[str, Any]], test_event_code: str | None, dry_run: bool) -> dict[str, Any]:
        pixel_id = self._pixel_id()
        if dry_run:
            return {"status": "dry_run", "message": "Payload preparado, mas não enviado por segurança.", "events": len(data)}
        if not self.settings.capi_enabled:
            return {"status": "blocked", "message": "CAPI_ENABLED=false."}
        if not pixel_id or not self.settings.meta_access_token:
            return {"status": "blocked", "message": "Pixel ID ou Meta Access Token ausente."}

        endpoint = f"https://graph.facebook.com/{self.settings.meta_api_version}/{pixel_id}/events"
        body: dict[str, Any] = {"data": data, "access_token": self.settings.meta_access_token}
        code = test_event_code or self.settings.capi_test_event_code
        if code:
            body["test_event_code"] = code
        try:
            with httpx.Client(timeout=20) as client:
                response = client.post(endpoint, json=body)
                response.raise_for_status()
                return {"status": "forwarded", "response": response.json()}
        except Exception as exc:  # pragma: no cover - rede externa não roda no teste local
            return {"status": "error", "message": f"Falha ao enviar para Meta CAPI: {exc}"}

    def _build_user_data(self, event: CapiEnterpriseEvent) -> dict[str, Any]:
        customer = event.customer
        user_data: dict[str, Any] = {}
        hashed_fields = {
            "em": self._hash_email(customer.email),
            "ph": self._hash_phone(customer.phone),
            "fn": self._hash_text(customer.first_name),
            "ln": self._hash_text(customer.last_name),
            "ct": self._hash_text(customer.city),
            "st": self._hash_text(customer.state),
            "zp": self._hash_zip(customer.zip_code),
            "country": self._hash_text(customer.country),
            "external_id": self._hash_text(customer.external_id),
        }
        for key, value in hashed_fields.items():
            if value:
                user_data[key] = [value] if key in {"em", "ph"} else value
        if customer.client_ip_address:
            user_data["client_ip_address"] = customer.client_ip_address.strip()
        if customer.client_user_agent:
            user_data["client_user_agent"] = customer.client_user_agent.strip()
        if customer.fbp:
            user_data["fbp"] = customer.fbp.strip()
        if customer.fbc:
            user_data["fbc"] = customer.fbc.strip()
        return user_data

    def _event_match_quality_score(self, user_data: dict[str, Any]) -> int:
        score = 0
        if user_data.get("em"):
            score += 25
        if user_data.get("ph"):
            score += 20
        if user_data.get("client_ip_address"):
            score += 15
        if user_data.get("client_user_agent"):
            score += 15
        if user_data.get("fbp") or user_data.get("fbc"):
            score += 15
        if user_data.get("fn") and user_data.get("ln"):
            score += 5
        if user_data.get("country"):
            score += 5
        return min(score, 100)

    def _validate_prepared_event(self, prepared: CapiPreparedEvent) -> list[str]:
        warnings: list[str] = []
        if prepared.event_name == "Purchase" and float(prepared.custom_data.get("value") or 0) <= 0:
            warnings.append("Purchase sem valor de compra; ROAS pode ficar incorreto.")
        if not prepared.user_data.get("em") and not prepared.user_data.get("ph"):
            warnings.append("Sem e-mail/telefone hashado; Event Match Quality tende a ficar baixo.")
        if not prepared.user_data.get("client_ip_address") or not prepared.user_data.get("client_user_agent"):
            warnings.append("IP/User-Agent ausentes; envie esses campos no backend quando possível.")
        if not prepared.event_source_url and prepared.action_source == "website":
            warnings.append("event_source_url ausente para evento website.")
        return warnings

    def _generate_event_id(self, event: CapiEnterpriseEvent, event_time: int) -> str:
        stable_parts = [event.event_name, event.order_id or "", event.campaign_id or "", event.ad_id or "", str(event.value), event.currency, str(event_time)]
        if event.order_id:
            return "evt_" + hashlib.sha256("|".join(stable_parts).encode()).hexdigest()[:32]
        return "evt_" + uuid4().hex

    def _hash_email(self, value: str | None) -> str | None:
        if not value:
            return None
        return self._sha256(value.strip().lower())

    def _hash_phone(self, value: str | None) -> str | None:
        if not value:
            return None
        digits = re.sub(r"\D+", "", value)
        return self._sha256(digits) if digits else None

    def _hash_text(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = " ".join(value.strip().lower().split())
        return self._sha256(normalized) if normalized else None

    def _hash_zip(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = re.sub(r"\s+", "", value.strip().lower())
        return self._sha256(normalized) if normalized else None

    def _sha256(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _load_event_ids(self) -> set[str]:
        if not CAPI_DEDUP_LOG.exists():
            return set()
        ids: set[str] = set()
        for line in CAPI_DEDUP_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_id = record.get("event_id")
            if event_id:
                ids.add(str(event_id))
        return ids

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        with _LOCK:
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _pixel_id(self) -> str | None:
        return getattr(self.settings, "capi_pixel_id", None) or getattr(self.settings, "meta_pixel_id", None)

    def _resolve_dry_run(self, requested: bool | None) -> bool:
        if requested is not None:
            return requested
        return bool(self.settings.meta_dry_run or not self.settings.capi_enabled)
