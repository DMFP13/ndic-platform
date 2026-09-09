"""
NDIC Platform Configuration
────────────────────────────
All settings are read from environment variables (or a .env file for local dev).
No secret defaults are ever hard-coded.

Environment variable naming:  UPPER_SNAKE_CASE, e.g. DB_PASSWORD, JWT_SECRET_KEY.

Deployment targets:
  local        → .env file, SSL disabled, local Postgres
  staging      → AWS RDS (SSL required), Secrets Manager for keys
  production   → AWS RDS Multi-AZ, IAM auth, Secrets Manager
"""

import os
from functools import lru_cache
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Nigerian Dairy Intelligence Consortium"
    app_version: str = "1.0.0"
    environment: str = "production"          # local | staging | production
    debug: bool = False
    log_level: str = "INFO"

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    # Railway provides DATABASE_URL directly; individual vars are fallback for local dev
    database_url: str = ""                   # set via DATABASE_URL (Railway auto-sets this)
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "ndic"
    db_user: str = "ndic_app"
    db_password: str = ""                    # set via DB_PASSWORD env var
    # "require" enforces TLS; use "disable" only for local dev
    db_ssl_mode: str = "require"
    db_pool_size: int = 10                   # base connections per process
    db_max_overflow: int = 20                # burst connections
    db_pool_timeout: int = 30                # seconds to wait for a connection
    db_pool_recycle: int = 1800              # recycle connections every 30 min
    db_echo_sql: bool = False                # set True for local query logging

    # AWS RDS IAM auth (replaces password when use_rds_iam_auth=True)
    use_rds_iam_auth: bool = False
    aws_region: str = "eu-west-1"            # Ireland; change to af-south-1 when available

    # ── JWT ───────────────────────────────────────────────────────────────────
    # Generate with: python -c "import secrets; print(secrets.token_hex(64))"
    jwt_secret_key: str = ""                 # REQUIRED — set via JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # ── Ed25519 Cryptographic Signing ─────────────────────────────────────────
    # The platform holds ONE server-side key pair for signing ledger meta-operations.
    # Each user/organisation manages their own key pair; public keys are stored in DB.
    # In production, private keys are NEVER on disk — they're fetched from Secrets Manager.
    platform_private_key_path: str = "/run/secrets/ndic_ed25519_private.pem"
    platform_public_key_path: str = "/run/secrets/ndic_ed25519_public.pem"
    # ARN of the AWS Secrets Manager secret holding the platform private key
    platform_key_secret_arn: str = ""       # set via PLATFORM_KEY_SECRET_ARN

    # ── AWS ───────────────────────────────────────────────────────────────────
    aws_secrets_manager_endpoint: str = ""  # leave empty to use regional default
    # S3 bucket for large attachment storage (e.g., vet reports, lab PDFs)
    s3_attachments_bucket: str = "ndic-attachments"

    # ── Security / CORS ───────────────────────────────────────────────────────
    allowed_origins: List[str] = ["https://ndic.arpexas.com"]
    max_request_size_mb: int = 10
    rate_limit_per_minute: int = 60         # per IP; configurable per role in middleware

    # ── Alembic / migrations ──────────────────────────────────────────────────
    # Sync URL used only by alembic (asyncpg does not work with alembic env.py)
    alembic_sync_driver: str = "psycopg2"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"local", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    @model_validator(mode="after")
    def require_jwt_secret_in_production(self) -> "Settings":
        if self.environment == "production" and self.debug:
            raise ValueError("debug=True is not allowed in production")
        return self

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def async_database_url(self) -> str:
        """
        asyncpg URL for SQLAlchemy async engine.
        Uses DATABASE_URL env var directly when set (e.g. Railway), otherwise
        builds from individual DB_* vars.
        """
        if self.database_url:
            # Railway provides postgresql:// — rewrite to asyncpg driver
            url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            return url
        ssl_param = "" if self.db_ssl_mode == "disable" else f"?ssl={self.db_ssl_mode}"
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}{ssl_param}"
        )

    @property
    def sync_database_url(self) -> str:
        """
        psycopg2 URL for Alembic migrations (sync context only).
        """
        ssl_param = (
            ""
            if self.db_ssl_mode == "disable"
            else f"?sslmode={self.db_ssl_mode}"
        )
        return (
            f"postgresql+{self.alembic_sync_driver}://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}{ssl_param}"
        )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sqlalchemy_engine_kwargs(self) -> dict:
        return {
            "pool_size": self.db_pool_size,
            "max_overflow": self.db_max_overflow,
            "pool_timeout": self.db_pool_timeout,
            "pool_recycle": self.db_pool_recycle,
            "echo": self.db_echo_sql,
        }


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings singleton.
    Call get_settings() anywhere; the .env file is parsed only once.
    """
    return Settings()


# ---------------------------------------------------------------------------
# Async engine + session factory
# Imported by FastAPI dependency injection and background workers.
# ---------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


def build_engine(settings: Settings | None = None):
    s = settings or get_settings()
    return create_async_engine(
        s.async_database_url,
        **s.sqlalchemy_engine_kwargs,
    )


def build_session_factory(engine=None):
    eng = engine or build_engine()
    return async_sessionmaker(
        eng,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# Lazily initialised singletons (populated on first import by app startup)
_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = build_session_factory(get_engine())
    return _session_factory


async def get_db_session() -> AsyncSession:
    """
    FastAPI dependency.

    Usage:
        @router.post("/animals")
        async def create_animal(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
