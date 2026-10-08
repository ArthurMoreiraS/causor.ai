"""Equipe do escritório: papéis, convite, desativação e avisos por responsável.

O cliente de teste age como o primeiro usuário do primeiro escritório (o da
fixture ``seeded``, administrador). Para agir com outro papel, muda-se o papel
desse usuário no banco.
"""

import time
from datetime import date

import jwt
import pytest
from fastapi import HTTPException

from app.alertas.notificacao import notificar_prazos
from app.auth.convite import ConviteIndisponivel, get_convidador
from app.auth.jwt_auth import get_current_user
from app.sor import models


def _eu(db_session, seeded) -> models.Usuario:
    return (
        db_session.query(models.Usuario)
        .filter_by(escritorio_id=seeded.escritorio_id)
        .order_by(models.Usuario.id)
        .first()
    )


def _membro(db_session, escritorio_id, nome, papel="advogado", *, ativo=True, sub=None):
    usuario = models.Usuario(
        escritorio_id=escritorio_id, nome=nome, email=f"{nome.lower()}@example.com",
        papel=papel, ativo=ativo, supabase_user_id=sub,
    )
    db_session.add(usuario)
    db_session.flush()
    return usuario


def _como(db_session, seeded, papel):
    eu = _eu(db_session, seeded)
    eu.papel = papel
    db_session.flush()
    return eu


class ConvidadorFalso:
    def __init__(self, resultado="enviado", *, falha=False):
        self.resultado, self.falha, self.convites = resultado, falha, []

    def convidar(self, *, email, nome):
        if self.falha:
            raise ConviteIndisponivel("fora do ar")
        self.convites.append(email)
        return self.resultado


@pytest.fixture
def convidador(client):
    falso = ConvidadorFalso()
    client.app.dependency_overrides[get_convidador] = lambda: falso
    return falso


# --- Permissões por papel ---------------------------------------------------


def test_me_expoe_papel_e_permissoes_do_assistente(client, db_session, seeded):
    _como(db_session, seeded, "assistente")

    corpo = client.get("/me").json()

    assert corpo["papel"] == "assistente"
    assert corpo["permissoes"] == []


