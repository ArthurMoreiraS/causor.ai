"""Approved bytes and destination shared by export and simulator adapters."""
from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class ApprovedFile:
    name: str
    content: bytes
    sha256: str

    def verify(self):
        if sha256(self.content).hexdigest() != self.sha256:
            raise ValueError("Arquivo diverge da aprovação")


@dataclass(frozen=True)
class ApprovedPackage:
    id: int
    fingerprint: str
    destination: tuple[tuple[str, str | None], ...]
    files: tuple[ApprovedFile, ...]

    def verify(self, *, fingerprint: str, destination: dict):
        if fingerprint != self.fingerprint or destination != dict(self.destination):
            raise ValueError("Pacote ou destino diverge da aprovação")
        for item in self.files:
            item.verify()
