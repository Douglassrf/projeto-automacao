from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.domain.models import User, AdAnalysis, DecisionLog, QueueJob, ContentWorkflow, Campaign, CampaignMetric, AdLibraryBenchmark, PerformanceTicket, MetaActionRequest, FinancialMetric, ScalingRule, ManualRevenueEntry, CacheEntry, CacheStat  # noqa: F401


def _ensure_sqlite_wal() -> None:
    settings = get_settings()
    if engine.dialect.name != "sqlite" or not settings.queue_sqlite_wal_enabled:
        return
    with engine.begin() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL"))
        connection.execute(text("PRAGMA busy_timeout=5000"))


def _ensure_sqlite_columns() -> None:
    """Small local-dev migration helper for SQLite projects without Alembic yet."""
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "ad_analyses" in tables:
        existing = {column["name"] for column in inspector.get_columns("ad_analyses")}
        required = {
            "preview_url": "VARCHAR(255) DEFAULT ''",
            "edited_link": "VARCHAR(255) DEFAULT ''",
        }
        with engine.begin() as connection:
            for column_name, ddl in required.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE ad_analyses ADD COLUMN {column_name} {ddl}"))

    if "users" in tables:
        existing = {column["name"] for column in inspector.get_columns("users")}
        required = {
            "hashed_password": "VARCHAR(255) DEFAULT ''",
            "is_active": "BOOLEAN DEFAULT 1",
        }
        with engine.begin() as connection:
            for column_name, ddl in required.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {ddl}"))


    if "campaigns" in tables:
        existing = {column["name"] for column in inspector.get_columns("campaigns")}
        required = {
            "meta_adset_id": "VARCHAR(160) DEFAULT ''",
            "desired_status": "VARCHAR(40) DEFAULT 'ACTIVE'",
            "real_status": "VARCHAR(40) DEFAULT 'UNKNOWN'",
            "last_state_sync_reason": "TEXT DEFAULT ''",
            "desired_budget": "FLOAT DEFAULT 0",
            "real_budget": "FLOAT DEFAULT 0",
            "budget_drift_detected": "BOOLEAN DEFAULT 0",
            "currency_code": "VARCHAR(8) DEFAULT 'BRL'",
            "currency_ad_account": "VARCHAR(8) DEFAULT 'BRL'",
            "currency_sales": "VARCHAR(8) DEFAULT 'EUR'",
        }
        with engine.begin() as connection:
            for column_name, ddl in required.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE campaigns ADD COLUMN {column_name} {ddl}"))


    if "campaign_metrics" in tables:
        existing = {column["name"] for column in inspector.get_columns("campaign_metrics")}
        required = {
            "revenue_amount": "FLOAT DEFAULT 0",
            "revenue_currency": "VARCHAR(8) DEFAULT 'EUR'",
            "exchange_rate_to_brl": "FLOAT DEFAULT 0",
            "revenue_brl": "FLOAT DEFAULT 0",
            "unified_roas_brl": "FLOAT DEFAULT 0",
        }
        with engine.begin() as connection:
            for column_name, ddl in required.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE campaign_metrics ADD COLUMN {column_name} {ddl}"))


    if "decision_logs" in tables:
        existing = {column["name"] for column in inspector.get_columns("decision_logs")}
        required = {
            "metadata_json": "TEXT DEFAULT '{}'",
        }
        with engine.begin() as connection:
            for column_name, ddl in required.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE decision_logs ADD COLUMN {column_name} {ddl}"))

    if "queue_jobs" in tables:
        # Missao 42 - Gerenciador Inteligente de Filas: backoff exponencial.
        existing = {column["name"] for column in inspector.get_columns("queue_jobs")}
        required = {
            "next_attempt_at": "DATETIME DEFAULT NULL",
        }
        with engine.begin() as connection:
            for column_name, ddl in required.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE queue_jobs ADD COLUMN {column_name} {ddl}"))

    # Missao 43 - Cache Inteligente: cache_entries/cache_stats sao tabelas
    # novas (criadas por Base.metadata.create_all() acima) - nao ha coluna
    # legada para migrar ainda. Mantido como marcador para futuras colunas.


def _ensure_default_admin() -> None:
    settings = get_settings()
    if not settings.default_admin_password:
        raise RuntimeError(
            "DEFAULT_ADMIN_PASSWORD nao configurado. Defina essa variavel no "
            "seu arquivo .env local (veja .env.example) antes de iniciar a "
            "aplicacao. Por seguranca, nao existe mais um valor padrao "
            "hardcoded no codigo-fonte."
        )
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == settings.default_admin_email.lower()).first()
        if user:
            if not user.hashed_password:
                user.hashed_password = hash_password(settings.default_admin_password)
                db.commit()
            return

        db.add(User(
            name=settings.default_admin_name,
            email=settings.default_admin_email.lower(),
            access_level="PERSONAL",
            hashed_password=hash_password(settings.default_admin_password),
            is_active=True,
        ))
        db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_wal()
    _ensure_sqlite_columns()
    _ensure_default_admin()
