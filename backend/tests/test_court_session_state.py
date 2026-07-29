import pytest

from app.connectors.sessions import (
    apply_login_failure,
    apply_login_result,
    mark_session_expired,
    request_court_login,
    session_state_for,
)
from app.sor import models


@pytest.fixture
def agent_installation(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    installation = models.AgentInstallation(
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        nome="Notebook jurídico",
        token_hash="c" * 64,
        ativo=True,
    )
    db_session.add(installation)
    db_session.flush()
    return installation


def _instancia(db_session, seeded):
    instancia = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://example.invalid/pje",
        status="active",
    )
    db_session.add(instancia)
    db_session.flush()
    return instancia


def test_login_request_creates_connecting_state_and_command(db_session, seeded, agent_installation):
    instancia = _instancia(db_session, seeded)
    state, command = request_court_login(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=agent_installation.usuario_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_login="https://pje.tjmg.jus.br/pje/login.seam",
        processo_instancia_id=instancia.id,
    )
    assert state.status == "conectando"
    assert command.tipo == "open_court_login"
    assert "storage_state" not in command.payload
    assert command.payload["url_login"].endswith("login.seam")


def test_successful_login_marks_connected_without_storing_cookie(
    db_session, seeded, agent_installation
):
    instancia = _instancia(db_session, seeded)
    state, command = request_court_login(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=agent_installation.usuario_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_login="https://x/login.seam",
        processo_instancia_id=instancia.id,
    )
    apply_login_result(
        db_session,
        command=command,
        installation=agent_installation,
        resultado={
            "session_ready": True,
            "version_marker": "pje-2.5",
            "evidence": {"marker": "painel"},
        },
    )
    refreshed = session_state_for(
        db_session,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
    )
    assert refreshed.status == "conectado"
    assert refreshed.last_confirmed_at is not None
    assert refreshed.version_marker == "pje-2.5"
    assert refreshed.installation_id == agent_installation.id
    # o estado nunca guarda cookie/sessão
    assert not hasattr(refreshed, "storage_state")


def test_login_request_is_idempotent_per_route_and_hour(db_session, seeded, agent_installation):
    instancia = _instancia(db_session, seeded)
    kwargs = dict(
        escritorio_id=seeded.escritorio_id,
        usuario_id=agent_installation.usuario_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_login="https://x/login.seam",
        processo_instancia_id=instancia.id,
    )
    _, first = request_court_login(db_session, **kwargs)
    _, second = request_court_login(db_session, **kwargs)
    assert first.id == second.id


def test_failed_login_marks_state_with_error_code(db_session, seeded, agent_installation):
    instancia = _instancia(db_session, seeded)
    state, command = request_court_login(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=agent_installation.usuario_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_login="https://x/login.seam",
        processo_instancia_id=instancia.id,
    )
    apply_login_failure(
        db_session,
        command=command,
        installation=agent_installation,
        erro_codigo="captcha_required",
    )
    refreshed = session_state_for(
        db_session,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
    )
    assert refreshed.status == "desconectado"
    assert refreshed.last_error_code == "captcha_required"


def test_mark_session_expired_transitions_connected_state(db_session, seeded, agent_installation):
    instancia = _instancia(db_session, seeded)
    _, command = request_court_login(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=agent_installation.usuario_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_login="https://x/login.seam",
        processo_instancia_id=instancia.id,
    )
    apply_login_result(
        db_session,
        command=command,
        installation=agent_installation,
        resultado={"session_ready": True, "version_marker": None, "evidence": {}},
    )
    mark_session_expired(
        db_session,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        error_code="session_expired",
    )
    refreshed = session_state_for(
        db_session,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
    )
    assert refreshed.status == "expirado"
    assert refreshed.last_error_code == "session_expired"


def test_session_state_for_returns_none_when_never_requested(db_session, seeded):
    assert (
        session_state_for(
            db_session,
            escritorio_id=seeded.escritorio_id,
            sistema="EPROC",
            tribunal="TJRS",
            grau="1",
        )
        is None
    )


# --- Checagem de sessão viva -------------------------------------------------
# O gatilho que finalmente aciona o estado "expirado": antes destes testes,
# mark_session_expired só era chamado por teste, nunca por produção.


def _rota(seeded):
    return {
        "escritorio_id": seeded.escritorio_id,
        "sistema": "EPROC",
        "tribunal": "TJTO",
        "grau": "1",
    }


def test_agente_expoe_o_comando_de_checagem():
    from app.local_agent.handlers import default_handlers

    assert "check_court_session" in default_handlers()


def test_sessao_viva_atualiza_confirmacao(db_session, seeded, agent_installation):
    from app.connectors.sessions import apply_session_check_result, request_session_check

    _state, command = request_session_check(
        db_session, usuario_id=None, url_login="https://exemplo/login", **_rota(seeded)
    )
    state = apply_session_check_result(
        db_session,
        command=command,
        installation=agent_installation,
        resultado={"session_alive": True},
    )
    assert state.status == "conectado"
    assert state.last_confirmed_at is not None


def test_sessao_morta_marca_expirado(db_session, seeded, agent_installation):
    from app.connectors.sessions import apply_session_check_result, request_session_check

    _state, command = request_session_check(
        db_session, usuario_id=None, url_login="https://exemplo/login", **_rota(seeded)
    )
    state = apply_session_check_result(
        db_session,
        command=command,
        installation=agent_installation,
        resultado={"session_alive": False, "error_code": "session_expired"},
    )
    assert state.status == "expirado"
    assert state.last_error_code == "session_expired"


def test_perfil_travado_nao_derruba_sessao_boa(db_session, seeded, agent_installation):
    """Lock do Chromium é inconclusivo. Marcar 'expirado' aqui faria o advogado
    relogar à toa toda vez que estivesse com o navegador aberto."""
    from app.connectors.sessions import apply_session_check_result, request_session_check

    _state, command = request_session_check(
        db_session, usuario_id=None, url_login="https://exemplo/login", **_rota(seeded)
    )
    state = apply_session_check_result(
        db_session,
        command=command,
        installation=agent_installation,
        resultado={"session_alive": None, "error_code": "profile_locked"},
    )
    assert state.status != "expirado"
    assert state.last_error_code == "profile_locked"


def test_checagem_e_idempotente_por_rota_e_hora(db_session, seeded):
    from app.connectors.sessions import request_session_check

    _s1, c1 = request_session_check(
        db_session, usuario_id=None, url_login="https://exemplo/login", **_rota(seeded)
    )
    _s2, c2 = request_session_check(
        db_session, usuario_id=None, url_login="https://exemplo/login", **_rota(seeded)
    )
    assert c1.id == c2.id
