"""PJe intermediate petition page object."""

from __future__ import annotations

from pathlib import Path
import re
import tempfile

from app.connectors.pje.pages.errors import CaptchaDetectedError, LayoutDesconhecidoError


class PeticionarPage:
    def __init__(self, page):
        self.page = page

    def abrir_intermediaria(self) -> None:
        self._raise_if_captcha()
        candidates = [
            self.page.get_by_role(
                "tab",
                name=re.compile("anexar peti|juntar documentos|peti.*document", re.I),
            ),
            self.page.get_by_role(
                "link",
                name=re.compile("anexar peti|juntar documentos|peticionar", re.I),
            ),
            self.page.get_by_role(
                "button",
                name=re.compile("anexar peti|juntar documentos|peticionar", re.I),
            ),
            self.page.get_by_text(
                re.compile("anexar peti|juntar documentos|peticionar", re.I)
            ),
            self.page.locator("a[href*='peticionar' i]"),
        ]
        action = next((candidate for candidate in candidates if candidate.count() > 0), None)
        if action is None:
            raise LayoutDesconhecidoError("aba/acao de anexar peticao nao encontrada")
        action.first.click()
        self.page.wait_for_load_state("networkidle")

    def selecionar_tipo(self, tipo_peticao: str | None) -> None:
        self._raise_if_captcha()
        if not tipo_peticao:
            return
        candidates = [
            self.page.get_by_label(re.compile("tipo.*peti", re.I)),
            self.page.locator("select[name*='tipo' i]"),
            self.page.locator("[role='combobox']"),
        ]
        field = next((candidate for candidate in candidates if candidate.count() > 0), None)
        if field is None:
            raise LayoutDesconhecidoError("campo de tipo de peticao nao encontrado")
        try:
            field.first.select_option(label=tipo_peticao)
        except Exception:  # noqa: BLE001 - Playwright raises different selector errors
            field.first.click()
            self.page.get_by_text(tipo_peticao, exact=False).first.click()

    def anexar_pdf(self, *, filename: str, pdf_bytes: bytes) -> None:
        self._raise_if_captcha()
        with tempfile.NamedTemporaryFile(prefix="causor-pje-", suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = Path(tmp.name)
        try:
            file_inputs = self.page.locator("input[type='file']")
            if file_inputs.count() == 0:
                raise LayoutDesconhecidoError("campo de upload de PDF nao encontrado")
            file_inputs.first.set_input_files(
                {"name": filename, "mimeType": "application/pdf", "buffer": pdf_bytes}
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        self.page.wait_for_load_state("networkidle")
        self._raise_if_captcha()

    def assert_ready_to_sign(self) -> dict:
        self._raise_if_captcha()
        content = self.page.content().lower()
        ready_markers = ("assinar", "pjeoffice", "protocolar", "enviar")
        if not any(marker in content for marker in ready_markers):
            raise LayoutDesconhecidoError("tela de assinatura/envio nao encontrada")
        return {"draft_url": self.page.url}

    def _raise_if_captcha(self) -> None:
        content = self.page.content().lower()
        if "captcha" in content or "recaptcha" in content:
            raise CaptchaDetectedError("captcha detectado; advogado precisa assumir")
