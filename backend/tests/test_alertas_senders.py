"""Escolha do canal de envio, e a regra de que segredo não vira config.

A senha do SMTP é lida do ambiente na hora do envio — nunca fica em
``Settings``, que é serializado em log/diagnóstico. Mesmo motivo pelo qual o
``ANTHROPIC_API_KEY`` é lido direto do ambiente.
"""

import logging

from app.alertas.senders import ConsoleSender, SmtpSender, build_sender


def test_sem_smtp_configurado_cai_no_console(monkeypatch):
    monkeypatch.setattr("app.alertas.senders.settings.smtp_host", "")

    assert isinstance(build_sender(), ConsoleSender)


def test_com_smtp_configurado_usa_smtp(monkeypatch):
    monkeypatch.setattr("app.alertas.senders.settings.smtp_host", "smtp.exemplo.com")

    assert isinstance(build_sender(), SmtpSender)


def test_console_registra_o_aviso_sem_derrubar_o_cron(caplog):
    sender = ConsoleSender()

    with caplog.at_level(logging.INFO):
        sender.enviar(destinos=["adv@example.com"], assunto="Assunto", corpo="Corpo")

    assert "adv@example.com" in caplog.text


def test_a_senha_do_smtp_nunca_aparece_em_settings(monkeypatch):
    monkeypatch.setenv("CAUSOR_SMTP_PASSWORD", "senha-secreta")
    from app.settings import Settings

    serializado = str(Settings().model_dump())

    assert "senha-secreta" not in serializado
    assert "smtp_password" not in serializado
