"""Application settings.

Everything environment-variable driven (prefix ``LEADSynt_``). Secrets are
never read from code or the frontend. See ``.env.example`` for the full
catalog and docs/deployment.md for the SQL Server profile.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LEADSynt_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Application ---------------------------------------------------------
    app_name: str = "LeadSynt"
    environment: Literal["dev", "staging", "production"] = "dev"
    debug: bool = True
    log_level: str = "INFO"
    log_json: bool = True
    secret_key: str = "change-me-to-a-long-random-secret-of-at-least-64-bytes-in-production"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    api_v1_prefix: str = "/api/v1"
    rate_limit_requests_per_minute: int = 300

    # -- Database ------------------------------------------------------------
    # Production target: mssql+pyodbc://...  (see .env.example)
    # Local dev default: SQLite (dev profile only, never production).
    database_url: str = "sqlite:///./leadsynt_dev.db"
    db_echo: bool = False
    db_pool_size: int = 10
    db_pool_recycle_seconds: int = 1800
    db_max_overflow: int = 20

    # -- Redis / queue ---------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    redis_db: int = 0
    celery_task_always_eager: bool = False
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # -- Authentication --------------------------------------------------------
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "leadsynt"
    jwt_access_token_ttl_minutes: int = 60
    jwt_refresh_token_ttl_days: int = 7
    allow_self_registration: bool = True
    default_registration_role: str = "viewer"
    seed_admin_email: str = "admin@leadsynt.io"
    seed_admin_password: str = "LeadSynt-Dev-Only-2026"
    bcrypt_rounds: int = 12

    # -- AI --------------------------------------------------------------------
    ai_provider: str = "none"
    ai_api_key: str = ""
    ai_model: str = ""
    ai_max_cost_per_run_usd: float = 0.05
    ai_max_tokens_per_run: int = 4000
    # 0.0 = unlimited per agent; applied as each agent's monthly_budget_usd.
    ai_default_monthly_budget_usd: float = 0.0
    ai_llm_timeout_seconds: int = 60

    # -- Email / SMS -------------------------------------------------------------
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_from: str = "notifications@leadsynt.local"
    sms_provider: str = "none"
    sms_api_key: str = ""

    # -- Outreach (Phase B) ----------------------------------------------------------
    # "log" (default) records outbound attempts to the log without claiming
    # external delivery; "smtp" performs real delivery via the SMTP settings.
    outreach_email_transport: str = "log"
    outreach_email_from: str = "outreach@leadsynt.local"
    outreach_sender_name: str = "LeadSynt"

    # -- Verification providers ---------------------------------------------------
    verification_email_provider: str = "none"
    verification_phone_provider: str = "none"

    # -- Storage --------------------------------------------------------------------
    storage_backend: str = "local"
    storage_local_path: str = "./storage"

    # -- Webhooks --------------------------------------------------------------------
    webhook_shared_secret: str = "change-me-webhook-secret"
    webhook_signature_tolerance_seconds: int = 300

    # -- Notifications ----------------------------------------------------------------
    notifications_in_app: bool = True
    notifications_email: bool = False
    notifications_sms: bool = False

    # -- Monitoring / QA --------------------------------------------------------------
    metrics_enabled: bool = True
    qa_stale_ticket_hours: int = 72

    # ------------------------------------------------------------------ helpers
    @field_validator("cors_origins")
    @classmethod
    def _strip_cors(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def db_dialect(self) -> str:
        return self.database_url.split("://", 1)[0]


@lru_cache
def get_settings() -> Settings:
    return Settings()
