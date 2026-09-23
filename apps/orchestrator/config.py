from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str

    # AI provider settings
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ollama_base_url: str = "http://localhost:11434"
    provider_timeout: float = 30.0

    # New chats use OpenRouter's free router by default. The model list still
    # exposes the complete OpenRouter catalog for users with credits.
    default_openrouter_model: str = "openrouter/free"
    default_fallback_model: str = "qwen2.5:3b"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
