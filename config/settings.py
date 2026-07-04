from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "cropsense-api"
    environment: str = "development"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    allowed_methods: str = "GET,POST,OPTIONS"
    allow_headers: str = "Authorization,Content-Type"
    cors_max_age: int = 600
    force_https: bool = False
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    max_upload_size_bytes: int = 5_242_880
    allowed_upload_content_types: str = "image/jpeg,image/png,image/webp"
    jwt_secret: str | None = None
    openai_model: str | None = None
    openai_api_key: str | None = None
    openweather_api_key: str | None = None
    access_token_minutes: int = 30
    refresh_token_minutes: int = 60 * 24 * 14

    model_path: str = "models/rice_disease_model.keras"
    model_use_gpu: bool = False
    model_cpu_inter_threads: int = 1
    model_cpu_intra_threads: int = 2
    model_gpu_memory_limit_mb: int | None = None
    metrics_token: str | None = None
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    allow_heuristic_fallbacks: bool = False

    # Database configuration
    database_url: str = "sqlite:///cropsense.db"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    analysis_retention_days: int = 730
    weather_retention_days: int = 365
    chat_retention_days: int = 90

    # Email configuration for password reset
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    frontend_url: str = "http://localhost:5173"

    # Redis configuration for distributed rate limiting
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    redis_use_rate_limiting: bool = False

    @field_validator("jwt_secret")
    def require_jwt_secret(cls, value, info):
        # Require JWT secret to be set
        if not value:
            raise ValueError("JWT_SECRET must be set in environment variables. Generate a strong secret using: python -c 'import secrets; print(secrets.token_urlsafe(32))'")
        
        # Require minimum length for security
        if len(value) < 32:
            raise ValueError("JWT secret must be at least 32 characters long for security")
        
        # Production-specific validation
        if info.data.get("environment") == "production" and len(value) < 64:
            raise ValueError("JWT_SECRET must be at least 64 characters in production")
        
        return value

    @model_validator(mode="after")
    def validate_model_available(self):
        # If heuristics are disabled, model file must exist.
        if not self.allow_heuristic_fallbacks and not Path(self.model_path).exists():
            raise ValueError(
                f"Model file not found at {self.model_path}. "
                "Either provide the trained model file or set ALLOW_HEURISTIC_FALLBACKS=true "
                "(not recommended for production)."
            )
        return self

    @field_validator("database_url")
    def validate_database_url(cls, value: str, info):
        if not value.startswith(("sqlite:///", "postgresql://", "postgres://")):
            raise ValueError(
                "DATABASE_URL must use sqlite:///, postgresql://, or postgres://. "
                "Unsupported database URLs never fall back silently."
            )
        return value

    @field_validator("openai_api_key", "openweather_api_key")
    def validate_api_keys(cls, value: str | None, info):
        # Require API keys in production
        if info.data.get("environment") == "production" and not value:
            field_name = info.field_name
            raise ValueError(
                f"{field_name.upper()} must be set in production environment variables. "
                f"Set {field_name.upper()} in your .env file."
            )
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self):
        if self.environment != "production":
            return self

        required = {
            "METRICS_TOKEN": self.metrics_token,
            "REDIS_PASSWORD": self.redis_password,
            "SMTP_HOST": self.smtp_host,
            "SMTP_USERNAME": self.smtp_username,
            "SMTP_PASSWORD": self.smtp_password,
            "SMTP_FROM_EMAIL": self.smtp_from_email,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing production settings: {', '.join(missing)}")
        if not self.redis_use_rate_limiting:
            raise ValueError("REDIS_USE_RATE_LIMITING must be true in production")
        if not self.frontend_url.startswith("https://"):
            raise ValueError("FRONTEND_URL must use https:// in production")
        origins = self.frontend_origin_list
        if not origins or any(not origin.startswith("https://") for origin in origins):
            raise ValueError("All FRONTEND_ORIGINS must use https:// in production")
        production_hosts = [
            host for host in self.allowed_hosts_list
            if host not in {"localhost", "127.0.0.1", "testserver"}
        ]
        if not production_hosts:
            raise ValueError("ALLOWED_HOSTS must include a production hostname")
        return self

    @property
    def frontend_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def allowed_methods_list(self) -> list[str]:
        return [method.strip() for method in self.allowed_methods.split(",") if method.strip()]

    @property
    def allow_headers_list(self) -> list[str]:
        return [header.strip() for header in self.allow_headers.split(",") if header.strip()]

    @property
    def allowed_upload_content_types_list(self) -> list[str]:
        return [mime.strip() for mime in self.allowed_upload_content_types.split(",") if mime.strip()]

    model_config = SettingsConfigDict(env_file=".env")


def get_settings() -> Settings:
    return Settings()


