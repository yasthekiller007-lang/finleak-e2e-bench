from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.intelligence.schema import Limits
from app.operations.intake_schema import IntakeLimits
from app.proof.schema import OperationalLimits
from app.recovery.schema import Limits as RecoveryLimits

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FLA_",
        env_file=REPOSITORY_ROOT / ".env",
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    processing_limits: Limits = Field(default_factory=Limits)
    recovery_limits: RecoveryLimits = Field(default_factory=RecoveryLimits)
    proof_limits: OperationalLimits = Field(default_factory=OperationalLimits)
    intake_limits: IntakeLimits = Field(default_factory=IntakeLimits)
    max_extraction_attempts: int = Field(default=10, ge=1, le=100)

    environment: Literal["development", "test", "production"] = "development"
    database_url: PostgresDsn | None = None
    database_timeout_seconds: int = Field(default=5, ge=1, le=30)
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=0, ge=0, le=10)
    database_pool_timeout_seconds: int = Field(default=5, ge=1, le=10)
    release_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    public_app_url: str | None = None
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    storage_backend: Literal["local", "s3"] = "local"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = Field(default=None, min_length=3, max_length=63)
    s3_region: str | None = None
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_timeout_seconds: int = Field(default=5, ge=1, le=10)
    s3_work_seconds: int = Field(default=25, ge=1, le=30)
    s3_private_profile: Literal["public-block", "no-policy"] = "public-block"
    scanner_backend: Literal["unconfigured", "clamav"] = "unconfigured"
    scanner_host: str | None = None
    scanner_socket_path: Path | None = None
    scanner_database_url: PostgresDsn | None = None
    scanner_port: int = Field(default=3310, ge=1, le=65535)
    scanner_timeout_seconds: int = Field(default=5, ge=1, le=10)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    storage_root: Path = REPOSITORY_ROOT / ".local" / "documents"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    oidc_issuer: str | None = Field(
        default=None, min_length=1, max_length=512, validation_alias="OIDC_ISSUER_URL"
    )
    oidc_audience: str | None = Field(
        default=None, min_length=1, max_length=512, validation_alias="OIDC_AUDIENCE"
    )
    oidc_jwks_url: str | None = Field(default=None, validation_alias="OIDC_JWKS_URL")
    oidc_signing_algorithms: list[
        Literal[
            "RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA"
        ]
    ] = Field(
        default_factory=lambda: ["RS256"], min_length=1, validation_alias="OIDC_SIGNING_ALGORITHMS"
    )
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)

    @field_validator("s3_access_key_id", "s3_secret_access_key", mode="before")
    @classmethod
    def empty_storage_credential(cls, value):
        return None if value == "" else value

    @field_validator("oidc_issuer", "oidc_audience", "oidc_jwks_url", mode="before")
    @classmethod
    def empty_oidc_setting(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def secure_identity_configuration(self):
        for value in (self.oidc_issuer, self.oidc_jwks_url):
            if value is None:
                continue
            url = urlsplit(value)
            local_http = (
                self.environment != "production"
                and url.scheme == "http"
                and url.hostname in {"localhost", "127.0.0.1", "::1"}
            )
            if (
                not url.hostname
                or url.username
                or url.password
                or url.fragment
                or (url.scheme != "https" and not local_http)
            ):
                raise ValueError(
                    "OIDC URLs require HTTPS; only non-production loopback may use HTTP"
                )
        if self.environment == "production" and "*" in self.cors_origins:
            raise ValueError("Production CORS must use explicit origins")
        return self

    @field_validator("database_url")
    @classmethod
    def supported_driver(cls, value: PostgresDsn | None) -> PostgresDsn | None:
        if value is not None and value.scheme != "postgresql+psycopg":
            raise ValueError("Use the installed synchronous driver: postgresql+psycopg://")
        return value

    @field_validator("storage_root")
    @classmethod
    def absolute_storage_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else (REPOSITORY_ROOT / value).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
