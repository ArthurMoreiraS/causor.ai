"""Papéis do escritório e o que cada um pode fazer.

Única fonte da matriz de permissões. O backend aplica (403); o frontend só
esconde o que não se pode fazer. Todos os membros enxergam todo o escritório:
a hierarquia restringe ações, não leitura (decisão de 07/10/2026).
"""

from __future__ import annotations

from typing import Literal

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.jwt_auth import CurrentUser, get_current_user
from app.auth.tenant import get_owned_or_404
from app.sor import models

Papel = Literal["administrador", "advogado", "assistente"]
PAPEIS: tuple[str, ...] = ("administrador", "advogado", "assistente")

Permissao = Literal["gerir_equipe", "configurar_escritorio", "aprovar_minuta", "decidir_prazo"]

PERMISSOES: dict[str, frozenset[str]] = {
    # Convidar, mudar papel, desativar.
    "gerir_equipe": frozenset({"administrador"}),
    # Nome, CNPJ, timbrado, OABs monitoradas e credenciais de tribunal.
    "configurar_escritorio": frozenset({"administrador"}),
    # O advogado responde profissionalmente pela peça e pelo prazo.
    "aprovar_minuta": frozenset({"administrador", "advogado"}),
    "decidir_prazo": frozenset({"administrador", "advogado"}),
}

MENSAGENS = {
    "gerir_equipe": "Só administradores gerenciam a equipe.",
    "configurar_escritorio": "Só administradores alteram a configuração do escritório.",
    "aprovar_minuta": "Só advogados e administradores aprovam minutas.",
    "decidir_prazo": "Só advogados e administradores alteram prazos.",
}


def pode(current: CurrentUser, permissao: Permissao) -> bool:
    return current.papel in PERMISSOES[permissao]


def exigir(current: CurrentUser, permissao: Permissao) -> None:
    if not pode(current, permissao):
        raise HTTPException(status_code=403, detail=MENSAGENS[permissao])


def requer(permissao: Permissao):
    """Dependência FastAPI: ``current: CurrentUser = Depends(requer("..."))``."""

    def _dependencia(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        exigir(current, permissao)
        return current

    return _dependencia


def permissoes_de(papel: str) -> list[str]:
    return sorted(nome for nome, papeis in PERMISSOES.items() if papel in papeis)


def responsavel_valido(session: Session, usuario_id: int, current: CurrentUser) -> models.Usuario:
    """Responsável precisa ser membro ativo do mesmo escritório."""
    usuario = get_owned_or_404(session, models.Usuario, usuario_id, current)
    if not usuario.ativo:
        raise HTTPException(status_code=422, detail="Este membro está desativado e não pode ser responsável.")
    return usuario
