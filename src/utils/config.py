from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parent.parent / ".env"


class BaseConfig(BaseSettings):
    """Базовый класс для всех настроек, читающих из .env"""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=ENV_FILE,
        extra="ignore",
    )


class Settings(BaseConfig):
    orders_file: str = "orders.xlsx"
    scheduler_interval: int = 60
    order_status_api_url: str = ""


settings = Settings()
