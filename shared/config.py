from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dental_bot.db"
    redis_url: str = "redis://localhost:6379/0"
    nats_url: str = "nats://localhost:4222"

    core_api_url: str = "http://localhost:8000"
    ai_orchestrator_url: str = "http://localhost:8001"
    crm_mock_url: str = "http://localhost:8002"

    telegram_bot_token: str = ""
    telegram_mode: str = "webhook"
    telegram_proxy_url: str = ""
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = ""
    telegram_api_base: str = "https://api.telegram.org"

    staff_group_chat_id: str = ""
    doctor_telegram_ids: str = ""
    staff_telegram_ids: str = ""
    clinic_phone: str = "+79990000000"

    ai_mode: str = "rules"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"

    crm_mock_failure_rate: float = Field(default=0, ge=0, le=1)
    log_level: str = "INFO"

    admin_token: str = "change-me-admin-token"
    admin_port: int = 8190
    bot_gateway_url: str = "http://127.0.0.1:8180"
    internal_service_token: str = ""
    debug_api_enabled: bool = False
    debug_api_token: str = ""
    notify_telegram_username: str = ""

    @property
    def doctor_ids(self) -> set[str]:
        return _parse_csv(self.doctor_telegram_ids)

    @property
    def staff_ids(self) -> set[str]:
        return _parse_csv(self.staff_telegram_ids)


def _parse_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
