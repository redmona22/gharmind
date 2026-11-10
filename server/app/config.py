from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"  # D:\gharmind\.env


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    app_env: str = "development"
    secret_key: str = "change-me"

    # Comma-separated browser origins allowed to call the API (the React dev server).
    cors_origins: str = "http://localhost:5173"
    access_token_minutes: int = 60
    # Key for encrypting secrets stored in the database (e.g. MFA secrets).
    # Empty = derived from secret_key. In production set a separate long random value.
    encryption_key: str = ""
    # Set true ONLY when the API runs behind your own reverse proxy or load balancer that sets
    # X-Forwarded-For. Used by the login rate limiter to see the real client address.
    trust_forwarded_for: bool = False

    database_url: str
    database_url_app: str
    redis_url: str = "redis://localhost:6379/0"

    # Which AI backend answers customers:
    #   "openai_compat" = anything that speaks the OpenAI chat API: Ollama on your own machine
    #                     (free), or free tiers such as Groq or Gemini's OpenAI-compatible endpoint
    #   "anthropic"     = Claude through Anthropic's paid API
    llm_provider: str = "openai_compat"
    llm_base_url: str = "http://localhost:11434/v1"  # Ollama's default address
    llm_api_key: str = ""  # Ollama needs none. Groq/Gemini/etc. give you one.
    llm_model_routine: str = "qwen2.5:7b"
    llm_model_complex: str = ""  # empty = use the routine model for everything

    anthropic_api_key: str = ""
    # Routine chats use the smaller model, harder ones the stronger one.
    # Override in .env (ANTHROPIC_MODEL_ROUTINE / ANTHROPIC_MODEL_COMPLEX) if needed.
    anthropic_model_routine: str = "claude-haiku-5-5"
    anthropic_model_complex: str = "claude-sonnet-5-5"

    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    # Graph API version. Check Meta's current version when you get access.
    whatsapp_api_version: str = "v21.0"
    sentry_dsn: str = ""


settings = Settings()