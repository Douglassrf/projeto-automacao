"""Missao 52 - Dependency Injection Framework.

Antes desta missao, toda rota que precisava de um service fazia a propria
instanciacao inline, repetida em cada handler:

    @router.get("/jobs")
    def list_jobs(db: Session = Depends(get_db)):
        return QueueService(db).list_jobs(...)

Isso funciona, mas tem dois problemas: (1) o construtor de QueueService fica
espalhado por N handlers - mudar a assinatura do __init__ exige caca a todos
os lugares; (2) nao ha um jeito padrao de substituir QueueService por um
fake/stub em teste sem mockar o modulo inteiro.

Este modulo nao substitui FastAPI.Depends - FastAPI ja e o framework de DI da
aplicacao (e um bom framework, por isso). O que faltava era uma fabrica
generica e um registro central de "como construir cada service", para que
novas rotas (e rotas existentes, por adesao incremental) parem de repetir
"NomeDoService(db)" e passem a declarar a dependencia uma unica vez, no
mesmo espirito de `db: Session = Depends(get_db)`:

    @router.get("/jobs")
    def list_jobs(queue: QueueService = Depends(get_queue_service)):
        return queue.list_jobs(...)

Em teste, isso e trivialmente substituivel:

    app.dependency_overrides[get_queue_service] = lambda: FakeQueueService()

Criterio de sucesso (Missao 52): existe uma fabrica generica reutilizavel
(`provide`) - novos services com `__init__(self, db: Session)` ganham um
provider funcional em uma linha, sem reescrever o boilerplate de
`def _provider(db: Session = Depends(get_db)): return Servico(db)` a cada
vez. Adesao e incremental: rotas existentes nao migradas continuam
funcionando exatamente como antes (nao e uma mudanca de contrato).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.alert_service import AlertService
from app.services.cache_service import CacheService
from app.services.certification_service import CertificationService
from app.services.diagnostics_service import DiagnosticsService
from app.services.queue_service import QueueService
from app.services.recovery_service import RecoveryService
from app.services.resource_manager_service import ResourceManagerService
from app.services.architecture_audit_service import ArchitectureAuditService
from app.services.code_review_service import CodeReviewService
from app.services.unified_certification_service import UnifiedCertificationEngine
from app.services.evolution_dashboard_service import EvolutionDashboardService
from app.services.tech_debt_manager_service import TechDebtManagerService
from app.services.architecture_stress_test_service import ArchitectureStressTestService
from app.services.enterprise_readiness_service import EnterpriseReadinessService
from app.services.engineering_memory_core_service import EngineeringMemoryCoreService
from app.services.architecture_evolution_timeline_service import ArchitectureEvolutionTimelineService
from app.services.enterprise_quality_observatory_service import EnterpriseQualityObservatoryService
from app.services.predictive_maintenance_service import PredictiveMaintenanceService
from app.services.intelligent_release_governance_service import (
    IntelligentReleaseGovernanceService,
)
from app.services.architecture_scoring_service import ContinuousArchitectureScoringService
from app.services.optimization_planner_service import AutonomousOptimizationPlannerService
from app.services.digital_twin_service import EngineeringDigitalTwinService

ServiceT = TypeVar("ServiceT")

# Registro central: nome -> provider gerado. Usado por diagnostico/auditoria
# de arquitetura (ex.: Missao 55) para enumerar quais services jah adotaram
# o container, sem precisar grep no codigo.
_PROVIDER_REGISTRY: dict[str, Callable[..., object]] = {}


def provide(service_cls: type[ServiceT], *, name: str | None = None) -> Callable[[Session], ServiceT]:
    """Fabrica generica de dependencia FastAPI para services com a forma
    `__init__(self, db: Session)` (o construtor mais comum no projeto -
    QueueService, CacheService, DiagnosticsService, AlertService,
    RecoveryService, ResourceManagerService, CertificationService).

    Devolve um callable usavel diretamente como `Depends(provider)`. O
    proprio `db` continua vindo de `Depends(get_db)` por baixo - este
    container nao reimplementa sessao de banco, soh evita repetir
    `Servico(db)` em cada handler.
    """
    provider_name = name or service_cls.__name__

    def _provider(db: Session = Depends(get_db)) -> ServiceT:
        return service_cls(db)

    _provider.__name__ = f"provide_{provider_name}"
    _provider.__qualname__ = _provider.__name__
    _PROVIDER_REGISTRY[provider_name] = _provider
    return _provider


def settings_dependency() -> Settings:
    """Wrapper de `get_settings()` como dependencia FastAPI.

    Services que hoje chamam `get_settings()` direto continuam funcionando
    (nao e obrigatorio migrar) - mas rotas que precisam de `Settings` podem
    declarar `settings: Settings = Depends(settings_dependency)` e, em
    teste, substituir via
    `app.dependency_overrides[settings_dependency] = lambda: fake_settings`
    sem precisar de `monkeypatch` no modulo `app.core.config`.
    """
    return get_settings()


def registered_providers() -> list[str]:
    """Nomes (ordenados) de todos os services que tem provider registrado
    via `provide()`. Util para diagnostico/auditoria - responde "quais
    services jah adotaram o container de DI" sem grep manual."""
    return sorted(_PROVIDER_REGISTRY)


