"""Cooperative stages: every external step checks ownership; submit is never retried."""
from dataclasses import dataclass
from threading import Event
from typing import Callable


class OwnershipLost(RuntimeError):
    pass


class ResultUncertain(RuntimeError):
    pass


@dataclass
class CommandGuard:
    client: object
    command_id: int
    lost: Event
    submitted: bool = False

    def check(self):
        if self.lost.is_set():
            raise OwnershipLost("Posse do comando perdida")
        try:
            self.client.heartbeat(self.command_id)
        except Exception as exc:
            self.lost.set()
            raise OwnershipLost("Não foi possível renovar a autorização") from exc

    def stage(self, name: str):
        self.check()
        self.client.checkpoint(self.command_id, name)

    def submit_once(self, operation: Callable[[], dict]) -> dict:
        if self.submitted:
            raise ResultUncertain("O envio já foi iniciado; consultar o resultado")
        self.stage("submitting")
        self.submitted = True
        try:
            return operation()
        except Exception as exc:
            raise ResultUncertain("Resultado do envio incerto; reconciliar antes de outra tentativa") from exc


@dataclass(frozen=True)
class GuardedHandler:
    run: Callable[[dict, CommandGuard], dict]

    def __call__(self, payload: dict, guard: CommandGuard) -> dict:
        return self.run(payload, guard)