def test_assistente_nao_aprova_minuta(client, db_session, seeded):
    _como(db_session, seeded, "assistente")
    peticao = models.Peticao(
        processo_id=seeded.id, escritorio_id=seeded.escritorio_id, tipo="contestacao",
        conteudo="texto", status="em_revisao",
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.post(f"/peticoes/{peticao.id}/approve")

    assert resp.status_code == 403
    assert db_session.get(models.Peticao, peticao.id).status == "em_revisao"


def test_assistente_nao_altera_nem_cumpre_prazo(client, db_session, seeded):
    _como(db_session, seeded, "assistente")
    prazo = db_session.query(models.Prazo).filter_by(escritorio_id=seeded.escritorio_id).first()

    assert client.patch(f"/prazos/{prazo.id}", json={"dias": 10}).status_code == 403
    assert client.post(f"/prazos/{prazo.id}/cumprir").status_code == 403


def test_advogado_altera_prazo_mas_nao_configura_escritorio(client, db_session, seeded):
    _como(db_session, seeded, "advogado")
    prazo = db_session.query(models.Prazo).filter_by(
        escritorio_id=seeded.escritorio_id, cumprido=False).first()

    assert client.post(f"/prazos/{prazo.id}/cumprir").status_code == 200
    assert client.post("/capturas/oab", json={"oab": "123", "uf": "SP"}).status_code == 403
    assert client.patch("/settings/profile", json={"nome_escritorio": "Outro nome"}).status_code == 403


def test_qualquer_membro_altera_os_proprios_dados(client, db_session, seeded):
    _como(db_session, seeded, "assistente")

    resp = client.patch("/settings/profile", json={"nome_usuario": "Novo Nome"})

    assert resp.status_code == 200
    assert resp.json()["usuario"]["nome"] == "Novo Nome"


def test_assistente_nao_gerencia_equipe(client, db_session, seeded, convidador):
    _como(db_session, seeded, "assistente")
    outro = _membro(db_session, seeded.escritorio_id, "Bia")

    assert client.post("/equipe/convites", json={
        "nome": "Novo", "email": "novo@example.com", "papel": "advogado"}).status_code == 403
    assert client.patch(f"/equipe/{outro.id}", json={"ativo": False}).status_code == 403
    assert convidador.convites == []


# --- Convite ----------------------------------------------------------------


def test_admin_convida_membro_e_audita(client, db_session, seeded, convidador):
    resp = client.post("/equipe/convites", json={
        "nome": "Bia Souza", "email": "  Bia@Example.com ", "papel": "assistente"})

    assert resp.status_code == 201, resp.text
    corpo = resp.json()
    assert corpo["convite"] == "enviado"
    assert corpo["membro"]["email"] == "bia@example.com"
    assert corpo["membro"]["papel"] == "assistente"
    assert corpo["membro"]["convite_pendente"] is True
    assert convidador.convites == ["bia@example.com"]
    log = db_session.query(models.AuditLog).filter_by(acao="membro_convidado").one()
    assert log.entidade_id == corpo["membro"]["id"]
    assert log.detalhe["papel"] == "assistente"


def test_convite_sem_chave_do_supabase_fica_manual(client, db_session, seeded):
    client.app.dependency_overrides[get_convidador] = lambda: None

    resp = client.post("/equipe/convites", json={
        "nome": "Caio", "email": "caio@example.com", "papel": "advogado"})

    assert resp.status_code == 201
    assert resp.json()["convite"] == "manual"
    assert db_session.query(models.Usuario).filter_by(email="caio@example.com").one()


def test_falha_no_convite_nao_cria_membro(client, db_session, seeded):
    client.app.dependency_overrides[get_convidador] = lambda: ConvidadorFalso(falha=True)

    resp = client.post("/equipe/convites", json={
        "nome": "Dani", "email": "dani@example.com", "papel": "advogado"})

    assert resp.status_code == 502
    assert db_session.query(models.Usuario).filter_by(email="dani@example.com").count() == 0


def test_convite_de_email_existente_e_recusado(client, db_session, seeded, convidador):
    _membro(db_session, seeded.escritorio_id, "Bia")
    outro_escritorio = models.Escritorio(nome="Outro")
    db_session.add(outro_escritorio)
    db_session.flush()
    _membro(db_session, outro_escritorio.id, "Edu")

    mesmo = client.post("/equipe/convites", json={
        "nome": "Bia", "email": "BIA@example.com", "papel": "advogado"})
    alheio = client.post("/equipe/convites", json={
        "nome": "Edu", "email": "edu@example.com", "papel": "advogado"})

    assert mesmo.status_code == 409
    assert "já é membro" in mesmo.json()["detail"]
    assert alheio.status_code == 409
    assert convidador.convites == []


def test_reenvio_so_para_quem_ainda_nao_entrou(client, db_session, seeded, convidador):
    pendente = _membro(db_session, seeded.escritorio_id, "Bia")
    ja_entrou = _membro(db_session, seeded.escritorio_id, "Caio", sub="sub-caio")

    assert client.post(f"/equipe/{pendente.id}/convite").status_code == 200
    assert client.post(f"/equipe/{ja_entrou.id}/convite").status_code == 409
    assert convidador.convites == ["bia@example.com"]


def test_usuarios_lista_papel_status_e_convite(client, db_session, seeded):
    _membro(db_session, seeded.escritorio_id, "Bia", "assistente", ativo=False)

    membros = {m["nome"]: m for m in client.get("/usuarios").json()}

    assert membros["Adv Seed"]["papel"] == "administrador"
    assert membros["Adv Seed"]["convite_pendente"] is False
    assert membros["Bia"] == {**membros["Bia"], "papel": "assistente", "ativo": False,
                              "convite_pendente": True}


# --- Papel e desativação ----------------------------------------------------


def test_admin_muda_papel_e_desativa_com_auditoria(client, db_session, seeded):
    bia = _membro(db_session, seeded.escritorio_id, "Bia", "assistente")

    assert client.patch(f"/equipe/{bia.id}", json={"papel": "advogado"}).json()["papel"] == "advogado"
    assert client.patch(f"/equipe/{bia.id}", json={"ativo": False}).json()["ativo"] is False

    acoes = [log.acao for log in db_session.query(models.AuditLog).filter_by(entidade_id=bia.id)]
    assert acoes == ["membro_papel_alterado", "membro_desativado"]


def test_ninguem_altera_o_proprio_papel(client, db_session, seeded):
    _membro(db_session, seeded.escritorio_id, "Outra Admin", "administrador")
    eu = _eu(db_session, seeded)

    assert client.patch(f"/equipe/{eu.id}", json={"papel": "advogado"}).status_code == 409
    assert client.patch(f"/equipe/{eu.id}", json={"ativo": False}).status_code == 409


def test_escritorio_nunca_fica_sem_administrador_ativo(db_session, seeded):
    """Quem age é sempre admin ativo, então a trava só dispara em corrida: duas
    admins se rebaixando ao mesmo tempo. A segunda requisição chega com a
    identidade resolvida antes de a primeira gravar."""
    from app.api import equipe_routes
    from app.auth.jwt_auth import CurrentUser

    eu = _eu(db_session, seeded)
    outra = _membro(db_session, seeded.escritorio_id, "Outra", "administrador")
    identidade_antiga = CurrentUser(usuario_id=outra.id, escritorio_id=seeded.escritorio_id,
                                    email=outra.email, papel="administrador")
    outra.papel = "advogado"  # a primeira requisição já rebaixou a outra admin
    db_session.flush()

    with pytest.raises(HTTPException) as erro:
        equipe_routes.alterar_membro(eu.id, equipe_routes.MembroPatch(papel="advogado"),
                                     session=db_session, current=identidade_antiga)

    assert erro.value.status_code == 409
    assert db_session.get(models.Usuario, eu.id).papel == "administrador"


def test_membro_desativado_perde_o_acesso(db_session, seeded, monkeypatch):
    from app.auth import jwt_auth

    monkeypatch.setattr(jwt_auth.settings, "supabase_jwt_secret", "segredo-de-teste-com-32-bytes-ok")
    bia = _membro(db_session, seeded.escritorio_id, "Bia", ativo=False, sub="sub-bia")
    token = jwt.encode({"sub": "sub-bia", "email": bia.email, "aud": "authenticated",
                        "exp": int(time.time()) + 600},
                       "segredo-de-teste-com-32-bytes-ok", algorithm="HS256")

    with pytest.raises(HTTPException) as erro:
        get_current_user(authorization=f"Bearer {token}", session=db_session)
    assert erro.value.status_code == 403


def test_membro_desativado_nao_pode_ser_responsavel(client, db_session, seeded):
    bia = _membro(db_session, seeded.escritorio_id, "Bia", ativo=False)
    caio = _membro(db_session, seeded.escritorio_id, "Caio")

    recusada = client.post("/tarefas", json={"titulo": "Ligar", "responsavel_id": bia.id})
    aceita = client.post("/tarefas", json={"titulo": "Ligar", "responsavel_id": caio.id})

    assert recusada.status_code == 422
    assert aceita.status_code == 201
    assert aceita.json()["responsavel_nome"] == "Caio"


def test_editar_tarefa_de_membro_desativado_sem_trocar_responsavel(client, db_session, seeded):
    caio = _membro(db_session, seeded.escritorio_id, "Caio")
    tarefa = client.post("/tarefas", json={"titulo": "Ligar", "responsavel_id": caio.id}).json()
    caio.ativo = False
    db_session.flush()

    resp = client.patch(f"/tarefas/{tarefa['id']}", json={
        "versao": tarefa["versao"], "titulo": "Ligar hoje", "responsavel_id": caio.id})

    assert resp.status_code == 200
    log = db_session.query(models.AuditLog).filter_by(acao="tarefa_atualizada").one()
    assert log.detalhe["campos"] == ["titulo"]


def test_troca_de_responsavel_fica_na_auditoria(client, db_session, seeded):
    caio = _membro(db_session, seeded.escritorio_id, "Caio")
    tarefa = client.post("/tarefas", json={"titulo": "Ligar"}).json()

    client.patch(f"/tarefas/{tarefa['id']}", json={"versao": tarefa["versao"], "responsavel_id": caio.id})

    log = db_session.query(models.AuditLog).filter_by(acao="tarefa_atualizada").one()
    assert log.detalhe["responsavel"] == {"de": None, "para": caio.id}


# --- Avisos de prazo por responsável ----------------------------------------

HOJE = date(2026, 7, 30)


class SenderFalso:
    def __init__(self, *, falha_para: set[str] = frozenset()):
        self.enviados: list[dict] = []
        self.falha_para = falha_para

    def enviar(self, *, destinos, assunto, corpo):
        if set(destinos) & self.falha_para:
            raise RuntimeError("smtp recusou")
        self.enviados.append({"destinos": destinos, "corpo": corpo})


@pytest.fixture
def escritorio_com_equipe(db_session):
    esc = models.Escritorio(nome="Equipe")
    db_session.add(esc)
    db_session.flush()
    membros = {
        "socia": _membro(db_session, esc.id, "Socia", "administrador"),
        "adv": _membro(db_session, esc.id, "Adv", "advogado"),
        "estag": _membro(db_session, esc.id, "Estag", "assistente"),
        "saiu": _membro(db_session, esc.id, "Saiu", "advogado", ativo=False),
    }
    return esc, membros


def _prazo(db_session, esc, descricao):
    prazo = models.Prazo(
        escritorio_id=esc.id, descricao=descricao, data_inicio=date(2026, 7, 1), dias=15,
        dias_uteis=True, data_fatal=HOJE, cumprido=False,
    )
    db_session.add(prazo)
    db_session.flush()
    return prazo


def _por_destino(sender):
    return {e["destinos"][0]: e["corpo"] for e in sender.enviados}


def test_prazo_com_responsavel_avisa_so_ele_e_os_admins(db_session, escritorio_com_equipe):
    esc, m = escritorio_com_equipe
    processo = models.Processo(escritorio_id=esc.id, numero="00000020020248260100")
    db_session.add(processo)
    db_session.flush()
    prazo = _prazo(db_session, esc, "Contestação")
    prazo.processo_id = processo.id
    db_session.add(models.TrabalhoJuridico(
        escritorio_id=esc.id, processo_id=processo.id, prazo_id=prazo.id,
        responsavel_id=m["adv"].id, providencia="Contestar"))
    db_session.flush()
    sender = SenderFalso()

    notificar_prazos(db_session, sender=sender, hoje=HOJE)

    assert set(_por_destino(sender)) == {"socia@example.com", "adv@example.com"}
    assert all(len(e["destinos"]) == 1 for e in sender.enviados)


def test_prazo_sem_responsavel_avisa_todos_os_ativos(db_session, escritorio_com_equipe):
    esc, _ = escritorio_com_equipe
    _prazo(db_session, esc, "Réplica")
    sender = SenderFalso()

    notificar_prazos(db_session, sender=sender, hoje=HOJE)

    assert set(_por_destino(sender)) == {"socia@example.com", "adv@example.com", "estag@example.com"}


def test_tarefa_aberta_da_intimacao_define_o_responsavel(db_session, escritorio_com_equipe):
    esc, m = escritorio_com_equipe
    intimacao = models.Intimacao(escritorio_id=esc.id, fonte="DJEN", fonte_id="x1", teor="t")
    db_session.add(intimacao)
    db_session.flush()
    prazo = _prazo(db_session, esc, "Manifestação")
    prazo.intimacao_id = intimacao.id
    db_session.add_all([
        models.Tarefa(escritorio_id=esc.id, titulo="Separar docs", intimacao_id=intimacao.id,
                      responsavel_id=m["estag"].id),
        models.Tarefa(escritorio_id=esc.id, titulo="Antiga", intimacao_id=intimacao.id,
                      responsavel_id=m["adv"].id, status="concluida"),
    ])
    db_session.flush()
    sender = SenderFalso()

    notificar_prazos(db_session, sender=sender, hoje=HOJE)

    assert set(_por_destino(sender)) == {"socia@example.com", "estag@example.com"}


def test_responsavel_desativado_cai_para_o_escritorio(db_session, escritorio_com_equipe):
    esc, m = escritorio_com_equipe
    processo = models.Processo(escritorio_id=esc.id, numero="00000030020248260100")
    db_session.add(processo)
    db_session.flush()
    prazo = _prazo(db_session, esc, "Recurso")
    db_session.add(models.TrabalhoJuridico(
        escritorio_id=esc.id, processo_id=processo.id, prazo_id=prazo.id,
        responsavel_id=m["saiu"].id, providencia="Recorrer"))
    db_session.flush()
    sender = SenderFalso()

    notificar_prazos(db_session, sender=sender, hoje=HOJE)

    assert "saiu@example.com" not in _por_destino(sender)
    assert set(_por_destino(sender)) == {"socia@example.com", "adv@example.com", "estag@example.com"}


def test_cada_pessoa_recebe_um_email_com_os_seus_prazos(db_session, escritorio_com_equipe):
    esc, m = escritorio_com_equipe
    processo = models.Processo(escritorio_id=esc.id, numero="00000040020248260100")
    db_session.add(processo)
    db_session.flush()
    do_adv = _prazo(db_session, esc, "Prazo do advogado")
    _prazo(db_session, esc, "Prazo de todos")
    db_session.add(models.TrabalhoJuridico(
        escritorio_id=esc.id, processo_id=processo.id, prazo_id=do_adv.id,
        responsavel_id=m["adv"].id, providencia="Peticionar"))
    db_session.flush()
    sender = SenderFalso()

    notificar_prazos(db_session, sender=sender, hoje=HOJE)

    corpos = _por_destino(sender)
    assert len(sender.enviados) == 3
    assert "Prazo do advogado" in corpos["adv@example.com"]
    assert "Prazo do advogado" not in corpos["estag@example.com"]
    assert "Prazo de todos" in corpos["estag@example.com"]


def test_falha_para_um_destinatario_nao_marca_o_prazo(db_session, escritorio_com_equipe):
    esc, _ = escritorio_com_equipe
    _prazo(db_session, esc, "Contrarrazões")

    marcadas = notificar_prazos(
        db_session, sender=SenderFalso(falha_para={"estag@example.com"}), hoje=HOJE)
    assert marcadas == []

    sender = SenderFalso()
    assert len(notificar_prazos(db_session, sender=sender, hoje=HOJE)) == 1
    assert "estag@example.com" in _por_destino(sender)


# --- Cliente do convite (Supabase Auth, sem rede) ---------------------------


class _Resposta:
    def __init__(self, status_code, text=""):
        self.status_code, self.text = status_code, text


@pytest.mark.parametrize(("status", "texto", "esperado"), [
    (200, "{}", "enviado"),
    (422, '{"error_code":"email_exists"}', "ja_cadastrado"),
])
def test_supabase_convidador_interpreta_resposta(monkeypatch, status, texto, esperado):
    from app.auth import convite

    chamadas = []
    monkeypatch.setattr(convite.httpx, "post",
                        lambda url, **kw: chamadas.append((url, kw)) or _Resposta(status, texto))
    cliente = convite.SupabaseConvidador(
        auth_url="https://ref.supabase.co/auth/v1", chave="chave-secreta",
        redirect_to="https://app.example.com/set-password")

    assert cliente.convidar(email="bia@example.com", nome="Bia") == esperado
    url, kw = chamadas[0]
    assert url == "https://ref.supabase.co/auth/v1/invite"
    assert kw["params"] == {"redirect_to": "https://app.example.com/set-password"}


def test_erro_do_supabase_nao_vaza_a_chave(monkeypatch):
    from app.auth import convite

    monkeypatch.setattr(convite.httpx, "post", lambda url, **kw: _Resposta(500, "chave-secreta"))
    cliente = convite.SupabaseConvidador(
        auth_url="https://ref.supabase.co/auth/v1", chave="chave-secreta", redirect_to=None)

    with pytest.raises(ConviteIndisponivel) as erro:
        cliente.convidar(email="bia@example.com", nome="Bia")
    assert "chave-secreta" not in str(erro.value)


def test_sem_chave_de_servico_o_convite_e_manual(monkeypatch):
    from app.auth import convite

    monkeypatch.delenv(convite.SERVICE_ROLE_ENV, raising=False)
    monkeypatch.setattr(convite.settings, "supabase_url", "https://ref.supabase.co")

    assert convite.get_convidador() is None

    monkeypatch.setenv(convite.SERVICE_ROLE_ENV, "chave")
    assert isinstance(convite.get_convidador(), convite.SupabaseConvidador)


@pytest.mark.parametrize(("chave", "com_bearer"), [("eyJhbGciOi.fake.jwt", True), ("sb_secret_abc", False)])
def test_formato_da_chave_define_os_cabecalhos(monkeypatch, chave, com_bearer):
    from app.auth import convite

    chamadas = []
    monkeypatch.setattr(convite.httpx, "post",
                        lambda url, **kw: chamadas.append(kw["headers"]) or _Resposta(200, "{}"))
    convite.SupabaseConvidador(auth_url="https://ref.supabase.co/auth/v1", chave=chave,
                               redirect_to=None).convidar(email="bia@example.com", nome="Bia")

    assert chamadas[0]["apikey"] == chave
    assert ("Authorization" in chamadas[0]) is com_bearer
