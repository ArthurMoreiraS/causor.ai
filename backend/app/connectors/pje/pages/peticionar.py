"""PJe intermediate petition page object."""

from __future__ import annotations

from pathlib import Path
import re
import tempfile

from app.connectors.pje.pages.errors import (
    AssinaturaPendenteError,
    CaptchaDetectedError,
    LayoutDesconhecidoError,
)


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

    def assinar_e_enviar(self, *, assinar_timeout_ms: int = 180_000) -> dict:
        """Clica em Assinar/Protocolar e aguarda o comprovante do PJe.

        O conector assume que o PJeOffice local ja assina o documento quando o
        PJe dispara o pedido (o certificado fica na maquina do advogado, nao no
        Causor). Aguardamos ate o comprovante aparecer; se o PJeOffice nao
        responder a tempo, levanta AssinaturaPendenteError para o advogado
        assumir a janela aberta.

        Retorna {'protocolo': str, 'comprovante_url': str | None} capturados do
        comprovante do PJe (PDF/HTML). O numero e validado por regex.
        """
        self._raise_if_captcha()

        # Clica no botao de assinar/protocolar (varias variantes do PJe).
        candidates = [
            self.page.get_by_role("button", name=re.compile("assinar.*protocol|protocol.*assinar", re.I)),
            self.page.get_by_role("button", name=re.compile("^assinar", re.I)),
            self.page.get_by_role("button", name=re.compile("protocolar|enviar pet", re.I)),
            self.page.get_by_text(re.compile("assinar e protocolar", re.I), exact=False),
        ]
        botao = next((c for c in candidates if c.count() > 0), None)
        if botao is None:
            raise LayoutDesconhecidoError("botao de assinar/protocolar nao encontrado")
        botao.first.click()

        # Aguarda o comprovante aparecer. PJe mostra "Comprovante" + numero.
        # E tolerante: o PJeOffice pode demorar (push de assinatura local).
        try:
            self.page.wait_for_text(
                re.compile("comprovante|protocolo.*gerado|peticao.*protocol", re.I),
                timeout=assinar_timeout_ms,
            )
        except Exception as exc:  # noqa: BLE001 - timeout espera do PJeOffice
            raise AssinaturaPendenteError(
                "assinatura pendente no PJeOffice local; advogado deve confirmar "
                "e o conector retomara na proxima tentativa"
            ) from exc

        self._raise_if_captcha()
        return self._capturar_comprovante()

    def _capturar_comprovante(self) -> dict:
        """Extrai o numero do protocolo e a URL do comprovante da tela atual."""
        conteudo = self.page.content()
        # Padrao classico de numero de protocolo PJe: numerico ou com
        # prefixo/ano; tambem captura "Protocolo: 1234567" todo-digits longo.
        match = re.search(
            r"(?:protocolo|n[ºo°\.]*\s*protocolo|processo)\D{0,5}(\d{4,20})", conteudo, re.I
        ) or re.search(r"(\d{6,20})", self.page.url)
        protocolo = match.group(1) if match else None
        comprovante_url = self.page.url
        return {"protocolo": protocolo, "comprovante_url": comprovante_url}

    def baixar_comprovante_pdf(self, timeout_ms: int = 30_000) -> bytes | None:
        """Baixa o PDF do comprovante se houver link de download visivel."""
        self._raise_if_captcha()
        link = self.page.get_by_role("link", name=re.compile("baixar.*comprov|comprovante.*pdf|download.*pdf", re.I))
        if link.count() == 0:
            return None
        try:
            with self.page.expect_download(timeout=timeout_ms) as info:
                link.first.click()
            download = info.value
            return download.path().read_bytes() if download.path() else None
        except Exception:  # noqa: BLE001 - download opcional; nao bloqueia o fluxo
            return None

    def _raise_if_captcha(self) -> None:
        content = self.page.content().lower()
        if "captcha" in content or "recaptcha" in content:
            raise CaptchaDetectedError("captcha detectado; advogado precisa assumir")
