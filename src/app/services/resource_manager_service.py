from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings, safe_project_path
from app.domain.models import QueueJob
from app.services.cache_service import CacheService
from app.services.queue_service import TERMINAL_STATUSES

# (rótulo, settings_field, fallback_relative) - mesma resolução de diretório
# já usada pelos serviços que efetivamente escrevem nesses caminhos
# (video_pipeline.py, learning_loop.py, serverless_render.py, hybrid_stack.py,
# zero_cost_stack.py, war_kit_generator.py, premium_render.py,
# ugc_processing.py). Mantido aqui como uma lista explícita (não descoberta
# automática de diretórios) para que o que é "gerenciado" seja sempre visível
# e auditável neste único arquivo.
_MANAGED_DIRS: tuple[tuple[str, str, str], ...] = (
    ("campaign_kits", "kit_output_dir", "data/campaign_kits"),
    ("orchestration_runs", "orchestration_output_dir", "data/orchestration_runs"),
    ("ugc", "ugc_output_dir", "data/ugc"),
    ("premium_renders", "premium_render_output_dir", "data/campaign_kits/PremiumRender"),
)


def _dir_stats(path: Path) -> tuple[float, int]:
    """Retorna (tamanho_mb, contagem_de_arquivos). Caminho ausente -> (0.0, 0)
    em vez de levantar - varios desses diretorios so existem depois do
    primeiro uso do pipeline correspondente."""

    if not path.exists():
        return 0.0, 0
    total_bytes = 0
    file_count = 0
    for root, _dirs, files in os.walk(path):
        for filename in files:
            try:
                total_bytes += (Path(root) / filename).stat().st_size
                file_count += 1
            except OSError:
                continue
    return round(total_bytes / (1024 * 1024), 2), file_count


class ResourceManagerService:
    """Missao 45 - Gerenciamento de Recursos.

    Contraparte de acao da Missao 44 (Diagnostico Automatico, que e somente
    leitura): aqui o servico de fato libera recursos - apaga jobs de fila
    terminais (done/dead) antigos e entradas de cache expiradas, e reporta
    uso de disco dos diretorios de saida que o proprio projeto gerencia.

    Escopo deliberadamente restrito a dados que o próprio aplicativo
    escreve (jobs na tabela queue_jobs, entradas em cache_entries, arquivos
    dentro dos diretórios de saída configurados) - nunca arquivos do
    usuário fora desses diretórios, e nunca jobs em estado não-terminal
    (queued/running/retry)."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def disk_usage_report(self) -> dict[str, Any]:
        directories: dict[str, dict[str, Any]] = {}
        total_mb = 0.0
        for label, field_name, fallback_relative in _MANAGED_DIRS:
            configured_dir = getattr(self.settings, field_name)
            resolved = safe_project_path(configured_dir, fallback_relative)
            size_mb, file_count = _dir_stats(resolved)
            directories[label] = {
                "path": str(resolved),
                "size_mb": size_mb,
                "file_count": file_count,
            }
            total_mb += size_mb
        return {"total_size_mb": round(total_mb, 2), "directories": directories}

    def purge_old_queue_jobs(self, max_age_days: int | None = None) -> dict[str, Any]:
        """Remove jobs com status terminal (done/dead) cujo updated_at seja
        mais antigo que max_age_days (default: resource_job_retention_days).
        Jobs queued/running/retry nunca sao tocados, independente da idade -
        sao trabalho ativo, nao lixo a ser limpo."""

        age_days = max_age_days if max_age_days is not None else self.settings.resource_job_retention_days
        cutoff = datetime.now(UTC) - timedelta(days=age_days)

        query = self.db.query(QueueJob).filter(
            QueueJob.status.in_(TERMINAL_STATUSES), QueueJob.updated_at < cutoff
        )
        deleted = query.delete(synchronize_session=False)
        self.db.commit()
        return {"deleted": deleted, "cutoff": cutoff.isoformat(), "max_age_days": age_days}

    def purge_expired_cache(self) -> int:
        """Delega para CacheService.purge_expired() (Missao 43) - reaproveita
        a limpeza de cache ja existente em vez de duplicar a logica aqui."""
        return CacheService(self.db).purge_expired()

    def run_cleanup(self, max_age_days: int | None = None) -> dict[str, Any]:
        """Varredura combinada: jobs de fila terminais antigos + entradas de
        cache expiradas. Um unico ponto de entrada para "liberar recursos"."""
        queue_result = self.purge_old_queue_jobs(max_age_days=max_age_days)
        cache_purged = self.purge_expired_cache()
        return {
            "queue_jobs_deleted": queue_result["deleted"],
            "queue_cutoff": queue_result["cutoff"],
            "cache_entries_purged": cache_purged,
        }
