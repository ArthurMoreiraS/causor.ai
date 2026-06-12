"""Signing credential vault boundary.

The local implementation stores only a deterministic non-secret reference in
the SOR. Real providers can swap in behind this service without changing API
handlers or agent code.
"""

from __future__ import annotations

from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sor import models


class VaultError(RuntimeError):
    """Base exception for vault failures."""


class UsuarioNotFoundError(VaultError):
    """Raised when a credential references an unknown user."""


class CredencialNotFoundError(VaultError):
    """Raised when a signing credential does not exist."""


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
        referencia_vault=_reference_for(usuario.id, provedor, external_ref),
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
