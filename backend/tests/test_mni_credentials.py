import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.connectors.mni import credentials as mni_credentials
from app.sor import models


def _usuario_id(db_session) -> int:
    return db_session.scalars(select(models.Usuario)).first().id


def test_mni_credencial_unique_por_escritorio_tribunal(db_session, seeded):
    db_session.add(models.MniCredencial(
        escritorio_id=seeded.escritorio_id, tribunal="TJMT",
        id_consultante="12345678900", referencia_vault="localdev://mni/x", ativo=True,
    ))
    db_session.flush()
    db_session.add(models.MniCredencial(
        escritorio_id=seeded.escritorio_id, tribunal="TJMT",
        id_consultante="98765432100", referencia_vault="localdev://mni/y", ativo=True,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_captura_autos_fonte_default_agente(db_session, seeded):
    instancia = models.ProcessoInstancia(
        processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
        sistema="PJe", tribunal="TJMG", grau="1", status="active",
    )
    db_session.add(instancia)
    db_session.flush()
    capture = models.CapturaAutos(
        escritorio_id=seeded.escritorio_id,
        processo_instancia_id=instancia.id,
        generation=99,
        status="queued",
    )
    db_session.add(capture)
    db_session.flush()
    assert capture.fonte == "agente"


def test_store_keeps_senha_no_vault_e_fora_do_sor(db_session, seeded):
    cred = mni_credentials.store_mni_credencial(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=_usuario_id(db_session),
        tribunal="TJMT",
        id_consultante="12345678900",
        senha="senha-mni-secreta",
    )
    assert cred.referencia_vault.startswith(("localdev://", "supabase-vault://"))
    assert "senha-mni-secreta" not in cred.referencia_vault
    assert mni_credentials.load_credencial_senha(db_session, cred) == "senha-mni-secreta"


def test_store_replaces_existing_row_for_same_tribunal(db_session, seeded):
    usuario_id = _usuario_id(db_session)
    first = mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=usuario_id,
        tribunal="TJMT", id_consultante="111", senha="a",
    )
    second = mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=usuario_id,
        tribunal="TJMT", id_consultante="222", senha="b",
    )
    assert second.id == first.id  # upsert na unique (escritorio, tribunal)
    assert second.id_consultante == "222"
    assert second.ativo is True


def test_find_active_ignores_deactivated(db_session, seeded):
    cred = mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id,
        usuario_id=_usuario_id(db_session),
        tribunal="TJPE", id_consultante="333", senha="c",
    )
    assert mni_credentials.find_active_credencial(
        db_session, escritorio_id=seeded.escritorio_id, tribunal="TJPE"
    ) is not None
    mni_credentials.deactivate_mni_credencial(
        db_session, credencial_id=cred.id, escritorio_id=seeded.escritorio_id
    )
    assert mni_credentials.find_active_credencial(
        db_session, escritorio_id=seeded.escritorio_id, tribunal="TJPE"
    ) is None


def test_api_cadastra_lista_mascarada_e_revoga(client, seeded):
    created = client.post("/mni/credenciais", json={
        "tribunal": "TJMT", "id_consultante": "12345678900", "senha": "s3nh4",
    })
    assert created.status_code == 200
    body = created.json()
    assert "senha" not in body
    assert body["id_consultante_mask"].startswith("123")
    assert body["id_consultante_mask"] != "12345678900"

    listed = client.get("/mni/credenciais")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    removed = client.delete(f"/mni/credenciais/{body['id']}")
    assert removed.status_code == 200
    assert client.get("/mni/credenciais").json()[0]["ativo"] is False


# --- Fail-closed: credencial so para tribunal que atende por MNI -------------
# Sem perfil na tabela, assistant.resolve_next_step nunca escolhe o canal
# oficial: a credencial vira peso morto e simula um acesso que nao existe.


def test_tribunal_sem_perfil_mni_e_recusado(db_session, seeded):
    """TJTO e eproc e nao tem endpoint MNI confirmado. Cadastrar credencial
    ali criava a ilusao de tribunal conectado enquanto tudo seguia pelo
    agente local."""
    with pytest.raises(mni_credentials.TribunalSemPerfilMni):
        mni_credentials.store_mni_credencial(
            db_session, escritorio_id=seeded.escritorio_id,
            usuario_id=_usuario_id(db_session),
            tribunal="TJTO", id_consultante="TO3981B", senha="x",
        )


def test_tribunal_removido_da_tabela_tambem_e_recusado(db_session, seeded):
    """TJMG saiu dos perfis na varredura de 22/07 (redireciona para pagina de
    erro). O cadastro precisa acompanhar a tabela, nao a memoria de quem usa."""
    with pytest.raises(mni_credentials.TribunalSemPerfilMni):
        mni_credentials.store_mni_credencial(
            db_session, escritorio_id=seeded.escritorio_id,
            usuario_id=_usuario_id(db_session),
            tribunal="TJMG", id_consultante="12345678900", senha="x",
        )


def test_tribunal_com_perfil_em_um_grau_so_e_aceito(db_session, seeded):
    """TJMT tem perfil so no 1o grau; a checagem olha os dois."""
    cred = mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id,
        usuario_id=_usuario_id(db_session),
        tribunal="TJMT", id_consultante="12345678900", senha="x",
    )
    assert cred.ativo is True


def test_sigla_normalizada_antes_da_checagem(db_session, seeded):
    cred = mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id,
        usuario_id=_usuario_id(db_session),
        tribunal="  tjpe  ", id_consultante="12345678900", senha="x",
    )
    assert cred.tribunal == "TJPE"


def test_api_recusa_tribunal_sem_mni_com_codigo_canonico(client, seeded):
    resposta = client.post("/mni/credenciais", json={
        "tribunal": "TJTO", "id_consultante": "TO3981B", "senha": "s3nh4",
    })
    assert resposta.status_code == 422
    assert resposta.json()["detail"]["code"] == "tribunal_sem_mni"
