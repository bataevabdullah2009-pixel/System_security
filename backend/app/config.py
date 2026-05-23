from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SmartGuard AI MVP"
    app_env: str = "local"
    app_version: str = "0.1.0"
    service_name: str = "smartguard-ai-backend"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
