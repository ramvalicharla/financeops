from __future__ import annotations

import base64 as _base64
import os
from functools import lru_cache
from typing import ClassVar

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url
from slowapi import Limiter
from starlette.requests import Request


def is_docker_environment() -> bool:
    return os.path.exists("/.dockerenv")


def is_render_environment() -> bool:
    markers = ("RENDER", "RENDER_SERVICE_ID", "RENDER_EXTERNAL_URL")
    return any(bool(os.getenv(marker, "").strip()) for marker in markers)


class Settings(BaseSettings):
    _DEV_SECRET_KEY_DEFAULT: ClassVar[str] = "dev-secret-key-change-me-before-production-use-123456"
    _DEV_JWT_SECRET_DEFAULT: ClassVar[str] = "dev-jwt-secret-change-me-before-production-use-123456"
    _DEV_DATABASE_URL_DEFAULT: ClassVar[str] = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    _DEV_REDIS_URL_DEFAULT: ClassVar[str] = "redis://localhost:6379/0"
    _DEV_FIELD_ENCRYPTION_KEY_DEFAULT: ClassVar[str] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    _PLACEHOLDER_MARKERS: ClassVar[tuple[str, ...]] = (
        "change-me",
        "replace-with",
        "placeholder",
        "your_",
        "your-",
        "<",
        ">",
    )

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
    SECRET_KEY: str = _DEV_SECRET_KEY_DEFAULT

    # Database
    DATABASE_URL: PostgresDsn = Field(default=_DEV_DATABASE_URL_DEFAULT)
    DATABASE_READ_REPLICA_URL: PostgresDsn | None = None
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: RedisDsn = Field(default=_DEV_REDIS_URL_DEFAULT)
    REDIS_TOPOLOGY: str = "single"
    REDIS_BROKER_URL: RedisDsn | None = None
    REDIS_CACHE_URL: RedisDsn | None = None
    REDIS_RESULT_BACKEND_URL: RedisDsn | None = None

    # JWT
    JWT_SECRET: str = _DEV_JWT_SECRET_DEFAULT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI Providers
    AI_CFO_ENABLED: bool = False
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    DEEPSEEK_API_KEY: str | None = None
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
    WEBHOOK_EVENT_RETENTION_DAYS: int = 90
    WEBHOOK_EVENT_RETENTION_SLOW_MS: int = 5000

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
    FIELD_ENCRYPTION_KEY: str = _DEV_FIELD_ENCRYPTION_KEY_DEFAULT
    STARTUP_FAIL_FAST: bool = False
    AUTO_MIGRATE: bool = False
    MIGRATION_FAIL_FAST: bool = False
    SEED_ON_STARTUP: bool = False

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
    ENABLE_CHUNKED_TASKS: bool = False
    REQUIRE_EXPLICIT_POLICY: bool = False

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

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_host_scope(cls, v: PostgresDsn) -> PostgresDsn:
        try:
            parsed = make_url(str(v))
        except Exception:
            return v

        host = (parsed.host or "").strip().lower()
        if host == "db" and not is_docker_environment():
            raise ValueError("DATABASE_URL host 'db' only valid inside docker")
        return v

    @model_validator(mode="after")
    def validate_cors_wildcard_for_production(self) -> Settings:
        if self.APP_ENV.lower() == "production" and "*" in self.CORS_ALLOWED_ORIGINS:
            raise RuntimeError(
                "CORS_ALLOWED_ORIGINS cannot include '*' when APP_ENV=production."
            )
        return self

    @model_validator(mode="after")
    def validate_render_environment_requirements(self) -> Settings:
        if not is_render_environment():
            return self

        raw_app_env = os.getenv("APP_ENV")
        if raw_app_env is None or not raw_app_env.strip():
            raise RuntimeError(
                "APP_ENV is required in Render environment and must be set to 'production'."
            )

        if self.APP_ENV.lower() != "production":
            raise RuntimeError(
                "APP_ENV must be 'production' in Render environment."
            )
        return self

    @staticmethod
    def _looks_placeholder(value: str) -> bool:
        normalized = value.strip().lower()
        if not normalized:
            return True
        return any(marker in normalized for marker in Settings._PLACEHOLDER_MARKERS)

    @property
    def anthropic_api_key(self) -> str | None:
        return self.ANTHROPIC_API_KEY

    @property
    def openai_api_key(self) -> str | None:
        return self.OPENAI_API_KEY

    @property
    def deepseek_api_key(self) -> str | None:
        return self.DEEPSEEK_API_KEY

    @property
    def ai_cfo_enabled(self) -> bool:
        return bool(self.AI_CFO_ENABLED)

    @property
    def redis_broker_url(self) -> str:
        return str(self.REDIS_BROKER_URL or self.REDIS_URL)

    @property
    def redis_cache_url(self) -> str:
        return str(self.REDIS_CACHE_URL or self.REDIS_URL)

    @property
    def redis_result_backend_url(self) -> str:
        return str(self.REDIS_RESULT_BACKEND_URL or self.REDIS_URL)

    @model_validator(mode="after")
    def validate_production_security_requirements(self) -> Settings:
        if self.APP_ENV.lower() != "production":
            return self

        required_values: dict[str, str] = {
            "SECRET_KEY": str(self.SECRET_KEY),
            "JWT_SECRET": str(self.JWT_SECRET),
            "DATABASE_URL": str(self.DATABASE_URL),
            "REDIS_URL": str(self.REDIS_URL),
            "FIELD_ENCRYPTION_KEY": str(self.FIELD_ENCRYPTION_KEY),
            "STRIPE_SECRET_KEY": str(self.STRIPE_SECRET_KEY),
            "RAZORPAY_WEBHOOK_SECRET": str(self.RAZORPAY_WEBHOOK_SECRET),
        }

        missing = [name for name, value in required_values.items() if not value.strip()]
        if missing:
            raise RuntimeError(
                f"Missing required production environment variables: {', '.join(missing)}"
            )

        for name, value in required_values.items():
            if self._looks_placeholder(value):
                raise RuntimeError(
                    f"{name} appears to be a placeholder value. "
                    "Set a production-secret value before startup."
                )

        if self.SECRET_KEY == self._DEV_SECRET_KEY_DEFAULT:
            raise RuntimeError("SECRET_KEY cannot use development default in production.")
        if self.JWT_SECRET == self._DEV_JWT_SECRET_DEFAULT:
            raise RuntimeError("JWT_SECRET cannot use development default in production.")
        if str(self.DATABASE_URL) == self._DEV_DATABASE_URL_DEFAULT:
            raise RuntimeError("DATABASE_URL cannot use development default in production.")
        if str(self.REDIS_URL) == self._DEV_REDIS_URL_DEFAULT:
            raise RuntimeError("REDIS_URL cannot use development default in production.")
        if self.FIELD_ENCRYPTION_KEY == self._DEV_FIELD_ENCRYPTION_KEY_DEFAULT:
            raise RuntimeError(
                "FIELD_ENCRYPTION_KEY cannot use development default in production."
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def get_real_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    forwarded_ip = forwarded_for.split(",", 1)[0].strip()
    return (
        request.headers.get("cf-connecting-ip")
        or forwarded_ip
        or (request.client.host if request.client else "unknown")
    )


def _rate_limit_key(request: Request) -> str:
    """Rate-limit key: per IP and per tenant when tenant is resolved."""
    remote_address = get_real_ip(request)
    tenant_id = getattr(request.state, "tenant_id", None)
    base_key = f"{remote_address}:{tenant_id}" if tenant_id else remote_address

    # Keep test isolation deterministic without changing production behavior.
    current_test = os.getenv("PYTEST_CURRENT_TEST", "")
    if current_test:
        test_id = current_test.split(" (", 1)[0]
        return f"{base_key}:{test_id}"
    return base_key


def _build_limiter(*, redis_url: str) -> Limiter:
    return Limiter(
        key_func=_rate_limit_key,
        headers_enabled=True,
        storage_uri=redis_url,
        in_memory_fallback_enabled=True,
    )


settings = get_settings()
limiter = _build_limiter(redis_url=settings.redis_cache_url)
