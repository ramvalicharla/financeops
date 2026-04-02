from __future__ import annotations

import base64 as _base64
import os
from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


class Settings(BaseSettings):
    # App
    APP_NAME: str = "FinanceOps"
    APP_ENV: str = "development"  # development / staging / production
    APP_ENVIRONMENT: str = "development"
    CORS_ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],
        description="Comma-separated allowed origins. Set via CORS_ALLOWED_ORIGINS env var.",
    )
    APP_RELEASE: str = "1.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "dev-secret-key-change-me-before-production-use-123456"

    # Database
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    )
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")

    # JWT
    JWT_SECRET: str = "dev-jwt-secret-change-me-before-production-use-123456"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI Providers
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    AI_DEFAULT_MONTHLY_TOKEN_LIMIT: int = 1000000
    AI_DEFAULT_MONTHLY_COST_LIMIT_USD: str = "50.00"
    OPEN_EXCHANGE_RATES_API_KEY: str = ""
    EXCHANGE_RATE_API_KEY: str = ""

    # Storage (Cloudflare R2)
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""

    # Telemetry
    SENTRY_DSN: str = ""
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""

    # Temporal
    TEMPORAL_ADDRESS: str = "temporal:7233"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "financeops-default"
    TEMPORAL_WORKER_IN_PROCESS: bool = False

    # Payments
    STRIPE_SECRET_KEY: str = ""
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Scheduled delivery transport
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_REQUIRED: bool = False

    # Auth rate limiting
    AUTH_LOGIN_RATE_LIMIT: str = "5/minute"
    AUTH_TOKEN_RATE_LIMIT: str = "5/minute"
    AUTH_MFA_RATE_LIMIT: str = "3/minute"
    AI_STREAM_RATE_LIMIT: str = "20/minute"
    ERP_SYNC_WRITE_RATE_LIMIT: str = "15/minute"
    UPLOAD_RATE_LIMIT: str = "10/minute"
    CURRENT_TERMS_VERSION: str = "2026-03-01"

    # Encryption
    FIELD_ENCRYPTION_KEY: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    STARTUP_FAIL_FAST: bool = False

    # Platform
    PLATFORM_TIMEZONE: str = "UTC"
    MAX_UPLOAD_SIZE_MB: int = 50
    CLAMAV_SOCKET: str = "/var/run/clamav/clamd.ctl"
    CLAMAV_HOST: str = "localhost"
    CLAMAV_PORT: int = 3310
    CLAMAV_REQUIRED: bool = False

    # ERP placeholder feature gates
    ERP_CONSENT_ENABLED: bool = False
    ERP_CONNECTOR_VERSIONING_ENABLED: bool = False
    ERP_CONNECTION_SERVICE_ENABLED: bool = False

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}

    @field_validator("FIELD_ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if not v:
            raise ValueError("FIELD_ENCRYPTION_KEY is required and cannot be empty")
        try:
            decoded = _base64.urlsafe_b64decode(v + "==")
        except Exception as exc:
            raise ValueError(
                "FIELD_ENCRYPTION_KEY must be valid URL-safe base64. "
                "Generate with: python -c \"import secrets, base64; "
                "import sys; "
                "sys.stdout.write(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())\""
                ) from exc
        if len(decoded) != 32:
            raise ValueError(
                f"FIELD_ENCRYPTION_KEY must decode to exactly 32 bytes "
                f"(AES-256). Got {len(decoded)} bytes. "
                f"Regenerate using the command above."
            )
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters. "
                "Generate with: python -c \"import secrets; "
                "import sys; "
                "sys.stdout.write(secrets.token_hex(32))\""
            )
        return v

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, v: object) -> list[str]:
        if v is None:
            return ["http://localhost:3000"]
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            parsed = [str(origin).strip() for origin in v if str(origin).strip()]
            return parsed or ["http://localhost:3000"]
        raise ValueError("CORS_ALLOWED_ORIGINS must be a comma-separated string or list")

    @model_validator(mode="after")
    def validate_cors_wildcard_for_production(self) -> Settings:
        if self.APP_ENV.lower() == "production" and "*" in self.CORS_ALLOWED_ORIGINS:
            raise RuntimeError(
                "CORS_ALLOWED_ORIGINS cannot include '*' when APP_ENV=production."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def _rate_limit_key(request: Request) -> str:
    """Rate-limit key: per IP and per tenant when tenant is resolved."""
    remote_address = get_remote_address(request)
    tenant_id = getattr(request.state, "tenant_id", None)
    base_key = f"{remote_address}:{tenant_id}" if tenant_id else remote_address

    # Keep test isolation deterministic without changing production behavior.
    current_test = os.getenv("PYTEST_CURRENT_TEST", "")
    if current_test:
        test_id = current_test.split(" (", 1)[0]
        return f"{base_key}:{test_id}"
    return base_key


settings = get_settings()
limiter = Limiter(key_func=_rate_limit_key, headers_enabled=True)
