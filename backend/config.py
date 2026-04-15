from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str
    php_api_base_url: str = "https://davidaedwards.com/ausfdclist"
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 4096
    okta_client_id: str = ""
    okta_issuer: str = ""
    okta_domain: str = ""
    okta_redirect_uri: str = "http://localhost:8000/auth/callback"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
