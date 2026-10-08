"""Convite de membro do escritório pelo Supabase Auth.

A chave service-role controla todo o Auth do projeto. Fica só no backend e é
lida do ambiente na hora do envio, como a senha do SMTP: ``settings`` acaba em
log e diagnóstico. Mensagens de erro carregam só o status HTTP, nunca a
resposta nem cabeçalhos.

Sem chave configurada o membro é criado mesmo assim e o convite fica
``manual``: o administrador convida pelo painel do Supabase e o primeiro login
liga a conta pelo e-mail (``jwt_auth.get_current_user``).
"""

from __future__ import annotations

import os
from typing import Literal, Protocol

import httpx

from app.auth.jwt_auth import _configured_issuer
from app.settings import settings

SERVICE_ROLE_ENV = "CAUSOR_SUPABASE_SERVICE_ROLE_KEY"

ResultadoConvite = Literal["enviado", "ja_cadastrado", "manual"]


class ConviteIndisponivel(Exception):
    """O Supabase não aceitou o convite; nada deve ser gravado."""


class Convidador(Protocol):
    def convidar(self, *, email: str, nome: str) -> ResultadoConvite: ...


class SupabaseConvidador:
    def __init__(self, *, auth_url: str, chave: str, redirect_to: str | None) -> None:
        self._auth_url = auth_url.rstrip("/")
        self._chave = chave
        self._redirect_to = redirect_to

    def _cabecalhos(self) -> dict[str, str]:
        # service_role clássica é um JWT e vai também como Bearer. A chave
        # secreta no formato novo (`sb_secret_...`) não é JWT: só em `apikey`.
        cabecalhos = {"apikey": self._chave}
        if self._chave.startswith("eyJ"):
            cabecalhos["Authorization"] = f"Bearer {self._chave}"
        return cabecalhos

    def convidar(self, *, email: str, nome: str) -> ResultadoConvite:
        try:
            resposta = httpx.post(
                f"{self._auth_url}/invite",
                params={"redirect_to": self._redirect_to} if self._redirect_to else None,
                json={"email": email, "data": {"nome": nome}},
                headers=self._cabecalhos(),
                timeout=15,
                trust_env=False,
            )
        except httpx.HTTPError as exc:
            raise ConviteIndisponivel("Supabase Auth indisponível") from exc
        if resposta.status_code in (200, 201):
            return "enviado"
        corpo = resposta.text.lower()
        if resposta.status_code == 422 and ("email_exists" in corpo or "already" in corpo):
            # Já tem conta no Auth (ex.: convidado antes): entra com a senha
            # que tem ou pelo "esqueci minha senha".
            return "ja_cadastrado"
        raise ConviteIndisponivel(f"Supabase Auth respondeu {resposta.status_code}")


def get_convidador() -> Convidador | None:
    """Dependência FastAPI; ``None`` quando o convite precisa ser manual."""
    chave = os.environ.get(SERVICE_ROLE_ENV, "").strip()
    auth_url = _configured_issuer()
    if not chave or not auth_url:
        return None
    app_url = settings.app_url.strip().rstrip("/")
    return SupabaseConvidador(
        auth_url=auth_url,
        chave=chave,
        redirect_to=f"{app_url}/set-password" if app_url else None,
    )
