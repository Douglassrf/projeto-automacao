from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.services.cache_service import CacheService
from app.services.diagnostics_service import STATUS_CRITICAL, STATUS_OK, STATUS_WARNING, DiagnosticsService
from app.services.resource_manager_service import ResourceManagerService

UTC = timezone.utc

_HISTORY_NAMESPACE = "__predictive_health__"
_HISTORY_KEY = "metric_snapshots"

TREND_STABLE = "stable"
TREND_DEGRADING = "degrading"
TREND_IMPROVING = "improving"


def _memory_used_percent() -> float | None:
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
            return float(stat.dwMemoryLoad)
    except Exception:  # noqa: BLE001
        pass

    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            lines = {line.split(":")[0]: line.split(":")[1].strip() for line in handle if ":" in line}
        total = int(lines.get("MemTotal", "0 kB").split()[0])
        available = int(lines.get("MemAvailable", lines.get("MemFree", "0 kB")).split()[0])
        if total > 0:
            return round(((total - available) / total) * 100, 1)
    except Exception:  # noqa: BLE001
        pass
    return None


def _cpu_load_percent() -> float | None:
    try:
        load_avg = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        return round(min(100.0, (load_avg / cpu_count) * 100), 1)
    except (AttributeError, OSError):
        pass
    return None


def _compute_trend(values: list[float]) -> str:
    if len(values) < 2:
        return TREND_STABLE
    delta = values[-1] - values[0]
    if delta > 5.0:
        return TREND_DEGRADING
    if delta < -5.0:
        return TREND_IMPROVING
    return TREND_STABLE


