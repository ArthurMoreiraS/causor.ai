"""Driver determinístico de homologação (Causor Sandbox).

NÃO é protocolo real. Renderiza os passos do agente e um comprovante rotulado
com o sistema resolvido, para a demo mostrar o fluxo autônomo ponta a ponta sem
risco de um portal real quebrar ao vivo (captcha/layout/rede). O número de
protocolo é determinístico (derivado de sistema+processo), então a mesma minuta
produz sempre o mesmo comprovante.
"""

from __future__ import annotations

from hashlib import sha256

from app.connectors.pje.connector import PjeFilingCheckpoint, PjeFilingPackage

# Passos do agente, na ordem em que aparecem como evidência.
_STATES = [
    "session_ok",
    "processo_localizado",
    "peticionamento_aberto",
    "minuta_anexada",
    "assinado",
    "protocolado",
]


class SandboxDriver:
    """Implementa a interface FilingDriver de forma determinística."""

    def __init__(self, sistema: str) -> None:
        self.sistema = sistema

    def prepare_filing(
        self, package: PjeFilingPackage, *, submit: bool = False
    ) -> PjeFilingCheckpoint:
        digest = sha256(
            f"{self.sistema}:{package.numero_processo}".encode("utf-8")
        ).hexdigest()[:8].upper()
        protocolo = f"SANDBOX-{self.sistema.replace('-', '')}-{digest}"

        base = {
            "sandbox": True,
            "sistema": self.sistema,
            "processo": package.numero_processo,
            "tribunal": package.tribunal,
            "orgao_julgador": package.orgao_julgador,
            "tipo_peticao": package.tipo_peticao,
            "credencial_id": package.credencial_id,
        }

        if not submit:
            states = _STATES[:-2]  # para antes de assinar/protocolar (gate humano)
            return PjeFilingCheckpoint(
                checkpoint="ready_to_sign",
                modo="causor_sandbox",
                irreversible=False,
                evidence={
                    **base,
                    "states": states,
                    "screenshots": [f"sandbox://{self.sistema}/{s}.png" for s in states],
                },
            )

        return PjeFilingCheckpoint(
            checkpoint="protocolado",
            modo="causor_sandbox",
            irreversible=True,
            evidence={
                **base,
                "states": list(_STATES),
                "screenshots": [f"sandbox://{self.sistema}/{s}.png" for s in _STATES],
                "protocolo": protocolo,
                "comprovante_url": f"sandbox://comprovante/{protocolo}.pdf",
            },
        )
