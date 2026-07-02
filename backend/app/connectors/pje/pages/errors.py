"""Domain errors surfaced by PJe page objects."""


class PjePageError(RuntimeError):
    """Base page-object failure."""


class PjeSessionInvalidError(PjePageError):
    """The stored browser session no longer grants access to PJe."""


class CaptchaDetectedError(PjePageError):
    """PJe displayed a captcha; the lawyer must take over manually."""


class ProcessoNaoEncontradoError(PjePageError):
    """The requested process could not be found in PJe."""


class LayoutDesconhecidoError(PjePageError):
    """The expected PJe layout/selectors did not match the current page."""


class AssinaturaPendenteError(PjePageError):
    """PJe esperava assinatura do PJeOffice/certificado e nao recebeu a tempo.

    O conector pausa o ciclo de automatizacao aqui e devolve o controle ao
    advogado, que assina/protocola manualmente na mesma janela aberta. O fluxo
    assistido (nao-cloud-cert) dependedo advogado confirmar a assinatura no
    PJeOffice local; o Causor nao detem o certificado nem o PIN.
    """
