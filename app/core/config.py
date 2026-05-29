from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Residential Community Platform API"
    app_version: str = "1.0.0"
    environment: str = "development"

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/residential_platform"
    auto_create_tables: bool = False

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7
    otp_expire_minutes: int = 5
    otp_length: int = 6

    fcm_enabled: bool = False
    firebase_credentials_path: str | None = None

    whatsapp_enabled: bool = False
    whatsapp_provider_url: str | None = None
    whatsapp_meta_api_version: str = "v25.0"
    whatsapp_phone_number_id: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_template_name: str = "hello_world"
    whatsapp_template_language: str = "en_US"
    tenant_app_android_url: str = "https://play.google.com/store/apps/details?id=com.example.easystay"
    tenant_app_ios_url: str = "https://apps.apple.com/app/example-easy-stay/id1234567890"

    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:8081"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
