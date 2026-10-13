"""Application configuration using Pydantic Settings."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Caos Vision"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    viewer_url: str = ""  # URL to viewer app (for admin login page link)

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Authentication
    admin_user: str = "admin"
    admin_pass: str = "admin"
    session_expire_seconds: int = 3600

    # Security - stored as string, use get_allowed_origins() for list
    allowed_origins: str = "*"
    rate_limit_attempts: int = 5
    rate_limit_window: int = 300

    def get_allowed_origins(self) -> List[str]:
        """Get allowed origins as a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    # Cloudflare / Proxy
    cloudflare_tunnel: bool = False
    behind_proxy: bool = False

    # Streams
    max_streams: int = 50


settings = Settings()
