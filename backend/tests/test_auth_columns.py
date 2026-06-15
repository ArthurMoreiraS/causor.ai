"""As novas colunas de auth/tenant existem e são gravaveis (SQLite-portable)."""

from datetime import date

from app.sor import models


def test_usuario_tem_supabase_user_id(db_session):
    esc = models.Escritorio(nome="E")
    db_session.add(esc)
    db_session.flush()
    u = models.Usuario(
        escritorio_id=esc.id, nome="Adv", email="a@b.com",
        supabase_user_id="11111111-1111-1111-1111-111111111111",
    )
    db_session.add(u)
    db_session.flush()
    assert u.supabase_user_id == "11111111-1111-1111-1111-111111111111"


def test_prazo_peticao_intimacao_tem_escritorio_id(db_session):
    esc = models.Escritorio(nome="E")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="1")
    db_session.add(proc)
    db_session.flush()
    intim = models.Intimacao(
        escritorio_id=esc.id, processo_id=proc.id, fonte="DJEN", fonte_id="x",
    )
    prazo = models.Prazo(
        escritorio_id=esc.id, processo_id=proc.id, data_inicio=date(2024, 1, 1),
        dias=15, dias_uteis=True, data_fatal=date(2024, 1, 22),
    )
    pet = models.Peticao(escritorio_id=esc.id, processo_id=proc.id, status="rascunho")
    db_session.add_all([intim, prazo, pet])
    db_session.flush()
    assert intim.escritorio_id == esc.id
    assert prazo.escritorio_id == esc.id
    assert pet.escritorio_id == esc.id
