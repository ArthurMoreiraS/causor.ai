"""Assisted PJe filing connector.

This first implementation deliberately does not submit the irreversible act.
It prepares a filing package and returns a checkpoint where the lawyer must
sign/submit in PJe/PJeOffice, or a future cloud-certificate adapter can finish
the act behind the same gate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PjeFilingPackage:
    peticao_id: int
    processo_id: int
    numero_processo: str
    tribunal: str | None
    orgao_julgador: str | None
    tipo_peticao: str | None
    conteudo: str | None
    credencial_id: int | None = None


@dataclass(frozen=True)
class PjeFilingCheckpoint:
    checkpoint: str
    modo: str
    irreversible: bool
    next_action: str
    evidence: dict


class PjeAssistedConnector:
    """Prepare PJe filing up to the human signature/submit checkpoint."""

    def prepare_filing(
        self,
        package: PjeFilingPackage,
        *,
        signature_mode: str = "manual_pjeoffice",
    ) -> PjeFilingCheckpoint:
        if signature_mode not in {"manual_pjeoffice", "cloud_certificate"}:
            raise ValueError("modo de assinatura PJe desconhecido")

        next_action = (
            "Advogado assina e envia no PJe/PJeOffice; depois informe o numero do protocolo."
            if signature_mode == "manual_pjeoffice"
            else "Conectar provedor de certificado em nuvem antes do envio final."
        )
        return PjeFilingCheckpoint(
            checkpoint="ready_to_sign",
            modo="pje_assistido_playwright",
            irreversible=False,
            next_action=next_action,
            evidence={
                "processo": package.numero_processo,
                "tribunal": package.tribunal,
                "orgao_julgador": package.orgao_julgador,
                "tipo_peticao": package.tipo_peticao,
                "credencial_id": package.credencial_id,
                "assinatura": signature_mode,
            },
        )
