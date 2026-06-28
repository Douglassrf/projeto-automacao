from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import detect_environment, validate_settings
from app.services.cache_service import CacheService
from app.services.queue_service import QueueService

STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_CRITICAL = "critical"

_SEVERITY = {STATUS_OK: 0, STATUS_WARNING: 1, STATUS_CRITICAL: 2}

_DIAGNOSTICS_CACHE_NAMESPACE = "__diagnostics__"


def _worst(statuses: list[str]) -> str:
    if not statuses:
        return STATUS_OK
    return max(statuses, key=lambda s: _SEVERITY[s])


@dataclass
class DiagnosticCheck:
    name: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }


class UnknownDiagnosticCheckError(ValueError):
    """Levantado quando run_check() recebe um nome de check inexistente."""


class DiagnosticsService:
    """Missao 44 - Diagnostico Automatico.

    Agrega, em uma unica chamada, sinais que ja existem espalhados em
    servicos das missoes anteriores:
    - QueueService.health_report() (Missao 42): jobs travados/em inanicao,
      filas com taxa de falha acima do limite.
    - CacheService (Missao 43): em vez de inventar uma heuristica de
      "saude" para o cache (o que produziria falsos positivos - uma baixa
      taxa de hit pode ser normal para certas cargas), este check faz uma
      sondagem funcional real: grava uma chave de prova, le de volta, e
      confere o valor - se o roundtrip falhar, o cache esta realmente
      quebrado, nao apenas "com estatisticas estranhas".
    - validate_settings() (Missao 41): problemas de configuracao.

    Mais dois checks novos, que nao existiam antes desta missao:
    - database: round-trip "SELECT 1" no banco ativo.
    - disk: espaco livre no caminho configurado (diagnostics_disk_path),
      com dois limiares (warning/critical).

    Sem estado novo: cada chamada calcula um snapshot fresco a partir do
    estado atual dos servicos - nao ha tabela de historico (decisao
    deliberada, para manter o escopo desta missao limitado a
    *diagnostico/leitura*, sem se sobrepor a uma futura gestao/enforcement
    de recursos)."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    # -- checks individuais -------------------------------------------------

    def check_database(self) -> DiagnosticCheck:
        try:
            self.db.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            return DiagnosticCheck(
                "database",
                STATUS_CRITICAL,
                "Banco de dados inacessivel.",
                {"error": type(exc).__name__},
            )
        return DiagnosticCheck("database", STATUS_OK, "Banco de dados respondendo normalmente.", {})

    def check_queue(self) -> DiagnosticCheck:
        report = QueueService(self.db).health_report()
        if report["unhealthy_queues"]:
            status = STATUS_CRITICAL
        elif report["stuck_jobs"] or report["starving_jobs"]:
            status = STATUS_WARNING
        else:
            status = STATUS_OK

        if report["warnings"]:
            message = " | ".join(report["warnings"])
        else:
            message = "Filas saudaveis: nenhum job travado, em inanicao, ou fila com taxa de falha acima do limite."

        return DiagnosticCheck(
            "queue",
            status,
            message,
            {
                "unhealthy_queues": report["unhealthy_queues"],
                "stuck_jobs_count": len(report["stuck_jobs"]),
                "starving_jobs_count": len(report["starving_jobs"]),
                "per_queue": report["per_queue"],
            },
        )

    def check_cache(self) -> DiagnosticCheck:
        cache = CacheService(self.db)
        probe_key = f"probe-{uuid.uuid4().hex[:8]}"
        probe_value = {"ts": datetime.now(UTC).isoformat()}
        try:
            cache.set(probe_key, probe_value, namespace=_DIAGNOSTICS_CACHE_NAMESPACE, ttl_seconds=30)
            readback = cache.get(probe_key, namespace=_DIAGNOSTICS_CACHE_NAMESPACE)
            roundtrip_ok = readback == probe_value
        except Exception as exc:  # noqa: BLE001 - qualquer falha do cache e um diagnostico critico
            return DiagnosticCheck(
                "cache",
                STATUS_CRITICAL,
                "Falha ao executar sondagem funcional do cache.",
                {"error": type(exc).__name__},
            )
        finally:
            try:
                cache.delete(probe_key, namespace=_DIAGNOSTICS_CACHE_NAMESPACE)
            except Exception:  # noqa: BLE001 - limpeza da sondagem nao deve mascarar o resultado acima
                pass

        if not roundtrip_ok:
            return DiagnosticCheck(
                "cache",
                STATUS_CRITICAL,
                "Sondagem funcional do cache: valor lido nao corresponde ao valor gravado.",
                {"roundtrip_ok": False},
            )

        stats = cache.stats()
        return DiagnosticCheck(
            "cache",
            STATUS_OK,
            "Sondagem funcional do cache (gravar + ler) bem-sucedida.",
            {
                "roundtrip_ok": True,
                "backend": stats["backend"],
                "hit_rate": stats["hit_rate"],
                "size": stats["size"],
            },
        )

    def check_config(self) -> DiagnosticCheck:
        environment = detect_environment()
        problems = validate_settings(self.settings, environment)
        if not problems:
            return DiagnosticCheck(
                "config",
                STATUS_OK,
                f"Configuracao valida para o perfil '{environment.value}'.",
                {"environment": environment.value},
            )

        # production/testing: validate_or_raise() ja bloquearia a inicializacao
        # da app com esses problemas - aqui reportamos como critical porque,
        # em produção real, isso significa "a app nem deveria ter subido assim".
        # development/staging: validate_settings() so avisa, nao bloqueia -
        # entao aqui e warning, nao critical.
        status = STATUS_CRITICAL if environment.value in ("production", "testing") else STATUS_WARNING
        return DiagnosticCheck(
            "config",
            status,
            f"{len(problems)} problema(s) de configuracao encontrado(s) no perfil '{environment.value}'.",
            {"environment": environment.value, "problems": problems},
        )

    def check_disk(self) -> DiagnosticCheck:
        path = Path(self.settings.diagnostics_disk_path)
        try:
            usage = shutil.disk_usage(path)
        except OSError as exc:
            return DiagnosticCheck(
                "disk",
                STATUS_CRITICAL,
                f"Nao foi possivel consultar espaco em disco em '{path}'.",
                {"error": type(exc).__name__},
            )

        free_mb = usage.free / (1024 * 1024)
        total_mb = usage.total / (1024 * 1024)
        if free_mb < self.settings.diagnostics_disk_critical_free_mb:
            status = STATUS_CRITICAL
        elif free_mb < self.settings.diagnostics_disk_warning_free_mb:
            status = STATUS_WARNING
        else:
            status = STATUS_OK

        return DiagnosticCheck(
            "disk",
            status,
            f"{free_mb:.0f} MB livres de {total_mb:.0f} MB em '{path}'.",
            {"free_mb": round(free_mb, 1), "total_mb": round(total_mb, 1), "path": str(path)},
        )

    # -- agregacao ------------------------------------------------------------

    def _all_checks(self) -> dict[str, Any]:
        return {
            "database": self.check_database,
            "queue": self.check_queue,
            "cache": self.check_cache,
            "config": self.check_config,
            "disk": self.check_disk,
        }

    def run_check(self, name: str) -> DiagnosticCheck:
        checks = self._all_checks()
        if name not in checks:
            raise UnknownDiagnosticCheckError(
                f"Check de diagnostico desconhecido: '{name}'. Validos: {sorted(checks)}."
            )
        return checks[name]()

    def run_full_diagnostics(self) -> dict[str, Any]:
        results = [fn() for fn in self._all_checks().values()]
        summary = {
            STATUS_OK: sum(1 for c in results if c.status == STATUS_OK),
            STATUS_WARNING: sum(1 for c in results if c.status == STATUS_WARNING),
            STATUS_CRITICAL: sum(1 for c in results if c.status == STATUS_CRITICAL),
        }
        return {
            "status": _worst([c.status for c in results]),
            "generated_at": datetime.now(UTC),
            "summary": summary,
            "checks": [c.to_dict() for c in results],
        }
