"""Signing credential vault boundary.

The local implementation stores only a deterministic non-secret reference in
the SOR. Real providers can swap in behind this service without changing API
handlers or agent code.
"""

from __future__ import annotations

from hashlib import sha256
import json

from sqlalchemy import text
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.settings import settings
from app.sor import models


class VaultError(RuntimeError):
    """Base exception for vault failures."""


class UsuarioNotFoundError(VaultError):
    """Raised when a credential references an unknown user."""


class CredencialNotFoundError(VaultError):
    """Raised when a signing credential does not exist."""


class VaultProviderError(VaultError):
    """Raised when the configured vault provider cannot store a secret."""


_LOCALDEV_SECRETS: dict[str, str] = {}


def _audit(
    session: Session,
    *,
    acao: str,
    entidade: str,
    entidade_id: int,
    ator: str,
    escritorio_id: int | None = None,
    detalhe: dict | None = None,
) -> None:
    session.add(
        models.AuditLog(
            escritorio_id=escritorio_id,
            ator=ator,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhe=detalhe or {},
        )
    )


def _reference_for(usuario_id: int, provedor: str, external_ref: str) -> str:
    digest = sha256(f"{usuario_id}:{provedor}:{external_ref}".encode("utf-8")).hexdigest()
    return f"localdev://assinatura/{usuario_id}/{provedor.lower()}/{digest[:16]}"


def _store_secret_reference(
    session: Session,
    *,
    usuario_id: int,
    provedor: str,
    secret: str,
    description: str,
) -> str:
    provider = settings.vault_provider.strip().lower()
    if provider == "localdev":
        reference = _reference_for(usuario_id, provedor, secret)
        _LOCALDEV_SECRETS[reference] = secret
        return reference
    if provider == "supabase":
        try:
            secret_id = session.execute(
                text(
                    "select vault.create_secret("
                    ":secret_value, :secret_name, :secret_description)"
                ),
                {
                    "secret_value": secret,
                    "secret_name": f"causor:{usuario_id}:{provedor.lower()}",
                    "secret_description": description,
                },
            ).scalar_one()
        except Exception as exc:  # noqa: BLE001 - SQL extension errors vary by provider
            raise VaultProviderError("falha ao gravar segredo no Supabase Vault") from exc
        return f"supabase-vault://{secret_id}"
    raise VaultProviderError(
        f"vault provider desconhecido: {settings.vault_provider!r}"
    )


def _load_secret_from_reference(session: Session, reference: str) -> str:
    if reference.startswith("localdev://"):
        try:
            return _LOCALDEV_SECRETS[reference]
        except KeyError as exc:
            raise VaultProviderError(
                "segredo localdev nao esta em memoria; recadastre a sessao assistida"
            ) from exc
    if reference.startswith("supabase-vault://"):
        secret_id = reference.removeprefix("supabase-vault://")
        try:
            return session.execute(
                text("select decrypted_secret from vault.decrypted_secrets where id = :secret_id"),
                {"secret_id": secret_id},
            ).scalar_one()
        except Exception as exc:  # noqa: BLE001 - SQL extension errors vary by provider
            raise VaultProviderError("falha ao recuperar segredo no Supabase Vault") from exc
    raise VaultProviderError("referencia de vault desconhecida")


