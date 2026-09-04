"""Environment-driven configuration. No implicit .env loading or secret logging."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RINGSENTINEL_", extra="ignore", populate_by_name=True, hide_input_in_errors=True
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr("sqlite:///./work/ringsentinel.db")
    storage_root: Path = Path("work/storage")
    frontend_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    auth_mode: Literal["development", "disabled", "jwt"] = "development"
    auth_jwks_path: Path | None = None
    auth_issuer: str = ""
    auth_audience: str = ""
    auth_required_scope: str = "ringsentinel:analyst"
    auth_max_token_seconds: int = Field(default=900, ge=60, le=3600)
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver", "backend"]
    development_user_id: str = Field(default="local-analyst", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    demo_enabled: bool = True
    jobs_enabled: bool = True
    upload_limit_bytes: int = Field(default=25_000_000, ge=1024, le=100_000_000)
    analysis_timeout_seconds: int = Field(default=300, ge=1, le=3600)
    max_investigations_per_owner: int = Field(default=1000, ge=1, le=10000)
    max_investigations_total: int = Field(default=10000, ge=1, le=100000)
    max_artifacts_per_investigation: int = Field(default=20, ge=1, le=1000)
    max_runs_per_investigation: int = Field(default=50, ge=1, le=1000)
    max_pending_runs: int = Field(default=100, ge=1, le=10000)
    storage_limit_bytes: int = Field(default=2_000_000_000, ge=1024)
    result_limit_bytes: int = Field(default=100_000_000, ge=1024, le=500_000_000)
    retention_days: int = Field(default=90, ge=1, le=3650)
    llm_provider: Literal["disabled", "deterministic", "openai"] = "deterministic"
    openai_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="OPENAI_API_KEY", repr=False
    )
    openai_model: str = "gpt-5.4-mini"
    llm_timeout_seconds: float = Field(default=20, gt=0, le=60)
    llm_retry_count: int = Field(default=0, ge=0, le=2)
    llm_max_output_tokens: int = Field(default=1200, ge=100, le=4000)
    build_commit: str = Field(default="unknown", pattern=r"^(unknown|[a-f0-9]{7,40})$")

    @model_validator(mode="after")
    def deployment_boundary(self) -> "Settings":
        if any(not host or any(c in host for c in "/*:@ ") for host in self.trusted_hosts):
            raise ValueError("Trusted hosts must be explicit hostnames without ports")
        if self.auth_mode == "jwt":
            issuer = urlsplit(self.auth_issuer)
            if (
                not self.auth_jwks_path
                or issuer.scheme != "https"
                or not issuer.hostname
                or issuer.username
                or issuer.password
                or issuer.query
                or issuer.fragment
                or not self.auth_audience.strip()
                or not self.auth_required_scope.strip()
            ):
                raise ValueError(
                    "JWT authentication requires public JWKS, HTTPS issuer, audience and scope"
                )
        for origin in self.frontend_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or "*" in origin
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Explicit HTTP(S) frontend origins without paths are required")
            _ = parsed.port  # Reject malformed/out-of-range port configuration.
        if self.environment == "production":
            if self.auth_mode == "development" or self.demo_enabled:
                raise ValueError("Production cannot enable development identity or public demo")
            if not self.frontend_origins or any(
                not origin.startswith("https://") for origin in self.frontend_origins
            ):
                raise ValueError("Production requires explicit HTTPS origins")
            if "trusted_hosts" not in self.model_fields_set:
                self.trusted_hosts = [urlsplit(o).hostname for o in self.frontend_origins]
                self.trusted_hosts += ["127.0.0.1", "localhost"]  # Private health probes.
        return self
