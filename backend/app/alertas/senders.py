"""Canais de saída do aviso de prazo.

Começa por **e-mail (SMTP)** de propósito: funciona hoje com qualquer provedor,
não exige aprovação de ninguém e não prende o produto a um fornecedor. WhatsApp
depende da API de negócios da Meta — aprovação e custo — e entra como um segundo
``AlertSender`` quando o piloto pedir; nada além deste arquivo muda.

A senha do SMTP é lida do ambiente **na hora do envio**, nunca de ``Settings``:
o objeto de settings acaba em log e diagnóstico, e segredo não entra lá (mesma
regra do ``ANTHROPIC_API_KEY``).
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from app.settings import settings

logger = logging.getLogger(__name__)

SMTP_PASSWORD_ENV = "CAUSOR_SMTP_PASSWORD"


class ConsoleSender:
    """Registra o aviso no log. É o default enquanto não houver SMTP.

    Deliberadamente não falha: um cron que quebra por falta de configuração de
    e-mail deixaria de rodar o resto do ciclo de alertas.
    """

    def enviar(self, *, destinos: list[str], assunto: str, corpo: str) -> bool:
        logger.info(
            "alerta de prazo (sem SMTP configurado) para %s | %s\n%s",
            ", ".join(destinos),
            assunto,
            corpo,
        )
        return False  # simulação não equivale a entrega


class SmtpSender:
    def __init__(self, *, host: str, port: int, usuario: str, remetente: str):
        self.host = host
        self.port = port
        self.usuario = usuario
        self.remetente = remetente

    def enviar(self, *, destinos: list[str], assunto: str, corpo: str) -> None:
        mensagem = EmailMessage()
        mensagem["From"] = self.remetente
        mensagem["To"] = ", ".join(destinos)
        mensagem["Subject"] = assunto
        mensagem.set_content(corpo)

        senha = os.environ.get(SMTP_PASSWORD_ENV, "")
        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.starttls()
            if self.usuario and senha:
                smtp.login(self.usuario, senha)
            refused = smtp.send_message(mensagem)
            if refused:
                raise RuntimeError("smtp_destinatarios_recusados")


def build_sender():
    """SMTP quando configurado; console caso contrário."""
    if not settings.smtp_host:
        return ConsoleSender()
    return SmtpSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        usuario=settings.smtp_user,
        remetente=settings.smtp_from or settings.smtp_user,
    )
