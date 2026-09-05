"""Acesso ao tribunal por **capacidade**, não por tecnologia.

Uma rota ``(sistema, tribunal, grau)`` serve a exatamente duas coisas: **ler os
autos** e **protocolar**. Este módulo é o *único* lugar que decide se cada uma
está disponível e, quando não está, o que falta.

Duas regras que a UI precisa contar e que ficam travadas aqui:

- **Ler os autos** tem duas fontes possíveis: o canal oficial do tribunal
  (quando há perfil MNI *e* credencial ativa) ou o computador pareado.
- **Protocolar tem uma só**: o computador pareado — em todo tribunal, inclusive
  onde existe credencial oficial. ``MniFilingDriver`` não existe e
  ``connectors/drivers.py`` falha fechado para protocolo no backend. Essa
  assimetria é a informação mais valiosa da tela e some quando se organiza por
  canal.

``assistant.resolve_next_step`` consome esta decisão em vez de repetir a ordem
das regras — o ``AGENTS.md`` proíbe um segundo ponto de decisão.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

# ``via``: quem atende a capacidade. ``falta``: a próxima ação do advogado.
VIA_OFICIAL = "oficial"
VIA_COMPUTADOR = "computador"

FALTA_PAREAR = "parear"
FALTA_LOGAR = "logar"
FALTA_RECONECTAR = "reconectar"


@dataclass(frozen=True)
class Capacidade:
    disponivel: bool
    via: str | None
    falta: str | None


@dataclass(frozen=True)
class AcessoTribunal:
    sistema: str
    tribunal: str
    grau: str
    ler_autos: Capacidade
    protocolar: Capacidade
    #: O tribunal *tem* canal oficial de leitura, com ou sem credencial nossa.
    mni_disponivel: bool


_PRONTO_PELO_COMPUTADOR = Capacidade(disponivel=True, via=VIA_COMPUTADOR, falta=None)


def _falta(motivo: str) -> Capacidade:
    return Capacidade(disponivel=False, via=None, falta=motivo)


def _acesso_pelo_computador(
    session: Session, *, escritorio_id: int, sistema: str, tribunal: str, grau: str,
    operation: str = "reader",
) -> Capacidade:
    """O que falta para o computador pareado atender esta rota."""
    from app.connectors import sessions as court_sessions
    from app.connectors.assistant import has_online_agent
    from app.connectors.registry import get_connector_registry, UnsupportedConnectorProfile

    try:
        getattr(get_connector_registry(), operation)(sistema, tribunal=tribunal, grau=grau)
    except UnsupportedConnectorProfile:
        return _falta("integracao_indisponivel")

    if not has_online_agent(session, escritorio_id):
        return _falta(FALTA_PAREAR)
    state = court_sessions.session_state_for(
        session,
        escritorio_id=escritorio_id,
        sistema=sistema,
        tribunal=tribunal,
        grau=grau,
    )
    if state is not None and state.status == "expirado":
        return _falta(FALTA_RECONECTAR)
    if state is None or state.status != "conectado":
        return _falta(FALTA_LOGAR)
    return _PRONTO_PELO_COMPUTADOR


def resolve_acesso_tribunal(
    session: Session,
    *,
    escritorio_id: int,
    sistema: str,
    tribunal: str,
    grau: str,
) -> AcessoTribunal:
    from app.connectors.mni.credentials import find_active_credencial
    from app.connectors.mni.profiles import resolve_mni_profile

    mni_disponivel = resolve_mni_profile(tribunal, grau) is not None
    tem_credencial = (
        mni_disponivel
        and find_active_credencial(
            session, escritorio_id=escritorio_id, tribunal=tribunal
        )
        is not None
    )

    pelo_computador = _acesso_pelo_computador(
        session,
        escritorio_id=escritorio_id,
        sistema=sistema,
        tribunal=tribunal,
        grau=grau,
    )
    ler_autos = (
        Capacidade(disponivel=True, via=VIA_OFICIAL, falta=None)
        if tem_credencial
        else pelo_computador
    )

    return AcessoTribunal(
        sistema=sistema,
        tribunal=tribunal,
        grau=grau,
        ler_autos=ler_autos,
        protocolar=_acesso_pelo_computador(
            session, escritorio_id=escritorio_id, sistema=sistema,
            tribunal=tribunal, grau=grau, operation="filing",
        ),
        mni_disponivel=mni_disponivel,
    )
