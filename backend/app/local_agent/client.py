"""Cliente HTTP do protocolo do agente local.

Envia ``Authorization: Agent <token>`` em toda chamada. Nunca loga headers
nem corpos de resposta que possam conter token.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from app.storage.objects import UploadTicket


class AgentApiError(RuntimeError):
    pass


class AgentApiClient:
    def __init__(self, api_url: str, token: str, *, timeout: float = 60.0):
        self._client = httpx.Client(
            base_url=api_url.rstrip("/"),
            headers={"Authorization": f"Agent {token}"},
            timeout=timeout,
        )

    @staticmethod
    def pair(api_url: str, *, code: str, installation_name: str, version: str) -> dict:
        response = httpx.post(
            f"{api_url.rstrip('/')}/agent/pair",
            json={"code": code, "installation_name": installation_name, "version": version},
            timeout=30.0,
        )
        if response.status_code != 200:
            raise AgentApiError(f"pairing failed: HTTP {response.status_code}")
        return response.json()

    def claim(self) -> dict | None:
        response = self._client.post("/agent/commands/claim")
        self._raise_for_status(response, "claim")
        return response.json()

    def heartbeat(self, command_id: int) -> None:
        response = self._client.post(f"/agent/commands/{command_id}/heartbeat")
        self._raise_for_status(response, "heartbeat")

    def complete(self, command_id: int, resultado: dict) -> None:
        response = self._client.post(
            f"/agent/commands/{command_id}/complete", json={"resultado": resultado}
        )
        self._raise_for_status(response, "complete")

    def fail(self, command_id: int, erro_codigo: str, erro_detalhe: str | None = None) -> None:
        response = self._client.post(
            f"/agent/commands/{command_id}/fail",
            json={"erro_codigo": erro_codigo, "erro_detalhe": erro_detalhe},
        )
        self._raise_for_status(response, "fail")

    def upload(self, ticket: UploadTicket, data: bytes) -> None:
        """Sobe bytes pelo ticket: rota local autenticada ou PUT S3 pré-assinado."""
        if ticket.url.startswith("local-object://"):
            response = self._client.put(
                "/agent/uploads/local",
                params={"key": ticket.key},
                headers=ticket.headers,
                content=data,
            )
            self._raise_for_status(response, "upload")
            return
        response = httpx.request(
            ticket.method, ticket.url, headers=ticket.headers, content=data, timeout=300.0
        )
        if response.status_code >= 400:
            raise AgentApiError(f"upload failed: HTTP {response.status_code}")

    def download_to(self, url: str, destination: Path) -> None:
        with self._client.stream("GET", url) as response:
            self._raise_for_status(response, "download")
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _raise_for_status(response: httpx.Response, action: str) -> None:
        if response.status_code >= 400:
            raise AgentApiError(f"{action} failed: HTTP {response.status_code}")
