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
    http_timeout_seconds: float = 120.0
    # Comma-separated list of allowed frontend origins (set the deployed domain
    # in production, e.g. "https://app.seudominio.com").
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Auth (Supabase). Aceita segredo HS256 legado ou chave PEM ES256;
    # tokens ES256 tambem podem ser validados pelo JWKS anunciado no issuer.
    supabase_jwt_secret: str = ""

    # Agente / LLM. O Causor usa Claude; modelos por tarefa mantem custo baixo:
    # Haiku for routine chat/classification; Sonnet for legal drafting quality.
    claude_model: str = "claude-sonnet-5"
    claude_chat_model: str = "claude-haiku-4-5"
    claude_classification_model: str = "claude-haiku-4-5"
    claude_draft_model: str = "claude-sonnet-5"
    # Resumo por documento dos autos (volume alto, tarefa extrativa): Haiku.
    claude_context_model: str = "claude-haiku-4-5"

    # Provedor de LLM para testes sem gastar creditos Claude. "claude" (default,
    # producao) usa o SDK Anthropic; "openai_compat" aponta para qualquer endpoint
    # compativel com a OpenAI Chat Completions API (Groq, OpenRouter, Gemini
    # OpenAI-compat, Ollama local). So cobre o pipeline classificar+gerar minuta
    # (LLMProvider); o chat agentic continua no Claude.
    llm_provider: str = "claude"  # "claude" | "openai_compat"
    llm_base_url: str = ""  # ex.: "https://api.groq.com/openai/v1" ou "http://localhost:11434/v1"
    llm_api_key: str = ""  # "" para Ollama local; chave do provedor para Groq/OpenRouter
    llm_model: str = ""  # ex.: "llama-3.3-70b-versatile" (Groq) ou "llama3.1:8b" (Ollama)
    # Teto de tokens de saida para o provider openai_compat. O drafter pede 8000
    # (afinado pro Claude); modelos gratuitos com contexto menor (ex.: 8192)
    # rejeitam 413 quando entrada + max_tokens ultrapassa o contexto. 4000 e
    # suficiente pra uma minuta de teste. 0 = respeita o valor pedido pelo caller.
    llm_max_tokens: int = 4000
    # Retry em falhas transientes do endpoint openai_compat: 429 (rate limit) e
    # 5xx de sobrecarga sao comuns em tiers gratuitos (ex.: Gemini free tier).
    # Mesma semantica de capture_retry_attempts/backoff: backoff exponencial.
    llm_retry_attempts: int = 3
    llm_retry_backoff_seconds: float = 2.0

# Capture scheduling
    capture_lookback_days: int = 3
    capture_manual_lookback_days: int = 60
    capture_intervalo_horas_default: int = 12
    capture_retry_attempts: int = 5
    capture_retry_backoff_seconds: float = 10.0
    job_stale_minutes: int = 60
    # Janela (em dias) de cada lote dentro de um captura_oab job. Quebra um
    # intervalo longo (ex.: 180 dias do /capture/oab manual) em transações
    # curtas e commit progressivo, evitando travar a UI e segurar locks longos.
    # 0 desativa (executa o intervalo inteiro em uma transacao so).
    capture_batch_days: int = 15

    # Vault. Localdev stores only deterministic non-secret references. In
    # production, set to "supabase" so sensitive connector/session material goes
    # into the Supabase Vault extension instead of the SOR tables.
    vault_provider: str = "localdev"  # "localdev" | "supabase"

    # Modo de execução do protocolo. "sandbox" roteia todo sistema para o
    # SandboxDriver determinístico (demo à prova de falhas); "real" usa o
    # conector real de cada sistema (PJe existe; e-SAJ/EPROC/Projudi incrementais).
    filing_mode: str = "sandbox"  # "sandbox" | "real"  (env CAUSOR_FILING_MODE)

    # Storage privado de documentos dos autos. "localdev" grava em disco local;
    # "s3" usa bucket privado (S3/Supabase Storage compat) com URL pré-assinada.
    # Chaves de acesso são backend-only; o agente local só recebe a URL assinada.
    object_store_provider: str = "localdev"  # "localdev" | "s3"
    object_store_local_path: str = "./artifacts/objects"
    object_store_endpoint: str = ""
    object_store_region: str = "sa-east-1"
    object_store_bucket: str = "causor-process-documents"
    object_store_access_key: str = ""
    object_store_secret_key: str = ""

    # Limite de upload aceito do agente local (rota PUT /agent/uploads/local).
    agent_max_upload_bytes: int = 100 * 1024 * 1024

    # Cobertura de conectores: validação live vale por N dias; health-check
    # read-only reexecuta a cada M horas.
    connector_validation_max_age_days: int = 30
    connector_health_interval_hours: int = 24

    # Extração de texto/OCR dos autos. OCR roda apenas em página sem camada
    # textual útil (menos de ocr_min_text_chars caracteres nativos).
    ocr_min_text_chars: int = 30
    ocr_dpi: int = 200
    tesseract_language: str = "por"
    tesseract_cmd: str = ""  # caminho do tesseract.exe se fora do PATH
    document_max_bytes: int = 262144000  # 250 MiB por arquivo de autos
    document_processing_attempts: int = 3
    document_processing_concurrency: int = 1

    # Gate fail-closed do contexto: minuta/protocolo exigem ContextoProcesso
    # ready com fingerprint atual e não mais velho que esta janela (a menos
    # que nada novo tenha chegado do tribunal desde então).
    context_freshness_hours: int = 24


settings = Settings()
