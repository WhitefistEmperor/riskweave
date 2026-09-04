"""Environment-driven configuration. No implicit .env loading or secret logging."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RINGSENTINEL_", extra="ignore", populate_by_name=True
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr("sqlite:///./work/ringsentinel.db")
    storage_root: Path = Path("work/storage")
    frontend_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    auth_mode: Literal["development", "disabled"] = "development"
    development_user_id: str = Field(default="local-analyst", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    demo_enabled: bool = True
    jobs_enabled: bool = True
    upload_limit_bytes: int = Field(default=25_000_000, ge=1024, le=100_000_000)
    analysis_timeout_seconds: int = Field(default=300, ge=1, le=3600)
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
        return self
