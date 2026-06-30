from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./hardware_hub.db"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24

    admin_email: str = "admin@booksy.com"
    admin_password: str = "admin123"
    allowed_email_domain: str = "booksy.com"

    gemini_api_key: str = ""
    # Free-tier Gemini model that supports custom function calling (tools).
    # Alternatives: gemini-2.5-flash-lite (higher free throughput),
    # gemini-3-flash-preview (newest). gemini-2.0-flash is retired.
    gemini_model: str = "gemini-3.5-flash"


settings = Settings()
