from __future__ import annotations

from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import AlertEvent
from app.services.diagnostics_service import STATUS_OK, DiagnosticsService

ALERT_STATUS_OPEN = "open"
ALERT_STATUS_RESOLVED = "resolved"


def _event_to_dict(event: AlertEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "check_name": event.check_name,
        "severity": event.severity,
        "message": event.message,
        "status": event.status,
        "first_seen_at": event.first_seen_at,
        "last_seen_at": event.last_seen_at,
        "resolved_at": event.resolved_at,
    }


class AlertService:
    """Missao 46 - Sistema de Alertas.

    Avalia DiagnosticsService.run_full_diagnostics() (Missao 44) e
    transforma checks com status != ok em eventos persistidos
    (AlertEvent) - a diferenca entre "diagnostico" (snapshot sem estado,
    recalculado do zero a cada chamada) e "alerta" (algo que abre quando
    um problema aparece, continua aberto enquanto o problema persiste, e
    se resolve sozinho quando o check correspondente volta a ok).

    De-duplicacao: no maximo um AlertEvent com status="open" por
    check_name. Reavaliacoes sucessivas do mesmo problema atualizam
    severity/message/last_seen_at em vez de criar linhas novas - sem isso,
    rodar evaluate() periodicamente (ex.: via Missao 47 ou um cron futuro)
    inundaria a tabela com um evento por execucao."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.diagnostics = DiagnosticsService(db)

    def _open_event_for(self, check_name: str) -> AlertEvent | None:
        return (
            self.db.query(AlertEvent)
            .filter(AlertEvent.check_name == check_name, AlertEvent.status == ALERT_STATUS_OPEN)
            .first()
        )

    def evaluate(self) -> dict[str, Any]:
        """Roda os diagnosticos completos e abre/atualiza/resolve
        AlertEvents conforme o status de cada check. Retorna um resumo da
        avaliacao (nao a lista completa de alertas - usar active_alerts()
        ou history() para isso)."""

        report = self.diagnostics.run_full_diagnostics()
        opened: list[str] = []
        updated: list[str] = []
        resolved: list[str] = []

        for check in report["checks"]:
            name = check["name"]
            existing = self._open_event_for(name)

            if check["status"] == STATUS_OK:
                if existing is not None:
                    existing.status = ALERT_STATUS_RESOLVED
                    existing.resolved_at = datetime.now(UTC)
                    self.db.commit()
                    resolved.append(name)
                continue

            if existing is not None:
                existing.severity = check["status"]
                existing.message = check["message"]
                existing.last_seen_at = datetime.now(UTC)
                self.db.commit()
                updated.append(name)
            else:
                event = AlertEvent(
                    check_name=name,
                    severity=check["status"],
                    message=check["message"],
                    status=ALERT_STATUS_OPEN,
                )
                self.db.add(event)
                self.db.commit()
                opened.append(name)

        return {
            "overall_status": report["status"],
            "evaluated_at": report["generated_at"],
            "opened": opened,
            "updated": updated,
            "resolved": resolved,
        }

    def active_alerts(self) -> list[dict[str, Any]]:
        """Todos os AlertEvents com status="open", mais recentes primeiro."""
        rows = (
            self.db.query(AlertEvent)
            .filter(AlertEvent.status == ALERT_STATUS_OPEN)
            .order_by(AlertEvent.first_seen_at.desc())
            .all()
        )
        return [_event_to_dict(row) for row in rows]

    def history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Eventos (open + resolved) mais recentes primeiro, limitados a
        `limit` (default: settings.alert_history_default_limit)."""
        effective_limit = limit if limit is not None else self.settings.alert_history_default_limit
        rows = (
            self.db.query(AlertEvent)
            .order_by(AlertEvent.first_seen_at.desc())
            .limit(effective_limit)
            .all()
        )
        return [_event_to_dict(row) for row in rows]
