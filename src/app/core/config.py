from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AdIntelligence Pro"
    database_url: str = "sqlite:///./adintelligence.db"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    cors_allow_credentials: bool = True
    rate_limit_enabled: bool = True
    rate_limit_login_limit: int = 5
    rate_limit_login_window_seconds: int = 15 * 60
    rate_limit_sensitive_limit: int = 10
    rate_limit_sensitive_window_seconds: int = 60 * 60
    rate_limit_ai_heavy_limit: int = 20
    rate_limit_ai_heavy_window_seconds: int = 24 * 60 * 60
    rate_limit_meta_api_limit: int = 60
    rate_limit_meta_api_window_seconds: int = 60 * 60
    rate_limit_default_limit: int = 120
    rate_limit_default_window_seconds: int = 60 * 60
    affiliate_network: str = "generic"
    affiliate_api_key: str | None = None
    affiliate_api_secret: str | None = None
    affiliate_default_id: str | None = "demo-affiliate"
    affiliate_mock_enabled: bool = True
    upload_max_bytes: int = 5 * 1024 * 1024
    upload_dir: str = "/data/uploads"
    auth_required: bool = True
    jwt_secret_key: str = "change-me-super-secret-local-key"
    access_token_expire_minutes: int = 60 * 24 * 7
    default_admin_name: str = "Douglas"
    default_admin_email: str = "admin@example.com"
    default_admin_password: str | None = None
    meta_access_token: str | None = None
    meta_ad_account_id: str | None = None
    meta_page_id: str | None = None
    meta_instagram_actor_id: str | None = None
    meta_pixel_id: str | None = None
    capi_pixel_id: str | None = None
    meta_api_version: str = "v20.0"
    meta_env: str = "sandbox"
    meta_dry_run: bool = True
    meta_allow_active_launch: bool = False
    meta_operator_enabled: bool = True
    meta_autopublish: bool = False
    meta_allow_production_real: bool = False
    meta_production_daily_spend_limit_brl: float = 50.0
    meta_require_manual_confirmation: bool = True
    currency_code: str = "BRL"
    currency_ad_account: str = "BRL"
    currency_sales: str = "EUR"
    exchange_rate_usd_to_brl: float = 5.0
    exchange_rate_eur_to_brl: float = 5.5
    test_budget_brl: float = 25.0
    scale_budget_brl: float = 50.0
    scale_min_ctr: float = 1.5
    scale_min_roas: float = 1.0
    meta_created_resources_log: str = "/data/runtime/meta_created_resources.jsonl"
    kit_output_dir: str = "/data/campaign_kits"
    ai_provider: str = "local_template"
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    storage_provider: str = "local"
    s3_bucket: str | None = None
    drive_folder_id: str | None = None
    capi_enabled: bool = False
    capi_test_event_code: str | None = None
    learning_loop_enabled: bool = True
    automation_level: int = 0
    automation_level_2_enabled: bool = False
    automation_daily_spend_limit_brl: float = 50.0
    kill_switch_enabled: bool = False
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model: str = "eleven_multilingual_v2"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"
    video_provider: str = "ffmpeg_local"
    war_kit_execute_video_render: bool = False
    huggingface_token: str | None = None
    huggingface_video_space: str | None = None
    site_output_dir: str = "/data/generated_sites"
    github_token: str | None = None
    github_owner: str | None = None
    vercel_token: str | None = None
    vercel_team_id: str | None = None
    netlify_token: str | None = None
    orchestration_output_dir: str = "/data/orchestration_runs"
    n8n_base_url: str | None = None
    n8n_webhook_secret: str | None = None
    google_gemini_api_key: str | None = None
    google_cloud_run_project: str | None = None
    aws_lambda_region: str | None = None
    colab_notebook_url: str | None = None
    comfyui_endpoint: str | None = None

    queue_backend: str = "sqlite"
    queue_sqlite_wal_enabled: bool = True
    queue_default_max_attempts: int = 3
    queue_lock_timeout_seconds: int = 900
    keydb_url: str | None = None


    ugc_output_dir: str = "/data/ugc"
    ugc_max_bytes: int = 50 * 1024 * 1024
    ugc_image_target_width: int = 1080
    ugc_video_target_width: int = 720
    ugc_video_crf: int = 28

    serverless_render_enabled: bool = True
    serverless_render_provider: str = "dry_run"
    serverless_render_max_cost_usd: float = 0.0
    aws_lambda_render_function_name: str | None = None
    google_cloud_function_render_url: str | None = None
    render_callback_url: str | None = None


    # Enterprise workers / observability / premium render
    celery_enabled: bool = False
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    render_worker_queue: str = "render-premium"
    sentry_dsn: str | None = None
    observability_enabled: bool = True
    premium_render_output_dir: str = "/data/premium_renders"
    premium_render_dry_run: bool = True
    premium_render_provider_image: str = "local_ffmpeg"
    premium_render_provider_video: str = "local_ffmpeg"
    premium_render_upscale_enabled: bool = True
    premium_render_color_lut: str = "warm_contrast"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def safe_project_path(configured_dir: str, fallback_relative: str) -> Path:
    configured = Path(configured_dir).resolve()
    try:
        configured.mkdir(parents=True, exist_ok=True)
        probe = configured / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return configured
    except OSError:
        fallback = project_root() / fallback_relative
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