class PredictiveHealthService:
    """Missao 72 - Predictive Health Monitor.

    Monitora tendencias de CPU, memoria e armazenamento usando amostras
    atuais (DiagnosticsService + ResourceManagerService + metricas de SO)
    e um historico curto persistido via CacheService (namespace dedicado).

    Gera alertas preditivos quando a tendencia indica degradacao gradual e
    produz relatorio consolidado de degradacao. Estritamente de LEITURA
    para servicos externos; apenas appenda snapshots ao historico em cache.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.diagnostics = DiagnosticsService(db)
        self.resources = ResourceManagerService(db)
        self.cache = CacheService(db)

    def _sample_current_metrics(self) -> dict[str, Any]:
        disk_check = self.diagnostics.check_disk()
        disk_details = disk_check.details
        free_mb = float(disk_details.get("free_mb", 0.0))
        total_mb = float(disk_details.get("total_mb", 1.0))
        storage_used_pct = round(((total_mb - free_mb) / total_mb) * 100, 1) if total_mb else 0.0

        resource_usage = self.resources.disk_usage_report()
        managed_storage_mb = float(resource_usage["total_size_mb"])

        memory_pct = _memory_used_percent()
        cpu_pct = _cpu_load_percent()

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "cpu_load_percent": cpu_pct,
            "memory_used_percent": memory_pct,
            "storage_used_percent": storage_used_pct,
            "disk_free_mb": free_mb,
            "managed_storage_mb": managed_storage_mb,
            "disk_status": disk_check.status,
        }

    def _load_history(self) -> list[dict[str, Any]]:
        raw = self.cache.get(_HISTORY_KEY, namespace=_HISTORY_NAMESPACE)
        if isinstance(raw, list):
            return raw
        return []

    def _save_history(self, history: list[dict[str, Any]]) -> None:
        max_snapshots = self.settings.predictive_health_history_max_snapshots
        trimmed = history[-max_snapshots:]
        self.cache.set(
            _HISTORY_KEY,
            trimmed,
            namespace=_HISTORY_NAMESPACE,
            ttl_seconds=max_snapshots * 3600,
        )

    def _append_snapshot(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        history = self._load_history()
        history.append(snapshot)
        self._save_history(history)
        return history

    def _metric_series(
        self, history: list[dict[str, Any]], key: str
    ) -> list[float]:
        series: list[float] = []
        for item in history:
            value = item.get(key)
            if isinstance(value, (int, float)):
                series.append(float(value))
        return series

    def _predictive_alerts(
        self,
        *,
        trends: dict[str, str],
        current: dict[str, Any],
    ) -> list[str]:
        if not self.settings.predictive_health_enable_predictive_alerts:
            return []

        alerts: list[str] = []
        if trends.get("cpu") == TREND_DEGRADING:
            alerts.append("Tendencia de CPU em degradacao gradual detectada no historico recente.")
        if trends.get("memory") == TREND_DEGRADING:
            alerts.append("Tendencia de memoria em degradacao gradual detectada no historico recente.")
        if trends.get("storage") == TREND_DEGRADING:
            alerts.append("Tendencia de armazenamento em degradacao gradual detectada no historico recente.")
        if current.get("disk_status") == STATUS_WARNING:
            alerts.append("Disco em faixa de aviso — risco de esgotamento se a tendencia continuar.")
        if current.get("disk_status") == STATUS_CRITICAL:
            alerts.append("Disco em faixa critica — acao imediata recomendada.")
        return alerts

    def _degradation_report(
        self,
        *,
        trends: dict[str, str],
        history: list[dict[str, Any]],
        predictive_alerts: list[str],
    ) -> dict[str, Any]:
        gradual_areas: list[str] = []
        for metric, trend in trends.items():
            if trend == TREND_DEGRADING:
                gradual_areas.append(metric)

        overall = STATUS_OK
        if any(t == TREND_DEGRADING for t in trends.values()):
            overall = STATUS_WARNING
        if predictive_alerts and any("critica" in a for a in predictive_alerts):
            overall = STATUS_CRITICAL

        return {
            "overall_status": overall,
            "snapshot_count": len(history),
            "gradual_degradation_areas": gradual_areas,
            "trends": trends,
            "predictive_alert_count": len(predictive_alerts),
        }

    def monitor_report(self) -> dict[str, Any]:
        """Consolida monitoramento preditivo com tendencias e alertas."""

        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)

        current = self._sample_current_metrics()
        history = self._append_snapshot(current)

        cpu_series = self._metric_series(history, "cpu_load_percent")
        memory_series = self._metric_series(history, "memory_used_percent")
        storage_series = self._metric_series(history, "storage_used_percent")

        trends = {
            "cpu": _compute_trend(cpu_series) if cpu_series else TREND_STABLE,
            "memory": _compute_trend(memory_series) if memory_series else TREND_STABLE,
            "storage": _compute_trend(storage_series) if storage_series else TREND_STABLE,
        }

        predictive_alerts = self._predictive_alerts(trends=trends, current=current)
        degradation = self._degradation_report(
            trends=trends,
            history=history,
            predictive_alerts=predictive_alerts,
        )

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "predictive_alerts_enabled": self.settings.predictive_health_enable_predictive_alerts,
            "current_metrics": current,
            "trends": trends,
            "metric_history": history,
            "predictive_alerts": predictive_alerts,
            "degradation_report": degradation,
            "config_validation_issues": config_validation_issues,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.monitor_report()
        current = report["current_metrics"]
        trends = report["trends"]
        degradation = report["degradation_report"]

        lines: list[str] = []
        lines.append("# Predictive Health Monitor")
        lines.append("")
        lines.append(f"- Gerado em: {report['generated_at']}")
        lines.append(f"- Ambiente: {report['environment']}")
        lines.append(f"- CONFIG_SCHEMA_VERSION: {report['config_schema_version']}")
        lines.append(f"- Alertas preditivos: {'ativos' if report['predictive_alerts_enabled'] else 'desativados'}")
        lines.append(f"- Status geral: **{degradation['overall_status']}**")
        lines.append("")

        lines.append("## Metricas atuais")
        lines.append("")
        lines.append(f"- CPU: {current.get('cpu_load_percent', 'N/A')}%")
        lines.append(f"- Memoria: {current.get('memory_used_percent', 'N/A')}%")
        lines.append(f"- Armazenamento usado: {current.get('storage_used_percent')}%")
        lines.append(f"- Disco livre: {current.get('disk_free_mb')} MB")
        lines.append(f"- Storage gerenciado: {current.get('managed_storage_mb')} MB")
        lines.append("")

        lines.append("## Tendencias")
        lines.append("")
        for metric, trend in trends.items():
            lines.append(f"- {metric}: {trend}")
        lines.append("")

        lines.append("## Alertas preditivos")
        lines.append("")
        if report["predictive_alerts"]:
            for alert in report["predictive_alerts"]:
                lines.append(f"- {alert}")
        else:
            lines.append("- Nenhum alerta preditivo no momento.")
        lines.append("")

        lines.append("## Degradacao gradual")
        lines.append("")
        if degradation["gradual_degradation_areas"]:
            for area in degradation["gradual_degradation_areas"]:
                lines.append(f"- Area em degradacao: {area}")
        else:
            lines.append("- Nenhuma degradacao gradual detectada.")
        lines.append("")

        return "\n".join(lines)
