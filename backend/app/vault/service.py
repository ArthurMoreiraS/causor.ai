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
        return _reference_for(usuario_id, provedor, secret)
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
    signature_mode: str = "manual_pjeoffice",
) -> models.CredencialAssinatura:
    usuario = session.get(models.Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNotFoundError("usuario nao encontrado")

    secret_payload = json.dumps(
        {
            "tribunal": tribunal,
            "url_base": url_base,
            "storage_state": storage_state,
            "signature_mode": signature_mode,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    credencial = models.CredencialAssinatura(
        usuario_id=usuario.id,
        provedor="PJeSession",
        referencia_vault=_store_secret_reference(
            session,
            usuario_id=usuario.id,
            provedor="PJeSession",
            secret=secret_payload,
            description="Sessao autenticada PJe assistida; sem senha do usuario.",
        ),
        ativo=True,
    )
    session.add(credencial)
    session.flush()
    _audit(
        session,
        acao="sessao_pje_cadastrada",
        entidade="credencial_assinatura",
        entidade_id=credencial.id,
        ator=f"usuario:{usuario.id}",
        escritorio_id=usuario.escritorio_id,
        detalhe={"tribunal": tribunal, "assinatura": signature_mode},
    )
    return credencial


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