# Providers prontos para os services mais usados pelas rotas (Missoes
# 42, 43, 44, 45, 46, 47, 50). Adesao por rota e incremental - ver
# `api/routes/queue.py` e `api/routes/cache.py` para o primeiro uso real.
get_queue_service = provide(QueueService)
get_cache_service = provide(CacheService)
get_diagnostics_service = provide(DiagnosticsService)
get_alert_service = provide(AlertService)
get_recovery_service = provide(RecoveryService)
get_resource_manager_service = provide(ResourceManagerService)
get_certification_service = provide(CertificationService)
get_unified_certification_engine = provide(UnifiedCertificationEngine)  # Missao 53
get_evolution_dashboard_service = provide(EvolutionDashboardService)  # Missao 57


def get_architecture_audit_service() -> ArchitectureAuditService:
    """Missao 55. Nao usa `provide()` pelo mesmo motivo de
    `settings_dependency()`: ArchitectureAuditService nao depende de `db`
    (todos os quatro eixos que audita leem codigo-fonte em disco ou estado
    vivo de modulo ja importado, nunca o banco) - forcar um `db: Session`
    aqui so para caber na fabrica generica seria decorativo."""
    return ArchitectureAuditService()


def get_code_review_service() -> CodeReviewService:
    """Missao 56. Mesmo motivo de `get_architecture_audit_service()`
    (Missao 55): CodeReviewService nao depende de `db` - os eixos de
    revisao leem arquivos `.py` do proprio repositorio via AST, nunca o
    banco. `provide()` forcaria um `db: Session` decorativo."""
    return CodeReviewService()


def get_tech_debt_manager_service() -> TechDebtManagerService:
    """Missao 58. Mesmo motivo de `get_architecture_audit_service()`
    (Missao 55) e `get_code_review_service()` (Missao 56):
    TechDebtManagerService nao depende de `db` - so de CodeReviewService
    (arquivo via AST) e do `git` (historico). `provide()` forcaria um
    `db: Session` decorativo."""
    return TechDebtManagerService()


def get_architecture_stress_test_service() -> ArchitectureStressTestService:
    """Missao 59. Mesmo motivo de `get_architecture_audit_service()`
    (Missao 55), `get_code_review_service()` (Missao 56) e
    `get_tech_debt_manager_service()` (Missao 58): ArchitectureStressTestService
    nao depende de `db` - dispara requisicoes in-process via `TestClient`
    contra os proprios endpoints da aplicacao e chama o container
    diretamente. `provide()` forcaria um `db: Session` decorativo."""
    return ArchitectureStressTestService()


get_enterprise_readiness_service = provide(EnterpriseReadinessService)  # Missao 60
get_engineering_memory_core_service = provide(EngineeringMemoryCoreService)  # Missao 122
get_architecture_evolution_timeline_service = provide(ArchitectureEvolutionTimelineService)  # Missao 123
get_enterprise_quality_observatory_service = provide(EnterpriseQualityObservatoryService)  # Missao 124
get_predictive_maintenance_service = provide(PredictiveMaintenanceService)  # Missao 125
get_intelligent_release_governance_service = provide(IntelligentReleaseGovernanceService)  # Missao 126


def get_architecture_scoring_service() -> ContinuousArchitectureScoringService:
    """Missao 127. Mesmo motivo de `get_architecture_audit_service()`
    (Missao 55), `get_code_review_service()` (Missao 56) e
    `get_tech_debt_manager_service()` (Missao 58): ContinuousArchitectureScoringService
    nao depende de `db` - os cinco eixos leem ArchitectureAuditService,
    CodeReviewService e TechDebtManagerService (todos tambem sem banco).
    `provide()` forcaria um `db: Session` decorativo, e pior: a fabrica
    generica passaria `db` como primeiro argumento posicional do
    construtor, que aqui e `architecture_audit` (nao `db`) - usar
    `provide()` quebraria a injecao de dependencia silenciosamente."""
    return ContinuousArchitectureScoringService()


def get_optimization_planner_service() -> AutonomousOptimizationPlannerService:
    """Missao 128. Mesmo motivo das funcoes dedicadas acima (Missoes 55,
    56, 58, 59, 127): AutonomousOptimizationPlannerService nao depende de
    `db` - so de TechDebtManagerService e ContinuousArchitectureScoringService,
    ambos tambem sem banco. `provide()` passaria `db` como primeiro
    argumento posicional do construtor (aqui `tech_debt_manager`),
    quebrando a injecao de dependencia silenciosamente."""
    return AutonomousOptimizationPlannerService()


def get_digital_twin_service() -> EngineeringDigitalTwinService:
    """Missao 129. Mesmo motivo das funcoes dedicadas acima (Missoes 55,
    56, 58, 59, 127, 128): EngineeringDigitalTwinService nao depende de
    `db` - so de ContinuousArchitectureScoringService (Missao 127),
    tambem sem banco. `provide()` passaria `db` como primeiro argumento
    posicional do construtor (aqui `architecture_scoring`), quebrando a
    injecao de dependencia silenciosamente."""
    return EngineeringDigitalTwinService()
