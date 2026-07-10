"""Loop de execução do agente: claim → dispatch → heartbeat → complete/fail.

Handlers por ``tipo`` de comando são registrados pelos Planos 2/3; um tipo
sem handler falha com ``unsupported_command`` (nunca sucesso presumido).
"""

from __future__ import annotations

from collections.abc import Callable
import threading
import time

from app.local_agent.client import AgentApiClient

HEARTBEAT_SECONDS = 20.0

CommandHandler = Callable[[dict], dict]


class AgentWorker:
    def __init__(
        self,
        client: AgentApiClient,
        *,
        handlers: dict[str, CommandHandler] | None = None,
    ):
        self._client = client
        self._handlers: dict[str, CommandHandler] = dict(handlers or {})

    def register_handler(self, tipo: str, handler: CommandHandler) -> None:
        self._handlers[tipo] = handler

    def run_once(self) -> bool:
        """Reivindica e executa um comando. Retorna False se a fila está vazia."""
        command = self._client.claim()
        if not command:
            return False
        command_id = command["id"]
        handler = self._handlers.get(command["tipo"])
        if handler is None:
            self._client.fail(
                command_id,
                "unsupported_command",
                f"tipo sem handler neste agente: {command['tipo']}",
            )
            return True

        stop_heartbeat = threading.Event()

        def _heartbeat_loop() -> None:
            while not stop_heartbeat.wait(HEARTBEAT_SECONDS):
                try:
                    self._client.heartbeat(command_id)
                except Exception:  # noqa: BLE001 - heartbeat é best-effort
                    return

        beat = threading.Thread(target=_heartbeat_loop, daemon=True)
        beat.start()
        try:
            resultado = handler(command["payload"])
        except Exception as exc:  # noqa: BLE001 - falha vira comando failed
            stop_heartbeat.set()
            beat.join(timeout=1.0)
            self._client.fail(command_id, "handler_error", str(exc)[:2000])
            return True
        stop_heartbeat.set()
        beat.join(timeout=1.0)
        self._client.complete(command_id, resultado)
        return True

    def run_forever(self, *, idle_seconds: float = 5.0) -> None:
        while True:
            worked = self.run_once()
            if not worked:
                time.sleep(idle_seconds)
