"""Acesso ao tribunal descrito por capacidade, não por tecnologia.

A tela de Configurações e o assistente JIT precisam responder à mesma
pergunta — *o advogado consegue ler os autos? consegue protocolar?* — e
precisam responder **igual**. Estes testes travam a matriz de decisão e a
assimetria que a UI nunca contou: protocolar depende sempre do computador
pareado, inclusive onde existe credencial oficial.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.connectors.access_channel import resolve_acesso_tribunal
from app.sor import models

pytestmark = pytest.mark.usefixtures("registered_test_routes")


def test_connected_session_without_driver_is_not_operational(db_session, escritorio, monkeypatch):
    from app.connectors import registry

    monkeypatch.setattr(registry, "_REGISTRY", registry.ConnectorRegistry())
    esc, user = escritorio
    _agente_online(db_session, esc, user)
    _sessao(db_session, esc, tribunal="TJTO", status="conectado")
    access = _resolver(db_session, esc, tribunal="TJTO")
    assert not access.ler_autos.disponivel
    assert access.ler_autos.falta == "integracao_indisponivel"
    assert not access.protocolar.disponivel

# TJMT tem perfil MNI confirmado (1º grau); TJTO não tem — é o par que separa
# "tribunal com canal oficial" de "tribunal só pelo computador".
TRIBUNAL_COM_MNI = "TJMT"
TRIBUNAL_SEM_MNI = "TJTO"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Acesso")
    db_session.add(esc)
    db_session.flush()
    usuario = models.Usuario(
        escritorio_id=esc.id,
        nome="Adv Acesso",
        email="acesso@example.com",
        supabase_user_id="acesso-sub",
    )
    db_session.add(usuario)
    db_session.flush()
    return esc, usuario


def _agente_online(db_session, esc, usuario, *, last_seen: datetime | None = None):
    inst = models.AgentInstallation(
        escritorio_id=esc.id,
        usuario_id=usuario.id,
        nome="Notebook",
        token_hash=f"hash-{esc.id}-{last_seen or 'now'}",
        ativo=True,
        last_seen_at=last_seen or _now(),
    )
    db_session.add(inst)
    db_session.flush()
    return inst


def _sessao(db_session, esc, *, tribunal, status, sistema="EPROC", grau="1"):
    state = models.CourtSessionState(
        escritorio_id=esc.id,
        sistema=sistema,
        tribunal=tribunal,
        grau=grau,
        status=status,
        last_confirmed_at=_now() if status == "conectado" else None,
    )
    db_session.add(state)
    db_session.flush()
    return state


def _credencial_mni(db_session, esc, *, tribunal):
    cred = models.MniCredencial(
        escritorio_id=esc.id,
        tribunal=tribunal,
        id_consultante="12345",
        referencia_vault="vault://mni/1",
        ativo=True,
    )
    db_session.add(cred)
    db_session.flush()
    return cred


def _resolver(db_session, esc, *, tribunal, sistema="EPROC", grau="1"):
    return resolve_acesso_tribunal(
        db_session,
        escritorio_id=esc.id,
        sistema=sistema,
        tribunal=tribunal,
        grau=grau,
    )


def test_sem_agente_pareado_falta_parear_nas_duas_capacidades(db_session, escritorio):
    esc, _ = escritorio

    acesso = _resolver(db_session, esc, tribunal=TRIBUNAL_SEM_MNI)

    assert acesso.ler_autos.disponivel is False
    assert acesso.ler_autos.falta == "parear"
    assert acesso.protocolar.disponivel is False
    assert acesso.protocolar.falta == "parear"


def test_agente_online_sem_sessao_falta_logar(db_session, escritorio):
    esc, usuario = escritorio
    _agente_online(db_session, esc, usuario)

    acesso = _resolver(db_session, esc, tribunal=TRIBUNAL_SEM_MNI)

    assert acesso.ler_autos.falta == "logar"
    assert acesso.protocolar.falta == "logar"


def test_sessao_expirada_pede_reconectar(db_session, escritorio):
    esc, usuario = escritorio
    _agente_online(db_session, esc, usuario)
    _sessao(db_session, esc, tribunal=TRIBUNAL_SEM_MNI, status="expirado")

    acesso = _resolver(db_session, esc, tribunal=TRIBUNAL_SEM_MNI)

    assert acesso.ler_autos.falta == "reconectar"
    assert acesso.protocolar.falta == "reconectar"


def test_agente_online_e_sessao_conectada_libera_as_duas_pelo_computador(
    db_session, escritorio
):
    esc, usuario = escritorio
    _agente_online(db_session, esc, usuario)
    _sessao(db_session, esc, tribunal=TRIBUNAL_SEM_MNI, status="conectado")

    acesso = _resolver(db_session, esc, tribunal=TRIBUNAL_SEM_MNI)

    assert acesso.ler_autos.disponivel is True
    assert acesso.ler_autos.via == "computador"
    assert acesso.protocolar.disponivel is True
    assert acesso.protocolar.via == "computador"


def test_credencial_oficial_libera_leitura_sem_computador(db_session, escritorio):
    esc, _ = escritorio
    _credencial_mni(db_session, esc, tribunal=TRIBUNAL_COM_MNI)

    acesso = _resolver(db_session, esc, tribunal=TRIBUNAL_COM_MNI, sistema="PJe")

    assert acesso.ler_autos.disponivel is True
    assert acesso.ler_autos.via == "oficial"
    assert acesso.ler_autos.falta is None


def test_protocolar_nunca_e_atendido_pelo_canal_oficial(db_session, escritorio):
    """A assimetria que a tela precisa contar: MNI cobre leitura, não protocolo.

    Enquanto ``MniFilingDriver`` não existir, protocolar depende sempre do
    computador pareado — mesmo no tribunal com credencial oficial ativa.
    """
    esc, _ = escritorio
    _credencial_mni(db_session, esc, tribunal=TRIBUNAL_COM_MNI)

    acesso = _resolver(db_session, esc, tribunal=TRIBUNAL_COM_MNI, sistema="PJe")

    assert acesso.protocolar.via != "oficial"
    assert acesso.protocolar.disponivel is False
    assert acesso.protocolar.falta == "parear"


def test_tribunal_com_perfil_mni_sem_credencial_sinaliza_canal_disponivel(
    db_session, escritorio
):
    esc, _ = escritorio

    com_mni = _resolver(db_session, esc, tribunal=TRIBUNAL_COM_MNI, sistema="PJe")
    sem_mni = _resolver(db_session, esc, tribunal=TRIBUNAL_SEM_MNI)

    assert com_mni.mni_disponivel is True
    assert sem_mni.mni_disponivel is False


def test_agente_com_heartbeat_velho_nao_conta_como_online(db_session, escritorio):
    esc, usuario = escritorio
    _agente_online(db_session, esc, usuario, last_seen=_now() - timedelta(minutes=10))

    acesso = _resolver(db_session, esc, tribunal=TRIBUNAL_SEM_MNI)

    assert acesso.ler_autos.falta == "parear"


def _passo_esperado(acesso) -> str:
    """O passo do assistente que corresponde ao estado do painel."""
    if acesso.ler_autos.falta == "parear":
        return "pair_agent"
    if acesso.ler_autos.falta in ("logar", "reconectar"):
        return "court_login"
    return "capture_autos"


@pytest.mark.parametrize(
    "cenario", ["nada", "agente", "sessao_expirada", "sessao_conectada", "credencial_mni"]
)
def test_assistente_e_painel_nunca_divergem(db_session, escritorio, cenario):
    """Caracterização da decisão única: uma regra, dois consumidores.

    O gate de contexto (via ``resolve_next_step``) e o painel de Configurações
    respondem sobre a mesma rota. Se divergirem, a tela promete um estado que o
    sistema não entrega na hora H. Este teste é o que impede a divergência
    voltar depois da extração.
    """
    from app.connectors.assistant import resolve_next_step

    esc, usuario = escritorio
    tribunal = TRIBUNAL_COM_MNI if cenario == "credencial_mni" else TRIBUNAL_SEM_MNI
    processo = models.Processo(
        escritorio_id=esc.id, numero="00000010020248270729", tribunal=tribunal
    )
    db_session.add(processo)
    db_session.flush()

    if cenario == "credencial_mni":
        _credencial_mni(db_session, esc, tribunal=tribunal)
    if cenario in ("agente", "sessao_expirada", "sessao_conectada"):
        _agente_online(db_session, esc, usuario)
    if cenario == "sessao_expirada":
        _sessao(db_session, esc, tribunal=tribunal, status="expirado")
    if cenario == "sessao_conectada":
        _sessao(db_session, esc, tribunal=tribunal, status="conectado")

    next_step, rota = resolve_next_step(
        db_session, processo=processo, grau="1", context_ready=False
    )
    acesso = _resolver(
        db_session, esc, tribunal=rota["tribunal"], sistema=rota["sistema"]
    )

    assert next_step == _passo_esperado(acesso)


def test_sessao_de_outro_escritorio_nao_libera_acesso(db_session, escritorio):
    esc, usuario = escritorio
    _agente_online(db_session, esc, usuario)
    outro = models.Escritorio(nome="Outro")
    db_session.add(outro)
    db_session.flush()
    _sessao(db_session, outro, tribunal=TRIBUNAL_SEM_MNI, status="conectado")

    acesso = _resolver(db_session, esc, tribunal=TRIBUNAL_SEM_MNI)

    assert acesso.ler_autos.falta == "logar"