def store_court_session(
    session: Session,
    *,
    usuario_id: int,
    sistema: str,
    tribunal: str,
    grau: str,
    url_base: str,
    storage_state: dict,
) -> models.CredencialAssinatura:
    """Guarda uma sessao autenticada de tribunal no cofre (chaveiro).

    Um advogado pode ter N sessoes, uma por ``(sistema, tribunal, grau)``. O
    cofre guarda apenas o ``storage_state`` (cookie) e metadados; nunca senha,
    certificado, PIN ou OTP.
    """
    usuario = session.get(models.Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNotFoundError("usuario nao encontrado")

    secret_payload = json.dumps(
        {
            "sistema": sistema,
            "tribunal": tribunal,
            "grau": grau,
            "url_base": url_base,
            "storage_state": storage_state,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    credencial = models.CredencialAssinatura(
        usuario_id=usuario.id,
        provedor="CourtSession",
        tipo="session",
        sistema=sistema,
        tribunal=tribunal,
        grau=grau,
        referencia_vault=_store_secret_reference(
            session,
            usuario_id=usuario.id,
            provedor="CourtSession",
            secret=secret_payload,
            description="Sessao autenticada de tribunal; sem senha do usuario.",
        ),
        ativo=True,
    )
    session.add(credencial)
    session.flush()
    _audit(
        session,
        acao="sessao_tribunal_cadastrada",
        entidade="credencial_assinatura",
        entidade_id=credencial.id,
        ator=f"usuario:{usuario.id}",
        escritorio_id=usuario.escritorio_id,
        detalhe={"sistema": sistema, "tribunal": tribunal, "grau": grau},
    )
    return credencial


def load_court_session_payload(
    session: Session,
    *,
    credencial_id: int | None,
) -> dict | None:
    if credencial_id is None:
        return None
    credencial = session.get(models.CredencialAssinatura, credencial_id)
    if credencial is None:
        raise CredencialNotFoundError("credencial de assinatura nao encontrada")
    if credencial.tipo != "session":
        return None
    secret = _load_secret_from_reference(session, credencial.referencia_vault)
    try:
        payload = json.loads(secret)
    except json.JSONDecodeError as exc:
        raise VaultProviderError("payload de sessao invalido no vault") from exc
    if not isinstance(payload, dict):
        raise VaultProviderError("payload de sessao invalido no vault")
    if not payload.get("url_base") or not payload.get("storage_state"):
        raise VaultProviderError("payload de sessao incompleto no vault")
    return payload


def find_active_session(
    session: Session,
    *,
    usuario_id: int,
    sistema: str,
    tribunal: str,
    grau: str,
) -> models.CredencialAssinatura | None:
    """Acha a sessao ativa que casa ``(sistema, tribunal, grau)`` do advogado."""
    stmt = (
        select(models.CredencialAssinatura)
        .where(
            models.CredencialAssinatura.usuario_id == usuario_id,
            models.CredencialAssinatura.tipo == "session",
            models.CredencialAssinatura.ativo.is_(True),
            models.CredencialAssinatura.sistema == sistema,
            models.CredencialAssinatura.tribunal == tribunal,
            models.CredencialAssinatura.grau == grau,
        )
        .order_by(models.CredencialAssinatura.id.desc())
    )
    return session.scalars(stmt).first()


def load_pje_session_payload(
    session: Session,
    *,
    credencial_id: int | None,
) -> dict | None:
    """Wrapper retrocompativel: carrega uma sessao de tribunal do cofre."""
    return load_court_session_payload(session, credencial_id=credencial_id)


def store_signature_reference(
    session: Session,
    *,
    usuario_id: int,
    provedor: str,
    external_ref: str,
) -> models.CredencialAssinatura:
    usuario = session.get(models.Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNotFoundError("usuario nao encontrado")

    credencial = models.CredencialAssinatura(
        usuario_id=usuario.id,
        provedor=provedor,
        tipo="cloud_cert",  # referencia de assinatura, nao sessao de navegacao
        referencia_vault=_store_secret_reference(
            session,
            usuario_id=usuario.id,
            provedor=provedor,
            secret=external_ref,
            description="Referencia de credencial de assinatura do Causor.",
        ),
        ativo=True,
    )
    session.add(credencial)
    session.flush()
    _audit(
        session,
        acao="credencial_assinatura_cadastrada",
        entidade="credencial_assinatura",
        entidade_id=credencial.id,
        ator=f"usuario:{usuario.id}",
        escritorio_id=usuario.escritorio_id,
        detalhe={"provedor": provedor},
    )
    return credencial


def store_pje_session_reference(
    session: Session,
    *,
    usuario_id: int,
    tribunal: str,
    url_base: str,
    storage_state: dict,
) -> models.CredencialAssinatura:
    """Wrapper retrocompativel: grava uma sessao PJe (1o grau) no chaveiro."""
    return store_court_session(
        session,
        usuario_id=usuario_id,
        sistema="PJe",
        tribunal=tribunal,
        grau="1",
        url_base=url_base,
        storage_state=storage_state,
    )


def list_signature_credentials(
    session: Session,
    *,
    usuario_id: int,
) -> list[models.CredencialAssinatura]:
    stmt = (
        select(models.CredencialAssinatura)
        .where(models.CredencialAssinatura.usuario_id == usuario_id)
        .order_by(models.CredencialAssinatura.id.desc())
    )
    return list(session.scalars(stmt))


def deactivate_signature_credential(
    session: Session,
    *,
    credencial_id: int,
) -> models.CredencialAssinatura:
    credencial = session.get(models.CredencialAssinatura, credencial_id)
    if credencial is None:
        raise CredencialNotFoundError("credencial de assinatura nao encontrada")
    credencial.ativo = False
    usuario = session.get(models.Usuario, credencial.usuario_id)
    _audit(
        session,
        acao="credencial_assinatura_desativada",
        entidade="credencial_assinatura",
        entidade_id=credencial.id,
        ator=f"usuario:{credencial.usuario_id}",
        escritorio_id=usuario.escritorio_id if usuario is not None else None,
        detalhe={"provedor": credencial.provedor},
    )
    return credencial
