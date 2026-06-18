"""Assisted PJe filing connector.

This first implementation deliberately does not submit the irreversible act.
It prepares a filing package and returns a checkpoint where the lawyer must
sign/submit in PJe/PJeOffice, or a future cloud-certificate adapter can finish
the act behind the same gate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import re

from app.connectors.pje.pages.errors import (
    CaptchaDetectedError,
    LayoutDesconhecidoError,
    PjePageError,
    PjeSessionInvalidError,
    ProcessoNaoEncontradoError,
)
from app.connectors.pje.pages.login import LoginPage
from app.connectors.pje.pages.peticionar import PeticionarPage
from app.connectors.pje.pages.processo import ProcessoPage
from app.connectors.pje.session import PjeBrowserSession


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
    pdf_bytes: bytes | None = None
    pje_base_url: str | None = None
    storage_state: dict | None = None


@dataclass(frozen=True)
class PjeFilingCheckpoint:
    checkpoint: str
    modo: str
    irreversible: bool
    next_action: str
    evidence: dict


class PjeConnectorError(RuntimeError):
    """Base connector failure surfaced to the job layer."""


class LocalEvidenceStore:
    """Capture local screenshots for audit evidence in development."""

    def __init__(self, root: str | Path = "artifacts/pje"):
        self.root = Path(root)

    def capture(self, page, label: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        safe_label = re.sub(r"[^a-zA-Z0-9_.-]+", "-", label).strip("-")
        path = self.root / f"{safe_label}.png"
        page.screenshot(path=str(path), full_page=True)
        return str(path)


class PjeAssistedConnector:
    """Prepare PJe filing up to the human signature/submit checkpoint."""

    def __init__(
        self,
        *,
        session_factory: Callable[..., object] | None = None,
        login_page_factory: Callable[[object], object] = LoginPage,
        processo_page_factory: Callable[[object], object] = ProcessoPage,
        peticionar_page_factory: Callable[[object], object] = PeticionarPage,
        evidence_store: LocalEvidenceStore | None = None,
    ):
        self._session_factory = session_factory
        self._login_page_factory = login_page_factory
        self._processo_page_factory = processo_page_factory
        self._peticionar_page_factory = peticionar_page_factory
        self._evidence_store = evidence_store or LocalEvidenceStore()

    def prepare_filing(
        self,
        package: PjeFilingPackage,
        *,
        signature_mode: str = "manual_pjeoffice",
    ) -> PjeFilingCheckpoint:
        if signature_mode not in {"manual_pjeoffice", "cloud_certificate"}:
            raise ValueError("modo de assinatura PJe desconhecido")

        next_action = self._next_action(signature_mode)
        if not package.pje_base_url or not package.storage_state:
            return self._manual_checkpoint(package, signature_mode, next_action)
        if not package.pdf_bytes:
            raise PjeConnectorError("PDF da minuta e obrigatorio para automacao PJe")

        states: list[str] = []
        screenshots: list[str] = []
        session_factory = self._session_factory or PjeBrowserSession

        try:
            with session_factory(
                base_url=package.pje_base_url,
                storage_state=package.storage_state,
            ) as browser:
                page = browser.page

                login = self._login_page_factory(page)
                login.ensure_session_valid()
                self._record_evidence(page, "session_ok", states, screenshots)

                processo = self._processo_page_factory(page)
                processo.localizar(package.numero_processo)
                self._record_evidence(page, "processo_localizado", states, screenshots)

                peticionar = self._peticionar_page_factory(page)
                peticionar.abrir_intermediaria()
                self._record_evidence(page, "peticionamento_aberto", states, screenshots)

                peticionar.selecionar_tipo(package.tipo_peticao)
                self._record_evidence(page, "tipo_selecionado", states, screenshots)

                peticionar.anexar_pdf(
                    filename=f"peticao-{package.peticao_id}.pdf",
                    pdf_bytes=package.pdf_bytes,
                )
                self._record_evidence(page, "minuta_anexada", states, screenshots)

                ready_evidence = peticionar.assert_ready_to_sign()
                self._record_evidence(page, "ready_to_sign", states, screenshots)
        except PjeSessionInvalidError as exc:
            raise PjeConnectorError("sessao_invalida") from exc
        except CaptchaDetectedError as exc:
            raise PjeConnectorError("captcha_detectado") from exc
        except ProcessoNaoEncontradoError as exc:
            raise PjeConnectorError("processo_nao_encontrado") from exc
        except LayoutDesconhecidoError as exc:
            raise PjeConnectorError("layout_desconhecido") from exc
        except PjePageError as exc:
            raise PjeConnectorError(str(exc)) from exc

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
                "base_url": package.pje_base_url,
                "draft_url": ready_evidence.get("draft_url"),
                "screenshots": screenshots,
                "states": states,
            },
        )

    def _record_evidence(
        self,
        page,
        state: str,
        states: list[str],
        screenshots: list[str],
    ) -> None:
        states.append(state)
        screenshots.append(self._evidence_store.capture(page, state))

    def _manual_checkpoint(
        self,
        package: PjeFilingPackage,
        signature_mode: str,
        next_action: str,
    ) -> PjeFilingCheckpoint:
        evidence = {
            "processo": package.numero_processo,
            "tribunal": package.tribunal,
            "orgao_julgador": package.orgao_julgador,
            "tipo_peticao": package.tipo_peticao,
            "credencial_id": package.credencial_id,
            "assinatura": signature_mode,
            "automation": "pending_pje_session",
        }
        return PjeFilingCheckpoint(
            checkpoint="ready_to_sign",
            modo="pje_assistido_playwright",
            irreversible=False,
            next_action=next_action,
            evidence=evidence,
        )

    def _next_action(self, signature_mode: str) -> str:
        if signature_mode == "manual_pjeoffice":
            return (
                "Advogado assina e envia no PJe/PJeOffice; depois informe o numero do protocolo."
            )
        return "Conectar provedor de certificado em nuvem antes do envio final."
