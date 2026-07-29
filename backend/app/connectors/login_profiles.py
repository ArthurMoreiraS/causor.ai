"""Detecção de sessão autenticada por sistema judicial.

**Fonte única.** O agente local (``open_court_login`` / ``check_court_session``)
e o conector PJe consomem daqui. Antes desta tabela existiam duas heurísticas
de substring independentes e quebradas em direções opostas: ``handlers.py``
exigia a *ausência* da palavra "senha" para confirmar login (e o painel logado
tem "Alterar Senha" no menu, então nunca confirmava), e ``pje/pages/login.py``
tratava "processo" como marcador de autenticado (e essa palavra aparece na
tela de login, então dava sessão válida para sessão morta).

Detecção é por **seletor visível**, não por substring: ``input[type=password]``
não existe num painel autenticado, mesmo que as palavras "Alterar Senha"
apareçam num link. As duas famílias de erro somem por construção.

``verificado=True`` exige ``evidencia`` preenchida e validação live contra o
portal real — a mesma trava de ``mni/profiles.py``. Perfil não verificado
**funciona**: apenas degrada para confirmação humana em vez de confirmar
sozinho.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoginProfile:
    sistema: str
    # Qualquer um visível => sessão autenticada.
    authenticated_selectors: tuple[str, ...]
    # Qualquer um visível => ainda na tela de login (tem precedência).
    login_selectors: tuple[str, ...]
    captcha_selectors: tuple[str, ...] = ()
    verificado: bool = False
    # Onde/quando o portal real foi observado. Obrigatório se verificado.
    evidencia: str | None = None


_PROFILES: dict[str, LoginProfile] = {}


def _register(profile: LoginProfile) -> None:
    _PROFILES[profile.sistema.casefold()] = profile


# Seletores abaixo são o melhor conhecimento sobre cada família, ainda NÃO
# confirmados contra portal real. Todos nascem verificado=False de propósito:
# a promoção acontece só depois da validação live (Task 8 do plano).

_register(
    LoginProfile(
        sistema="EPROC",
        authenticated_selectors=(
            "#infraBarraSuperior",
            "a[href*='acao=logout']",
            "#lnkInfraSairSistema",
        ),
        login_selectors=("input[type='password']", "#txtSenha", "#pwdSenha"),
        captcha_selectors=("iframe[src*='recaptcha']", ".g-recaptcha"),
    )
)

_register(
    LoginProfile(
        sistema="PJe",
        authenticated_selectors=(
            "a[href*='logout']",
            "#painel-usuario",
            "[id*='btnSair']",
        ),
        login_selectors=("input[type='password']", "#username", "#password"),
        captcha_selectors=("iframe[src*='recaptcha']", ".g-recaptcha"),
    )
)

_register(
    LoginProfile(
        sistema="e-SAJ",
        authenticated_selectors=("a[href*='logout']", "#usuarioLogado", ".sairSistema"),
        login_selectors=("input[type='password']", "#senhaUsuario", "#usuario"),
        captcha_selectors=("iframe[src*='recaptcha']", ".g-recaptcha"),
    )
)

_register(
    LoginProfile(
        sistema="Projudi",
        authenticated_selectors=("a[href*='logout']", "a[href*='Sair']", "#menuPrincipal"),
        login_selectors=("input[type='password']", "#senha", "#login"),
        captcha_selectors=("iframe[src*='recaptcha']", ".g-recaptcha"),
    )
)


def resolve_login_profile(sistema: str | None) -> LoginProfile | None:
    if not sistema or not sistema.strip():
        return None
    return _PROFILES.get(sistema.strip().casefold())


def known_login_profiles() -> list[LoginProfile]:
    return sorted(_PROFILES.values(), key=lambda p: p.sistema)


def classify_page_state(*, authenticated: bool, login: bool, captcha: bool) -> str:
    """Regra pura de classificação. Precedência: captcha > login > autenticado.

    ``login`` vence ``authenticated`` de propósito: portal que ainda mostra o
    formulário de senha não está autenticado, por mais que a página também
    tenha um link parecido com menu de usuário.
    """
    if captcha:
        return "captcha"
    if login:
        return "login"
    if authenticated:
        return "authenticated"
    return "inconclusive"


def _any_visible(page, selectors: tuple[str, ...]) -> bool:
    """True se algum seletor está visível. Seletor quebrado é ignorado, nunca
    propaga exceção: portal que mudou vira ``inconclusive`` (confirmação
    humana), não um comando de agente morto."""
    for selector in selectors:
        try:
            if page.locator(selector).first.is_visible(timeout=500):
                return True
        except Exception:
            continue
    return False


def detect_page_state(page, profile: LoginProfile) -> str:
    """Classifica a página aberta no Playwright segundo o perfil do sistema."""
    return classify_page_state(
        authenticated=_any_visible(page, profile.authenticated_selectors),
        login=_any_visible(page, profile.login_selectors),
        captcha=_any_visible(page, profile.captcha_selectors),
    )


__all__ = [
    "LoginProfile",
    "classify_page_state",
    "detect_page_state",
    "known_login_profiles",
    "resolve_login_profile",
]
