"""Entrega do aviso de prazo fora do app.

Duas propriedades importam mais que o texto do e-mail:

1. **Não repetir.** O advogado recebe um aviso por prazo *por nível* — D-3, D-1,
   D-0, vencido. Repetir a cada execução do cron treina o usuário a ignorar.
2. **Não perder.** Se o envio falhar, nada é marcado como enviado; a próxima
   execução tenta de novo. Marcar antes de enviar transformaria uma falha de
   SMTP em prazo perdido — exatamente o que o produto promete evitar.
"""

from datetime import date

import pytest

from app.alertas.notificacao import notificar_prazos
from app.sor import models

HOJE = date(2026, 7, 30)


class SenderFalso:
    """Sender de verdade, em memória — não é mock: registra o que enviaria."""

    def __init__(self, *, falha: bool = False):
        self.enviados: list[dict] = []
        self.falha = falha

    def enviar(self, *, destinos: list[str], assunto: str, corpo: str) -> None:
        if self.falha:
            raise RuntimeError("smtp fora do ar")
        self.enviados.append({"destinos": destinos, "assunto": assunto, "corpo": corpo})


def _escritorio(db_session, nome, *, email: str | None = "adv@example.com"):
    """``email=None`` cria escritório **sem usuário** — o único jeito real de
    ficar sem destino, já que ``usuario.email`` é NOT NULL."""
    esc = models.Escritorio(nome=nome)
    db_session.add(esc)
    db_session.flush()
    if email is not None:
        db_session.add(
            models.Usuario(
                escritorio_id=esc.id,
                nome=f"Adv {nome}",
                email=email,
                supabase_user_id=f"sub-{nome}",
            )
        )
        db_session.flush()
    return esc


def _prazo(db_session, esc, *, data_fatal: date, descricao="Contestação"):
    prazo = models.Prazo(
        escritorio_id=esc.id,
        processo_id=None,
        intimacao_id=None,
        descricao=descricao,
        data_inicio=date(2026, 7, 1),
        dias=15,
        dias_uteis=True,
        data_fatal=data_fatal,
        cumprido=False,
    )
    db_session.add(prazo)
    db_session.flush()
    return prazo


@pytest.fixture
def esc(db_session):
    return _escritorio(db_session, "Piloto")


def test_console_does_not_consume_delivery_deduplication(db_session, esc):
    from app.alertas.senders import ConsoleSender

    _prazo(db_session, esc, data_fatal=HOJE)
    assert notificar_prazos(db_session, sender=ConsoleSender(), hoje=HOJE) == []
    assert db_session.query(models.NotificacaoPrazo).count() == 0
    assert len(notificar_prazos(db_session, sender=SenderFalso(), hoje=HOJE)) == 1


def test_envia_um_aviso_com_os_prazos_do_escritorio(db_session, esc):
    _prazo(db_session, esc, data_fatal=HOJE, descricao="Contestação")
    sender = SenderFalso()

    enviadas = notificar_prazos(db_session, sender=sender, hoje=HOJE)

    assert len(sender.enviados) == 1
    assert sender.enviados[0]["destinos"] == ["adv@example.com"]
    assert "Contestação" in sender.enviados[0]["corpo"]
    assert len(enviadas) == 1


def test_nao_repete_o_mesmo_prazo_no_mesmo_nivel(db_session, esc):
    _prazo(db_session, esc, data_fatal=HOJE)
    sender = SenderFalso()

    notificar_prazos(db_session, sender=sender, hoje=HOJE)
    notificar_prazos(db_session, sender=sender, hoje=HOJE)

    assert len(sender.enviados) == 1


def test_avisa_de_novo_quando_o_prazo_muda_de_nivel(db_session, esc):
    """D-3 e D-1 são avisos diferentes sobre o mesmo prazo — os dois vão."""
    _prazo(db_session, esc, data_fatal=date(2026, 8, 2))
    sender = SenderFalso()

    notificar_prazos(db_session, sender=sender, hoje=HOJE)  # D-3
    notificar_prazos(db_session, sender=sender, hoje=date(2026, 8, 1))  # D-1

    assert len(sender.enviados) == 2


def test_falha_no_envio_nao_marca_como_enviado(db_session, esc):
    _prazo(db_session, esc, data_fatal=HOJE)

    enviadas = notificar_prazos(db_session, sender=SenderFalso(falha=True), hoje=HOJE)
    assert enviadas == []

    sender_ok = SenderFalso()
    notificar_prazos(db_session, sender=sender_ok, hoje=HOJE)
    assert len(sender_ok.enviados) == 1


def test_escritorio_sem_destino_nao_e_marcado_como_avisado(db_session):
    """Sem para quem mandar, nada é gravado — o aviso sai quando houver usuário."""
    sem_email = _escritorio(db_session, "SemEmail", email=None)
    _prazo(db_session, sem_email, data_fatal=HOJE)
    sender = SenderFalso()

    assert notificar_prazos(db_session, sender=sender, hoje=HOJE) == []
    assert sender.enviados == []
    assert db_session.query(models.NotificacaoPrazo).count() == 0


def test_cada_escritorio_recebe_so_os_proprios_prazos(db_session, esc):
    outro = _escritorio(db_session, "Outro", email="outro@example.com")
    _prazo(db_session, esc, data_fatal=HOJE, descricao="Do piloto")
    _prazo(db_session, outro, data_fatal=HOJE, descricao="Do outro")
    sender = SenderFalso()

    notificar_prazos(db_session, sender=sender, hoje=HOJE)

    assert len(sender.enviados) == 2
    por_destino = {e["destinos"][0]: e["corpo"] for e in sender.enviados}
    assert "Do piloto" in por_destino["adv@example.com"]
    assert "Do outro" not in por_destino["adv@example.com"]


def test_prazo_fora_da_janela_nao_gera_aviso(db_session, esc):
    _prazo(db_session, esc, data_fatal=date(2026, 8, 15))
    sender = SenderFalso()

    notificar_prazos(db_session, sender=sender, hoje=HOJE)

    assert sender.enviados == []


def test_registra_auditoria_do_aviso(db_session, esc):
    _prazo(db_session, esc, data_fatal=HOJE)

    notificar_prazos(db_session, sender=SenderFalso(), hoje=HOJE)

    log = (
        db_session.query(models.AuditLog)
        .filter(models.AuditLog.acao == "alerta_prazo_enviado")
        .one()
    )
    assert log.escritorio_id == esc.id
    assert log.detalhe["niveis"] == {"d0": 1}
