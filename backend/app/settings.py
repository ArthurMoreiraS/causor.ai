"""Application settings loaded from environment / .env.

Secrets (certificate passwords, signing credentials) must NEVER be defined
here or anywhere they could leak into prompts/logs — they live in the vault.
This module only holds infra/config knobs.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CAUSOR_", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://causor:causor@localhost:5432/causor"

    # External APIs
    djen_base_url: str = "https://comunicaapi.pje.jus.br/api/v1"
    datajud_base_url: str = "https://api-publica.datajud.cnj.jus.br"
    # Public CNJ key — fetched at runtime/config, never hardcoded permanently.
    datajud_api_key: str = ""

    # HTTP
    http_timeout_seconds: float = 30.0

    # Capture scheduling
    capture_lookback_days: int = 3
    capture_intervalo_horas_default: int = 12


settings = Settings()
