"""Signature provider seam.

Single responsibility: translate a lawyer's signing provider into safe handoff
instructions for the ``manual_handoff`` flow. The lawyer signs OUTSIDE the
Causor; this module never receives or stores a PIN, password, certificate or
OTP. The ``request_signature`` hook is where a future cloud-certificate API
(BirdID/VIDaaS) plugs in without refactoring the connector.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MANUAL_HANDOFF = "manual_handoff"
_MANUAL_ACOES = ["abrir_pje", "ja_assinei", "cancelar"]
_MANUAL_INSTRUCOES = [
    "Abra o PJe/PJeOffice no seu ambiente.",
    "Assine a peticao com a sua credencial.",
    "Protocole no PJe.",
    "Volte e registre o numero do protocolo aqui.",
]


@dataclass(frozen=True)
class SignatureHandoff:
    """How a lawyer should sign for a given provider/mode. Carries no secret."""

    provedor: str
    modo: str
    mensagem: str
    instrucoes: list[str]
    acoes: list[str]


@dataclass(frozen=True)
class ProviderSpec:
    provedor: str
    label: str
    modos: tuple[str, ...]
    mensagem: str
    instrucoes: list[str] = field(default_factory=lambda: list(_MANUAL_INSTRUCOES))
    acoes: list[str] = field(default_factory=lambda: list(_MANUAL_ACOES))


_GENERIC = ProviderSpec(
    provedor="generico",
    label="Assinatura manual",
    modos=(MANUAL_HANDOFF,),
    mensagem=(
        "Assine e protocole no PJe/PJeOffice com a sua credencial e registre o "
        "numero do protocolo aqui."
    ),
)

PROVIDER_CATALOG: dict[str, ProviderSpec] = {
    "birdid": ProviderSpec(
        provedor="birdid",
        label="BirdID",
        modos=(MANUAL_HANDOFF, "api"),
        mensagem=(
            "Assinatura pendente via BirdID. Aprove no app BirdID, protocole no "
            "PJe e registre o numero do protocolo aqui."
        ),
    ),
    "vidaas": ProviderSpec(
        provedor="vidaas",
        label="VIDaaS",
        modos=(MANUAL_HANDOFF, "api"),
        mensagem=(
            "Assinatura pendente via VIDaaS. Aprove no app VIDaaS, protocole no "
            "PJe e registre o numero do protocolo aqui."
        ),
    ),
    "pjeoffice": ProviderSpec(
        provedor="pjeoffice",
        label="PJeOffice",
        modos=(MANUAL_HANDOFF,),
        mensagem=(
            "Assine e protocole no PJe usando o PJeOffice e registre o numero do "
            "protocolo aqui."
        ),
    ),
    "a3": ProviderSpec(
        provedor="a3",
        label="Token A3",
        modos=(MANUAL_HANDOFF,),
        mensagem=(
            "Assine com o seu token A3 no PJe/PJeOffice e registre o numero do "
            "protocolo aqui."
        ),
    ),
    "a1": ProviderSpec(
        provedor="a1",
        label="Certificado A1",
        modos=(MANUAL_HANDOFF, "api"),
        mensagem=(
            "Assine com o seu certificado A1 no PJe/PJeOffice e registre o numero "
            "do protocolo aqui."
        ),
    ),
}


class SignatureProvider:
    """Produce signing handoff for one provider/mode. Holds no secret."""

    def __init__(self, spec: ProviderSpec, modo: str = MANUAL_HANDOFF) -> None:
        self._spec = spec
        self._modo = modo

    def handoff(self, package=None) -> SignatureHandoff:
        if self._modo != MANUAL_HANDOFF:
            raise NotImplementedError(
                f"handoff so suporta manual_handoff; modo={self._modo!r}"
            )
        return SignatureHandoff(
            provedor=self._spec.provedor,
            modo=self._modo,
            mensagem=self._spec.mensagem,
            instrucoes=list(self._spec.instrucoes),
            acoes=list(self._spec.acoes),
        )

    def request_signature(self, package=None):
        """Hook for a future cloud-certificate API. Not implemented in the MVP."""
        raise NotImplementedError(
            "assinatura via API (cloud_certificate) ainda nao suportada"
        )


def get_signature_provider(
    provedor: str | None,
    modo: str = MANUAL_HANDOFF,
) -> SignatureProvider:
    """Resolve a provider name into a SignatureProvider; unknown -> generic."""
    key = (provedor or "").strip().lower()
    spec = PROVIDER_CATALOG.get(key, _GENERIC)
    return SignatureProvider(spec, modo=modo)
