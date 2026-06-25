"""Application settings loaded from environment / .env.

Secrets (certificate passwords, signing credentials) must NEVER be defined
here or anywhere they could leak into prompts/logs — they live in the vault.
This module only holds infra/config knobs.
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent

# Load .env into the process environment at import time. pydantic-settings reads
# the CAUSOR_* knobs below straight from the file, while the Anthropic SDK reads
# ANTHROPIC_API_KEY directly from os.environ.
for _env_file in (REPO_DIR / ".env", BACKEND_DIR / ".env"):
    if _env_file.exists():
        load_dotenv(_env_file, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_prefix="CAUSOR_",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+psycopg://causor:causor@localhost:5432/causor"

    # External APIs
    djen_base_url: str = "https://comunicaapi.pje.jus.br/api/v1"
    datajud_base_url: str = "https://api-publica.datajud.cnj.jus.br"
    # Public CNJ key — fetched at runtime/config, never hardcoded permanently.
    datajud_api_key: str = ""

    # HTTP / CORS
    http_timeout_seconds: float = 30.0
    # Comma-separated list of allowed frontend origins (set the deployed domain
    # in production, e.g. "https://app.seudominio.com").
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Auth (Supabase). Aceita segredo HS256 legado ou chave PEM ES256;
    # tokens ES256 tambem podem ser validados pelo JWKS anunciado no issuer.
    supabase_jwt_secret: str = ""

    # Agente / LLM. O Causor usa Claude; modelos por tarefa mantem custo baixo:
    # Haiku for routine chat/classification; Sonnet for legal drafting quality.
    claude_model: str = "claude-sonnet-4-6"
    claude_chat_model: str = "claude-haiku-4-5"
    claude_classification_model: str = "claude-haiku-4-5"
    claude_draft_model: str = "claude-sonnet-4-6"

    # Capture scheduling
    capture_lookback_days: int = 3
    capture_intervalo_horas_default: int = 12
    capture_retry_attempts: int = 3
    capture_retry_backoff_seconds: float = 2.0
    job_stale_minutes: int = 60

    # Vault. Localdev stores only deterministic non-secret references. In
    # production, set to "supabase" so sensitive connector/session material goes
    # into the Supabase Vault extension instead of the SOR tables.
    vault_provider: str = "localdev"  # "localdev" | "supabase"


settings = Settings()
