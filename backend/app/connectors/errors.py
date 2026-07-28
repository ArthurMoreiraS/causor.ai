"""Erros canônicos de conector, neutros de sistema.

Todo driver (PJe/e-SAJ/EPROC/Projudi) mapeia falhas cruas do Playwright para
um destes erros antes de devolver o comando ao backend. O ``str()`` carrega
apenas ``safe_detail``: nunca URL com query string, cookie ou conteúdo de
página — o texto pode acabar em job, auditoria e UI.
"""

from __future__ import annotations


class ConnectorError(RuntimeError):
    """Base: erro canônico com código estável e detalhe seguro."""

    code: str = "connector_error"
    retryable: bool = False
    requires_human: bool = True

    def __init__(self, safe_detail: str | None = None):
        self.safe_detail = safe_detail or ""
        super().__init__(self.safe_detail or self.code)

    def __str__(self) -> str:  # noqa: D105 - contrato: nunca vazar URL/página
        return self.safe_detail or self.code


class SessionExpired(ConnectorError):
    """Perfil local sem sessão válida; o advogado precisa relogar."""

    code = "session_expired"
    retryable = True
    requires_human = True


class CaptchaRequired(ConnectorError):
    """Portal exibiu CAPTCHA/desafio; automação para e devolve o controle."""

    code = "captcha_required"
    retryable = True
    requires_human = True


class AccessDenied(ConnectorError):
    """Conta sem permissão para o processo/ação."""

    code = "access_denied"
    retryable = False
    requires_human = True


class LayoutUnknown(ConnectorError):
    """Variante de layout sem perfil aprovado; nunca clicar por texto genérico."""

    code = "layout_unknown"
    retryable = False
    requires_human = True


class CursorIncomplete(ConnectorError):
    """Paginação sem marcador determinístico de término."""

    code = "cursor_incomplete"
    retryable = True
    requires_human = False


class DocumentDownloadFailed(ConnectorError):
    """Download vazio, HTML no lugar de PDF ou hash divergente."""

    code = "document_download_failed"
    retryable = True
    requires_human = False


class SignatureRequired(ConnectorError):
    """Assinador (PJeOffice/applet) pediu ação humana fora da janela."""

    code = "signature_required"
    retryable = False
    requires_human = True


class ReceiptNotVerified(ConnectorError):
    """Protocolo sem número/comprovante verificáveis; nunca marcar protocolada."""

    code = "receipt_not_verified"
    retryable = False
    requires_human = True


class SystemMigrated(ConnectorError):
    """Processo migrou de sistema (ex.: e-SAJ -> eproc); reroteamento necessário."""

    code = "system_migrated"
    retryable = False
    requires_human = False

    def __init__(self, target_system: str, safe_detail: str | None = None):
        self.target_system = target_system
        super().__init__(safe_detail or f"processo migrou para {target_system}")


class InstanceNotFound(ConnectorError):
    """O processo não existe nesta instância/grau — ausência, não falha.

    Distinto de `AccessDenied`: aqui o tribunal respondeu e afirmou que não há
    processo. Na dúvida (mensagem que também sugere permissão) o mapeamento
    tem de escolher `AccessDenied`, porque selar `not_applicable` sem os autos
    é fail-open.
    """

    code = "instance_not_found"
    retryable = False
    requires_human = False


class MniUnavailable(ConnectorError):
    """Endpoint MNI fora do ar ou instável; retry automático é seguro."""

    code = "mni_unavailable"
    retryable = True
    requires_human = False
