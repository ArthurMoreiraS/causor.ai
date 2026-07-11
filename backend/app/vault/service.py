"""Signing credential vault boundary.

The local implementation stores only a deterministic non-secret reference in
the SOR. Real providers can swap in behind this service without changing API
handlers or agent code.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

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


# Provider localdev: in-memory por padrao (testes isolados). Quando
# CAUSOR_VAULT_LOCALDEV_PATH aponta para um arquivo, os segredos passam a ser
# file-backed e sobrevivem a um reinicio do backend (demo/dev), sem depender de
# um vault gerenciado. O arquivo fica fora do git.
_LOCALDEV_MEM: dict[str, str] = {}


def _localdev_path() -> Path | None:
    raw = os.getenv("CAUSOR_VAULT_LOCALDEV_PATH")
    return Path(raw) if raw else None


def _localdev_load() -> dict[str, str]:
    path = _localdev_path()
    if path is None:
        return dict(_LOCALDEV_MEM)  # cópia: save() faz clear()+update() sem apagar a fonte
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _localdev_save(data: dict[str, str]) -> None:
    path = _localdev_path()
    if path is None:
        _LOCALDEV_MEM.clear()
        _LOCALDEV_MEM.update(data)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


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
        data = _localdev_load()
        data[reference] = secret
        _localdev_save(data)
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
        data = _localdev_load()
        try:
            return data[reference]
        except KeyError as exc:
            raise VaultProviderError(
                "segredo localdev nao encontrado; recadastre a sessao assistida"
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
