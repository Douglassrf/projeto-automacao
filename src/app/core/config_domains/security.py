"""Domínio: CORS, rate limiting, autenticação e admin padrão."""

from pydantic import BaseModel


class SecurityConfig(BaseModel):
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
    auth_required: bool = True
    jwt_secret_key: str = "change-me-super-secret-local-key"
    access_token_expire_minutes: int = 60 * 24 * 7
    default_admin_name: str = "Douglas"
    default_admin_email: str = "admin@example.com"
    default_admin_password: str | None = None
