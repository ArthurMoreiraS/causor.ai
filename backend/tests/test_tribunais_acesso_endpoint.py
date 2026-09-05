"""``GET /tribunais/acesso`` — o painel "Seus tribunais" das Configurações.

Agrega por rota ``(sistema, tribunal, grau)`` a partir das instâncias do
escritório, porque é onde o grau existe. Ordena pelo número de processos
afetados: o que trava mais casos aparece primeiro.
"""

from datetime import datetime, timezone

import pytest

from app.sor import models

pytestmark = pytest.mark.usefixtures("registered_test_routes")


@pytest.fixture
def escritorio_com_rotas(db_session):
    esc = models.Escritorio(nome="Escritório Painel")
    db_session.add(esc)
    db_session.flush()
    usuario = models.Usuario(
        escritorio_id=esc.id,
        nome="Adv Painel",
        email="painel@example.com",
        supabase_user_id="painel-sub",
    )
    db_session.add(usuario)
    db_session.flush()

    def _instancia(*, sistema, tribunal, grau, numero):
        processo = models.Processo(
            escritorio_id=esc.id, numero=numero, tribunal=tribunal, sistema=sistema
        )
        db_session.add(processo)
        db_session.flush()
        inst = models.ProcessoInstancia(
            processo_id=processo.id,
            escritorio_id=esc.id,
            sistema=sistema,
            tribunal=tribunal,
            grau=grau,
        )
        db_session.add(inst)
        db_session.flush()
        return inst

    # TJTO 1º grau com 2 processos; TJMT 1º grau com 1 — a ordem do painel
    # precisa refletir isso.
    _instancia(sistema="EPROC", tribunal="TJTO", grau="1", numero="00000010020248270729")
    _instancia(sistema="EPROC", tribunal="TJTO", grau="1", numero="00000020020248270729")
    _instancia(sistema="PJe", tribunal="TJMT", grau="1", numero="00000030020248110001")
    db_session.commit()
    return esc, usuario


def test_lista_rotas_do_escritorio_ordenadas_por_processos(client, escritorio_com_rotas):
    resp = client.get("/tribunais/acesso")

    assert resp.status_code == 200
    rotas = resp.json()
    assert [(r["tribunal"], r["grau"], r["processos"]) for r in rotas] == [
        ("TJTO", "1", 2),
        ("TJMT", "1", 1),
    ]


def test_cada_rota_traz_as_duas_capacidades(client, escritorio_com_rotas):
    resp = client.get("/tribunais/acesso")

    rota = resp.json()[0]
    assert rota["ler_autos"] == {"disponivel": False, "via": None, "falta": "parear"}
    assert rota["protocolar"] == {"disponivel": False, "via": None, "falta": "parear"}


def test_protocolar_nunca_vem_pelo_canal_oficial(client, db_session, escritorio_com_rotas):
    """Mesmo com credencial oficial ativa, protocolar depende do computador."""
    esc, _ = escritorio_com_rotas
    db_session.add(
        models.MniCredencial(
            escritorio_id=esc.id,
            tribunal="TJMT",
            id_consultante="12345",
            referencia_vault="vault://mni/1",
            ativo=True,
        )
    )
    db_session.commit()

    rotas = client.get("/tribunais/acesso").json()
    tjmt = next(r for r in rotas if r["tribunal"] == "TJMT")

    assert tjmt["ler_autos"]["via"] == "oficial"
    assert tjmt["protocolar"]["via"] != "oficial"
    assert tjmt["protocolar"]["falta"] == "parear"


def test_rota_de_outro_escritorio_nao_aparece(client, db_session, escritorio_com_rotas):
    outro = models.Escritorio(nome="Outro Escritório")
    db_session.add(outro)
    db_session.flush()
    processo = models.Processo(
        escritorio_id=outro.id, numero="00000040020248260100", tribunal="TJSP"
    )
    db_session.add(processo)
    db_session.flush()
    db_session.add(
        models.ProcessoInstancia(
            processo_id=processo.id,
            escritorio_id=outro.id,
            sistema="ESAJ",
            tribunal="TJSP",
            grau="1",
        )
    )
    db_session.commit()

    rotas = client.get("/tribunais/acesso").json()

    assert all(r["tribunal"] != "TJSP" for r in rotas)


def test_rota_pronta_quando_agente_online_e_sessao_conectada(
    client, db_session, escritorio_com_rotas
):
    esc, usuario = escritorio_com_rotas
    db_session.add(
        models.AgentInstallation(
            escritorio_id=esc.id,
            usuario_id=usuario.id,
            nome="Notebook",
            token_hash="hash-painel",
            ativo=True,
            last_seen_at=datetime.now(timezone.utc),
        )
    )
    db_session.add(
        models.CourtSessionState(
            escritorio_id=esc.id,
            sistema="EPROC",
            tribunal="TJTO",
            grau="1",
            status="conectado",
            last_confirmed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    rotas = client.get("/tribunais/acesso").json()
    tjto = next(r for r in rotas if r["tribunal"] == "TJTO")

    assert tjto["ler_autos"] == {"disponivel": True, "via": "computador", "falta": None}
    assert tjto["protocolar"] == {"disponivel": True, "via": "computador", "falta": None}
