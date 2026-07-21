"""Credenciais MNI: segredo no vault, referência no SOR, auditoria sempre."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sor import models
from app.vault.service import load_secret, store_generic_secret


class MniCredencialNotFound(RuntimeError):
    pass


def _audit(session: Session, *, acao: str, credencial: models.MniCredencial, ator: str) -> None:
    session.add(models.AuditLog(
        escritorio_id=credencial.escritorio_id,
        ator=ator,
        acao=acao,
        entidade="mni_credencial",
        entidade_id=credencial.id,
        detalhe={"tribunal": credencial.tribunal},
    ))


def store_mni_credencial(
    session: Session,
    *,
    escritorio_id: int,
    usuario_id: int | None,
    tribunal: str,
    id_consultante: str,
    senha: str,
) -> models.MniCredencial:
    tribunal = tribunal.strip().upper()
    referencia = store_generic_secret(
        session,
        usuario_id=usuario_id or 0,
        provedor=f"mni-{tribunal.lower()}",
        secret=senha,
        description=f"Senha de consulta MNI ({tribunal}).",
    )
    existing = session.scalars(
        select(models.MniCredencial).where(
            models.MniCredencial.escritorio_id == escritorio_id,
            models.MniCredencial.tribunal == tribunal,
        )
    ).first()
    if existing is not None:
        existing.id_consultante = id_consultante
        existing.referencia_vault = referencia
        existing.ativo = True
        existing.last_validated_at = None
        credencial = existing
        acao = "mni_credencial_atualizada"
    else:
        credencial = models.MniCredencial(
            escritorio_id=escritorio_id,
            tribunal=tribunal,
            id_consultante=id_consultante,
            referencia_vault=referencia,
            ativo=True,
            created_by_usuario_id=usuario_id,
        )
        session.add(credencial)
        acao = "mni_credencial_cadastrada"
    session.flush()
    _audit(session, acao=acao, credencial=credencial,
           ator=f"usuario:{usuario_id}" if usuario_id else "system")
    return credencial


def find_active_credencial(
    session: Session, *, escritorio_id: int, tribunal: str | None
) -> models.MniCredencial | None:
    if not tribunal:
        return None
    return session.scalars(
        select(models.MniCredencial).where(
            models.MniCredencial.escritorio_id == escritorio_id,
            models.MniCredencial.tribunal == tribunal.strip().upper(),
            models.MniCredencial.ativo.is_(True),
        )
    ).first()


def deactivate_mni_credencial(
    session: Session, *, credencial_id: int, escritorio_id: int
) -> models.MniCredencial:
    credencial = session.get(models.MniCredencial, credencial_id)
    if credencial is None or credencial.escritorio_id != escritorio_id:
        raise MniCredencialNotFound(str(credencial_id))
    credencial.ativo = False
    session.flush()
    _audit(session, acao="mni_credencial_desativada", credencial=credencial, ator="usuario")
    return credencial


def load_credencial_senha(session: Session, credencial: models.MniCredencial) -> str:
    return load_secret(session, credencial.referencia_vault)


def mark_validated(session: Session, credencial: models.MniCredencial) -> None:
    credencial.last_validated_at = datetime.now(timezone.utc)
    session.flush()
