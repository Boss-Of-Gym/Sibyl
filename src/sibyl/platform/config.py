from functools import lru_cache

from fastapi import Request
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    sibyl_env: str = "local"

    database_url: str = "postgresql+asyncpg://sibyl:sibyl_local_dev@localhost:5432/sibyl"
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:9092"

    otel_exporter_otlp_endpoint: str = "http://localhost:4318"

    github_app_id: str = ""
    github_app_private_key_path: str = ""
    github_webhook_secret: str = ""
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""

    llm_provider_api_key: str = ""
    llm_provider_model: str = ""

    jwt_signing_key: str = "local-dev-signing-key-not-for-production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_request_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings
