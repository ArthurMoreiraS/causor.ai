# Login multi-sistema robusto + sessão viva — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir a detecção de login por substring (quebrada em dois lugares, em direções opostas) por detecção via seletor DOM com fonte única, e fazer o estado `"expirado"` — hoje inalcançável em produção — ser realmente alcançado por uma checagem de sessão viva.

**Architecture:** Um registro de `LoginProfile` por sistema (mesmo padrão de `mni/profiles.py`) com uma função pura `classify_page_state` que agente local e conector PJe consomem. Detecção por `locator.is_visible()`, não por substring no HTML. Quando o resultado é inconclusivo, degrada para confirmação humana no navegador local — nunca para `login_timeout`.

**Tech Stack:** Python 3.12, Playwright (sync API), SQLAlchemy 2.0, pytest.

**Spec de referência:** [`../specs/2026-07-29-login-multissistema-design.md`](../specs/2026-07-29-login-multissistema-design.md)

## Global Constraints

- **Fonte única de detecção.** Depois deste plano, nenhum arquivo além de `login_profiles.py` pode conter lista de marcadores de login/autenticado. `handlers.py` e `pje/pages/login.py` consomem de lá.
- **Seletor, nunca substring.** Detecção é `locator(...).is_visible()`. Proibido `"palavra" in page.content()`.
- **Todos os perfis nascem `verificado=False`.** Promoção a `True` exige evidência registrada em `LoginProfile.evidencia` e validação live. A observação do eproc/TJTO **ainda não aconteceu** — quem a fizer promove o perfil na Task 8.
- **Nunca criar segundo ponto de decisão MNI vs agente.** `assistant.py:65` é o único. Nada neste plano pergunta "isto é MNI?"; a exclusão é por construção (rota MNI não tem linha em `CourtSessionState`).
- **Inconclusivo nunca vira erro.** Sistema sem perfil, ou perfil que não bateu, cai em confirmação humana.
- **Lock de perfil Chromium é `inconclusive`, nunca `expirado`.** Derrubar sessão boa é pior que não checar.
- Comandos rodados de `/backend` com `.venv\Scripts\python.exe` (Windows).

---

## Estrutura de arquivos

**Criar:**
- `backend/app/connectors/login_profiles.py` — registro de perfis + `classify_page_state` (pura) + `detect_page_state` (adapter Playwright)
- `backend/tests/test_login_profiles.py` — testes puros, incluindo os dois bugs como regressão

**Modificar:**
- `backend/app/connectors/simulators/base.py` — login/painel com DOM realista (form de senha real; painel com "Alterar Senha")
- `backend/app/local_agent/handlers.py` — detecção por seletor + `handle_check_court_session` + banner
- `backend/app/connectors/pje/pages/login.py` — consumir `login_profiles` (deduplicação)
- `backend/app/connectors/sessions.py` — `request_session_check` + `apply_session_check_result`
- `backend/app/capture/court_routing.py:217` — remover default `"PJe"`
- `backend/app/connectors/assistant.py:43` — remover default `"PJe"`
- `backend/app/connectors/pje/session.py` — `CAUSOR_PJE_ALLOW_PROD` → `CAUSOR_COURT_ALLOW_PROD` (aceitando o antigo)

---

### Task 1: `login_profiles.py` — perfis e classificação pura

**Files:**
- Create: `backend/app/connectors/login_profiles.py`
- Create: `backend/tests/test_login_profiles.py`

**Interfaces:**
- Produces: `LoginProfile` (dataclass), `resolve_login_profile(sistema: str) -> LoginProfile | None`, `known_login_profiles() -> list[LoginProfile]`, `classify_page_state(*, authenticated: bool, login: bool, captcha: bool) -> str` retornando `"authenticated" | "login" | "captcha" | "inconclusive"`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_login_profiles.py`:

```python
"""Detecção de sessão: regras puras e trava de perfil verificado."""

import pytest

from app.connectors.login_profiles import (
    LoginProfile,
    classify_page_state,
    known_login_profiles,
    resolve_login_profile,
)


def test_captcha_tem_precedencia_sobre_tudo():
    assert classify_page_state(authenticated=True, login=True, captcha=True) == "captcha"


def test_formulario_de_login_visivel_significa_ainda_esperando():
    assert classify_page_state(authenticated=False, login=True, captcha=False) == "login"


def test_painel_com_link_alterar_senha_e_autenticado():
    """Regressão do bug de handlers.py: o painel logado tem 'Alterar Senha' no
    menu, mas NÃO tem formulário de senha. Com seletor, login=False."""
    assert classify_page_state(authenticated=True, login=False, captcha=False) == "authenticated"


def test_tela_de_login_com_a_palavra_processo_nao_e_autenticado():
    """Regressão do bug de pje/pages/login.py: 'processo' aparece na tela de
    login de vários tribunais. O que decide é o formulário visível."""
    assert classify_page_state(authenticated=True, login=True, captcha=False) == "login"


def test_nada_reconhecido_e_inconclusivo_nao_erro():
    assert classify_page_state(authenticated=False, login=False, captcha=False) == "inconclusive"


def test_resolve_e_case_insensitive():
    assert resolve_login_profile("eproc") is resolve_login_profile("EPROC")


def test_sistema_desconhecido_nao_tem_perfil():
    assert resolve_login_profile("SISTEMA-QUE-NAO-EXISTE") is None


def test_os_quatro_sistemas_tem_perfil():
    sistemas = {p.sistema for p in known_login_profiles()}
    assert sistemas == {"PJe", "EPROC", "e-SAJ", "Projudi"}


def test_perfil_verificado_exige_evidencia_registrada():
    """Espelha test_todo_perfil_registrado_foi_verificado do MNI. Marcar
    verificado sem ter olhado o portal real é o erro de 2026-07-21."""
    for profile in known_login_profiles():
        if profile.verificado:
            assert profile.evidencia, f"{profile.sistema}: verificado sem evidência"


def test_todo_perfil_tem_seletor_de_login_e_de_autenticado():
    for profile in known_login_profiles():
        assert profile.login_selectors, f"{profile.sistema} sem login_selectors"
        assert profile.authenticated_selectors, f"{profile.sistema} sem authenticated_selectors"


def test_perfil_e_imutavel():
    profile = resolve_login_profile("EPROC")
    with pytest.raises(Exception):
        profile.sistema = "outro"
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_login_profiles.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.connectors.login_profiles'`

- [ ] **Step 3: Implementar o módulo**

Criar `backend/app/connectors/login_profiles.py`:

```python
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

from dataclasses import dataclass, field


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
# confirmados contra portal real. Todos nascem verificado=False de propósito.

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


__all__ = [
    "LoginProfile",
    "classify_page_state",
    "known_login_profiles",
    "resolve_login_profile",
]
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_login_profiles.py -q`
Expected: PASS (11 testes)

- [ ] **Step 5: Lint e commit**

```bash
.\.venv\Scripts\python.exe -m ruff check app/connectors/login_profiles.py tests/test_login_profiles.py
git add backend/app/connectors/login_profiles.py backend/tests/test_login_profiles.py
git commit -m "feat(login): registro de perfis de deteccao por sistema, fonte unica"
```

**Deliverable:** regra de classificação pura, testada, com os dois bugs cobertos por teste de regressão.

---

### Task 2: Simuladores com DOM realista de login e painel

**Files:**
- Modify: `backend/app/connectors/simulators/base.py`
- Create: `backend/tests/test_simulator_login_dom.py`

**Interfaces:**
- Consumes: nada.
- Produces: `CourtSimulator.login_html()` com `<input type="password">` real; `CourtSimulator.panel_html()` com link "Alterar Senha" **e** marcador de autenticado. É o alvo sintético que reproduz o bug.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_simulator_login_dom.py`:

```python
"""O simulador precisa reproduzir a armadilha real dos portais."""

from app.connectors.simulators import eproc, esaj, pje, projudi

SIMULADORES = (eproc.build(), pje.build(), esaj.build(), projudi.build())


def test_login_tem_campo_de_senha_de_verdade():
    for sim in SIMULADORES:
        assert 'type="password"' in sim.login_html(), sim.sistema


def test_painel_tem_alterar_senha_mas_nao_tem_campo_de_senha():
    """Esta é a armadilha que quebrou handlers.py: a palavra 'senha' aparece
    no painel logado, mas não há formulário de senha."""
    for sim in SIMULADORES:
        panel = sim.panel_html()
        assert "Alterar Senha" in panel, sim.sistema
        assert 'type="password"' not in panel, sim.sistema


def test_painel_tem_marcador_de_autenticado():
    for sim in SIMULADORES:
        assert 'href="#logout"' in sim.panel_html(), sim.sistema


def test_login_nao_tem_marcador_de_autenticado():
    for sim in SIMULADORES:
        assert 'href="#logout"' not in sim.login_html(), sim.sistema
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_simulator_login_dom.py -q`
Expected: FAIL — `assert 'type="password"' in sim.login_html()` (hoje o login só tem `<button>`)

- [ ] **Step 3: Ajustar o simulador base**

Em `backend/app/connectors/simulators/base.py`, substituir `login_html` e `panel_html`:

```python
    def login_html(self) -> str:
        return (
            f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            f"<title>{self.sistema} Simulator</title></head><body>"
            f"<h1>Acesso {self.sistema}</h1>"
            # A palavra "processo" aqui é de propósito: é o falso positivo que
            # quebrava pje/pages/login.py ("processo" como marcador de logado).
            f"<p>Consulta processual e peticionamento de processo eletronico.</p>"
            f"<form id='form-login' method='post'>"
            f"<input type='text' name='usuario' placeholder='Usuario'>"
            f'<input type="password" name="senha" placeholder="Senha">'
            f"<button type='submit'>Entrar</button>"
            f"</form>"
            f"<button type='button'>{self.login_marker}</button>"
            f"<button type='button'>Entrar com gov.br</button>"
            f"</body></html>"
        )

    def panel_html(self) -> str:
        return (
            f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            f"<title>{self.sistema} Simulator</title></head><body>"
            f"<header>{self.panel_marker}"
            # "Alterar Senha" no menu do painel logado: a armadilha que fazia
            # handlers.py nunca confirmar o login (substring "senha").
            f" · <a href='#alterar-senha'>Alterar Senha</a>"
            f" · <a href=\"#logout\">Sair</a></header>"
            f"<section id='autos'>{self.autos_html(page=1)}</section>"
            f"</body></html>"
        )
```

- [ ] **Step 4: Rodar e confirmar que passa**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_simulator_login_dom.py -q
.\.venv\Scripts\python.exe -m pytest tests/ -q -k simulator
```
Expected: novos testes PASS; nenhum teste de simulador existente quebrado.

- [ ] **Step 5: Commit**

```bash
git add backend/app/connectors/simulators/base.py backend/tests/test_simulator_login_dom.py
git commit -m "test(simulators): login/painel com o DOM que reproduz os dois bugs de deteccao"
```

**Deliverable:** alvo sintético que reproduz as duas armadilhas reais.

---

### Task 3: Agente detecta sessão por seletor

**Files:**
- Modify: `backend/app/connectors/login_profiles.py` (adicionar `detect_page_state`)
- Modify: `backend/app/local_agent/handlers.py`
- Create: `backend/tests/test_agent_login_detection.py`

**Interfaces:**
- Consumes: `classify_page_state`, `resolve_login_profile` (Task 1).
- Produces: `detect_page_state(page, profile) -> str` — adapter que consulta o Playwright; `handle_open_court_login` passa a usá-lo.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_agent_login_detection.py`:

```python
"""Detecção contra uma página falsa que imita a API do Playwright."""

from app.connectors.login_profiles import detect_page_state, resolve_login_profile


class FakeLocator:
    def __init__(self, visible: bool, raises: bool = False):
        self._visible = visible
        self._raises = raises

    @property
    def first(self):
        return self

    def is_visible(self, timeout: float = 0) -> bool:
        if self._raises:
            raise RuntimeError("seletor invalido")
        return self._visible


class FakePage:
    """Devolve visível apenas para os seletores listados."""

    def __init__(self, visiveis: set[str], quebrados: set[str] | None = None):
        self.visiveis = visiveis
        self.quebrados = quebrados or set()

    def locator(self, selector: str):
        if selector in self.quebrados:
            return FakeLocator(False, raises=True)
        return FakeLocator(selector in self.visiveis)


def test_painel_autenticado_com_alterar_senha_e_reconhecido():
    profile = resolve_login_profile("EPROC")
    page = FakePage({"#infraBarraSuperior"})
    assert detect_page_state(page, profile) == "authenticated"


def test_tela_de_login_e_reconhecida_pelo_campo_de_senha():
    profile = resolve_login_profile("EPROC")
    page = FakePage({"input[type='password']"})
    assert detect_page_state(page, profile) == "login"


def test_captcha_vence():
    profile = resolve_login_profile("PJe")
    page = FakePage({".g-recaptcha", "input[type='password']"})
    assert detect_page_state(page, profile) == "captcha"


def test_pagina_desconhecida_e_inconclusiva():
    profile = resolve_login_profile("PJe")
    assert detect_page_state(FakePage(set()), profile) == "inconclusive"


def test_seletor_que_explode_nao_derruba_a_deteccao():
    """Portal muda e um seletor vira inválido: vira inconclusivo (confirmação
    humana), nunca exceção que mata o comando do agente."""
    profile = resolve_login_profile("EPROC")
    page = FakePage(set(), quebrados={"#infraBarraSuperior"})
    assert detect_page_state(page, profile) == "inconclusive"
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_agent_login_detection.py -q`
Expected: FAIL — `ImportError: cannot import name 'detect_page_state'`

- [ ] **Step 3: Adicionar o adapter em `login_profiles.py`**

Acrescentar ao final de `backend/app/connectors/login_profiles.py` (antes do `__all__`):

```python
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
```

E incluir `"detect_page_state"` na lista `__all__`.

- [ ] **Step 4: Reescrever a detecção em `handlers.py`**

Em `backend/app/local_agent/handlers.py`, remover `_LOGIN_MARKERS`, `_AUTHENTICATED_MARKERS` e `_page_state`, e trocar o corpo de `handle_open_court_login`:

```python
"""Handlers de comando do agente local.

``open_court_login`` abre o portal do tribunal em janela headed na máquina do
advogado e espera o login acontecer. O desfecho reportado ao backend é apenas
``session_ready``/marcadores — a sessão fica no perfil local do navegador.

A detecção de estado vem de ``app.connectors.login_profiles`` (fonte única,
por seletor). Não reintroduzir marcadores de substring aqui.
"""

from __future__ import annotations

import time

from app.connectors.login_profiles import detect_page_state, resolve_login_profile
from app.local_agent import config as agent_config

LOGIN_WAIT_SECONDS = 300.0
POLL_SECONDS = 2.0


def handle_open_court_login(payload: dict) -> dict:
    """Abre o portal e aguarda o advogado logar; nunca digita credencial."""
    from app.local_agent.browser import persistent_court_context

    sistema = payload["sistema"]
    tribunal = payload["tribunal"]
    grau = payload["grau"]
    url_login = payload["url_login"]
    profile = resolve_login_profile(sistema)

    with persistent_court_context(
        root=agent_config.profiles_root(),
        sistema=sistema,
        tribunal=tribunal,
        grau=grau,
        url=url_login,
        headed=True,
    ) as (_context, page):
        deadline = time.monotonic() + LOGIN_WAIT_SECONDS
        while time.monotonic() < deadline:
            state = "inconclusive" if profile is None else detect_page_state(page, profile)
            if state == "authenticated":
                return {
                    "session_ready": True,
                    "version_marker": None,
                    "evidence": {
                        "final_url_host": _safe_host(page.url),
                        "confirmed_by": "selector",
                    },
                }
            if state == "captcha":
                return {"session_ready": False, "error_code": "captcha_required"}
            time.sleep(POLL_SECONDS)
    return {"session_ready": False, "error_code": "login_timeout"}
```

`_safe_host`, `handle_read_process`, `handle_prepare_filing` e `default_handlers` ficam como estão.

- [ ] **Step 5: Rodar testes**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_login_detection.py -q
.\.venv\Scripts\python.exe -m pytest tests/ -q -k "agent or login"
```
Expected: PASS. Se algum teste antigo referenciava `_page_state`, atualizar para usar `detect_page_state`.

- [ ] **Step 6: Commit**

```bash
.\.venv\Scripts\python.exe -m ruff check app/ tests/
git add backend/app/connectors/login_profiles.py backend/app/local_agent/handlers.py backend/tests/test_agent_login_detection.py
git commit -m "fix(agent): detecta sessao por seletor, elimina o falso negativo de 'Alterar Senha'"
```

**Deliverable:** o agente confirma login corretamente em painel que contém a palavra "senha".

---

### Task 4: Deduplicar a detecção do conector PJe

**Files:**
- Modify: `backend/app/connectors/pje/pages/login.py`
- Create: `backend/tests/test_pje_login_page.py`

**Interfaces:**
- Consumes: `detect_page_state`, `resolve_login_profile` (Tasks 1, 3).
- Produces: `LoginPage.ensure_session_valid()` sem marcadores próprios.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_pje_login_page.py`:

```python
"""O conector PJe usa a mesma fonte de detecção do agente."""

import pytest

from app.connectors.pje.pages.errors import CaptchaDetectedError, PjeSessionInvalidError
from app.connectors.pje.pages.login import LoginPage


class FakeLocator:
    def __init__(self, visible: bool):
        self._visible = visible

    @property
    def first(self):
        return self

    def is_visible(self, timeout: float = 0) -> bool:
        return self._visible


class FakePage:
    def __init__(self, visiveis: set[str]):
        self.visiveis = visiveis

    def locator(self, selector: str):
        return FakeLocator(selector in self.visiveis)


def test_tela_de_login_com_a_palavra_processo_e_sessao_invalida():
    """Regressão: 'processo' era marcador de autenticado, então a tela de
    login passava como sessão válida."""
    page = FakePage({"input[type='password']"})
    with pytest.raises(PjeSessionInvalidError):
        LoginPage(page).ensure_session_valid()


def test_painel_autenticado_passa():
    page = FakePage({"a[href*='logout']"})
    LoginPage(page).ensure_session_valid()  # não levanta


def test_captcha_levanta_erro_proprio():
    page = FakePage({".g-recaptcha"})
    with pytest.raises(CaptchaDetectedError):
        LoginPage(page).ensure_session_valid()


def test_inconclusivo_nao_derruba_o_fluxo():
    """Sem evidência nenhuma, não dá para afirmar que a sessão morreu."""
    LoginPage(FakePage(set())).ensure_session_valid()  # não levanta


def test_modulo_nao_tem_mais_marcadores_proprios():
    from app.connectors.pje.pages import login as login_module

    fonte = login_module.__file__
    with open(fonte, encoding="utf-8") as handle:
        conteudo = handle.read()
    assert "entrar com gov.br" not in conteudo.lower(), "marcador duplicado voltou"
    assert "authenticated_markers" not in conteudo, "marcador duplicado voltou"
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pje_login_page.py -q`
Expected: FAIL — hoje `ensure_session_valid` chama `self.page.content()`, que `FakePage` não tem.

- [ ] **Step 3: Reescrever consumindo a fonte única**

Substituir todo `backend/app/connectors/pje/pages/login.py`:

```python
"""Validação de sessão PJe.

A regra de detecção **não** mora aqui: vem de
``app.connectors.login_profiles`` (fonte única, compartilhada com o agente
local). Antes, este módulo tinha sua própria lista de marcadores com
"processo" contando como autenticado — e essa palavra aparece na tela de
login de vários tribunais, então sessão morta passava como válida.
"""

from __future__ import annotations

from app.connectors.login_profiles import detect_page_state, resolve_login_profile
from app.connectors.pje.pages.errors import CaptchaDetectedError, PjeSessionInvalidError


class LoginPage:
    def __init__(self, page):
        self.page = page

    def ensure_session_valid(self) -> None:
        """Levanta se a sessão claramente não está autenticada.

        ``inconclusive`` não levanta: sem evidência não se afirma que a sessão
        morreu — derrubar sessão boa é pior que seguir e falhar adiante com
        erro específico.
        """
        profile = resolve_login_profile("PJe")
        if profile is None:  # pragma: no cover - perfil PJe é registrado sempre
            return
        state = detect_page_state(self.page, profile)
        if state == "captcha":
            raise CaptchaDetectedError("captcha detectado; advogado precisa assumir")
        if state == "login":
            raise PjeSessionInvalidError("sessao PJe expirada ou nao autenticada")
```

- [ ] **Step 4: Rodar testes**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pje_login_page.py -q
.\.venv\Scripts\python.exe -m pytest tests/ -q -k pje
```
Expected: PASS. Testes antigos que montavam HTML por string podem precisar virar `FakePage`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/connectors/pje/pages/login.py backend/tests/test_pje_login_page.py
git commit -m "refactor(pje): consome login_profiles, remove a segunda copia da deteccao"
```

**Deliverable:** uma única regra de detecção no repositório, com teste que impede a duplicação voltar.

---

### Task 5: `check_court_session` — sessão viva de ponta a ponta

**Files:**
- Modify: `backend/app/local_agent/handlers.py`
- Modify: `backend/app/connectors/sessions.py`
- Create: `backend/tests/test_session_check.py`

**Interfaces:**
- Consumes: `detect_page_state`, `resolve_login_profile`.
- Produces: handler `check_court_session`; `request_session_check(session, *, escritorio_id, usuario_id, sistema, tribunal, grau, url_login) -> tuple[CourtSessionState, AgentCommand]`; `apply_session_check_result(session, *, command, installation, resultado) -> CourtSessionState`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_session_check.py`:

```python
"""Checagem de sessão viva: o gatilho que finalmente aciona 'expirado'."""

from app.connectors.sessions import (
    apply_session_check_result,
    request_session_check,
    session_state_for,
)
from app.local_agent.handlers import default_handlers


def _rota(seeded):
    return {
        "escritorio_id": seeded.escritorio_id,
        "sistema": "EPROC",
        "tribunal": "TJTO",
        "grau": "1",
    }


def test_agente_expoe_o_comando_de_checagem():
    assert "check_court_session" in default_handlers()


def test_sessao_viva_atualiza_confirmacao(db_session, seeded, agent_installation):
    rota = _rota(seeded)
    _state, command = request_session_check(
        db_session, usuario_id=None, url_login="https://exemplo/login", **rota
    )
    state = apply_session_check_result(
        db_session,
        command=command,
        installation=agent_installation,
        resultado={"session_alive": True},
    )
    assert state.status == "conectado"
    assert state.last_confirmed_at is not None


def test_sessao_morta_marca_expirado(db_session, seeded, agent_installation):
    """Este é o caminho que hoje é inalcançável em produção: mark_session_expired
    só era chamado em teste."""
    rota = _rota(seeded)
    _state, command = request_session_check(
        db_session, usuario_id=None, url_login="https://exemplo/login", **rota
    )
    state = apply_session_check_result(
        db_session,
        command=command,
        installation=agent_installation,
        resultado={"session_alive": False, "error_code": "session_expired"},
    )
    assert state.status == "expirado"
    assert state.last_error_code == "session_expired"


def test_perfil_travado_nao_derruba_sessao_boa(db_session, seeded, agent_installation):
    """Lock do Chromium é inconclusivo. Marcar 'expirado' aqui faria o advogado
    relogar à toa toda vez que estivesse com o navegador aberto."""
    rota = _rota(seeded)
    _state, command = request_session_check(
        db_session, usuario_id=None, url_login="https://exemplo/login", **rota
    )
    state = apply_session_check_result(
        db_session,
        command=command,
        installation=agent_installation,
        resultado={"session_alive": None, "error_code": "profile_locked"},
    )
    assert state.status != "expirado"


def test_checagem_e_idempotente_por_rota_e_hora(db_session, seeded):
    rota = _rota(seeded)
    _s1, c1 = request_session_check(
        db_session, usuario_id=None, url_login="https://exemplo/login", **rota
    )
    _s2, c2 = request_session_check(
        db_session, usuario_id=None, url_login="https://exemplo/login", **rota
    )
    assert c1.id == c2.id
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_session_check.py -q`
Expected: FAIL — `ImportError: cannot import name 'request_session_check'`

- [ ] **Step 3: Implementar no backend**

Em `backend/app/connectors/sessions.py`, acrescentar ao final:

```python
def request_session_check(
    session: Session,
    *,
    escritorio_id: int,
    usuario_id: int | None,
    sistema: str,
    tribunal: str,
    grau: str,
    url_login: str,
) -> tuple[models.CourtSessionState, models.AgentCommand]:
    """Pede ao agente que confira se a sessão daquela rota continua viva.

    Só faz sentido para rota que já tem estado de navegador. Rota servida por
    MNI nunca cria ``CourtSessionState`` (a credencial vive no vault e a
    captura roda no servidor), então é excluída por construção — sem nenhuma
    pergunta do tipo "isto é MNI?" aqui.
    """
    state = _get_or_create_state(
        session, escritorio_id=escritorio_id, sistema=sistema, tribunal=tribunal, grau=grau
    )
    command = enqueue_command(
        session,
        escritorio_id=escritorio_id,
        usuario_id=usuario_id,
        tipo="check_court_session",
        idempotency_key=(
            f"court-check:{sistema.casefold()}:{tribunal.upper()}:{grau}:"
            f"{_now().strftime('%Y-%m-%dT%H')}"
        ),
        payload={
            "sistema": sistema,
            "tribunal": tribunal,
            "grau": grau,
            "url_login": url_login,
        },
    )
    session.flush()
    return state, command


def apply_session_check_result(
    session: Session,
    *,
    command: models.AgentCommand,
    installation: models.AgentInstallation,
    resultado: dict,
) -> models.CourtSessionState:
    """Traduz a checagem em estado.

    ``session_alive`` só decide quando é booleano. ``None`` significa que o
    agente não conseguiu concluir (perfil travado pelo navegador aberto, por
    exemplo) — nesse caso o estado fica como está: derrubar sessão boa é pior
    que não checar.
    """
    payload = command.payload
    alive = resultado.get("session_alive")
    if alive is True:
        state = _get_or_create_state(
            session,
            escritorio_id=command.escritorio_id,
            sistema=payload["sistema"],
            tribunal=payload["tribunal"],
            grau=payload["grau"],
        )
        state.status = "conectado"
        state.installation_id = installation.id
        state.last_confirmed_at = _now()
        state.last_error_code = None
        session.flush()
        return state
    if alive is False:
        return mark_session_expired(
            session,
            escritorio_id=command.escritorio_id,
            sistema=payload["sistema"],
            tribunal=payload["tribunal"],
            grau=payload["grau"],
            error_code=resultado.get("error_code") or "session_expired",
        )
    state = _get_or_create_state(
        session,
        escritorio_id=command.escritorio_id,
        sistema=payload["sistema"],
        tribunal=payload["tribunal"],
        grau=payload["grau"],
    )
    state.last_error_code = resultado.get("error_code") or "check_inconclusive"
    session.flush()
    return state
```

- [ ] **Step 4: Implementar o handler no agente**

Em `backend/app/local_agent/handlers.py`, acrescentar antes de `default_handlers` e registrar no dict:

```python
def handle_check_court_session(payload: dict) -> dict:
    """Confere headless se o perfil persistente ainda está autenticado.

    ``session_alive=None`` quando não dá para afirmar (perfil travado por uma
    janela aberta, seletor que mudou): o backend mantém o estado atual.
    """
    from app.local_agent.browser import persistent_court_context

    sistema = payload["sistema"]
    profile = resolve_login_profile(sistema)
    if profile is None:
        return {"session_alive": None, "error_code": "sem_perfil_de_login"}

    try:
        with persistent_court_context(
            root=agent_config.profiles_root(),
            sistema=sistema,
            tribunal=payload["tribunal"],
            grau=payload["grau"],
            url=payload["url_login"],
            headed=False,
        ) as (_context, page):
            state = detect_page_state(page, profile)
    except Exception:
        # Perfil em uso pelo navegador aberto do advogado é o caso comum.
        return {"session_alive": None, "error_code": "profile_locked"}

    if state == "authenticated":
        return {"session_alive": True}
    if state == "login":
        return {"session_alive": False, "error_code": "session_expired"}
    return {"session_alive": None, "error_code": f"check_{state}"}
```

E em `default_handlers`:

```python
def default_handlers() -> dict:
    return {
        "open_court_login": handle_open_court_login,
        "check_court_session": handle_check_court_session,
        "read_process": handle_read_process,
        "prepare_filing": handle_prepare_filing,
    }
```

- [ ] **Step 5: Rodar testes**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_session_check.py tests/test_court_session_state.py -q
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
.\.venv\Scripts\python.exe -m ruff check app/ tests/
git add backend/app/connectors/sessions.py backend/app/local_agent/handlers.py backend/tests/test_session_check.py
git commit -m "feat(sessions): checagem de sessao viva aciona o estado expirado orfao"
```

**Deliverable:** `mark_session_expired` deixa de ser código só de teste; lock de perfil não derruba sessão boa.

---

### Task 6: Confirmação humana quando a detecção é inconclusiva

**Files:**
- Modify: `backend/app/local_agent/handlers.py`
- Create: `backend/tests/test_login_human_confirm.py`

**Interfaces:**
- Consumes: `detect_page_state`.
- Produces: constante `INCONCLUSIVE_BEFORE_PROMPT_SECONDS = 30.0`; função `_install_confirm_banner(page) -> None`; `_confirm_clicked(page) -> bool`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_login_human_confirm.py`:

```python
"""Tribunal desconhecido não pode virar login_timeout."""

from app.local_agent import handlers


class FakePage:
    def __init__(self, clicked_after: int = 1):
        self.evaluated = []
        self.calls = 0
        self.clicked_after = clicked_after
        self.url = "https://tribunal.exemplo/painel"

    def evaluate(self, script: str):
        self.evaluated.append(script)
        if "causorLoginConfirmed" in script and "document.createElement" not in script:
            self.calls += 1
            return self.calls >= self.clicked_after
        return None


def test_banner_e_injetado_uma_vez():
    page = FakePage()
    handlers._install_confirm_banner(page)
    handlers._install_confirm_banner(page)
    criacoes = [s for s in page.evaluated if "document.createElement" in s]
    assert len(criacoes) == 1


def test_banner_pergunta_em_portugues():
    page = FakePage()
    handlers._install_confirm_banner(page)
    assert "Já estou logado" in page.evaluated[0]


def test_confirmacao_humana_e_lida_do_flag():
    page = FakePage(clicked_after=1)
    assert handlers._confirm_clicked(page) is True


def test_pagina_que_explode_nao_confirma_sozinha():
    class Explode:
        def evaluate(self, script: str):
            raise RuntimeError("sem javascript")

    assert handlers._confirm_clicked(Explode()) is False
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_login_human_confirm.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute '_install_confirm_banner'`

- [ ] **Step 3: Implementar o banner**

Em `backend/app/local_agent/handlers.py`, acrescentar após as constantes:

```python
INCONCLUSIVE_BEFORE_PROMPT_SECONDS = 30.0

_BANNER_SCRIPT = """
(() => {
  if (document.getElementById('causor-confirm-banner')) return;
  window.causorLoginConfirmed = false;
  const bar = document.createElement('div');
  bar.id = 'causor-confirm-banner';
  bar.style.cssText = 'position:fixed;z-index:2147483647;left:0;right:0;bottom:0;'
    + 'background:#111;color:#fff;font:14px system-ui;padding:12px 16px;'
    + 'display:flex;gap:12px;align-items:center;justify-content:center';
  const text = document.createElement('span');
  text.textContent = 'Causor não conseguiu confirmar o login automaticamente.';
  const button = document.createElement('button');
  button.textContent = 'Já estou logado';
  button.style.cssText = 'background:#fff;color:#111;border:0;border-radius:6px;'
    + 'padding:6px 14px;cursor:pointer;font-weight:600';
  button.onclick = () => { window.causorLoginConfirmed = true; bar.remove(); };
  bar.appendChild(text); bar.appendChild(button);
  document.body.appendChild(bar);
})();
"""


def _install_confirm_banner(page) -> None:
    """Injeta o pedido de confirmação na janela local do agente.

    Só renderiza no navegador da máquina do advogado; não envia nem altera
    nada no sistema do tribunal.
    """
    try:
        page.evaluate(_BANNER_SCRIPT)
    except Exception:
        return


def _confirm_clicked(page) -> bool:
    try:
        return bool(page.evaluate("window.causorLoginConfirmed === true"))
    except Exception:
        return False
```

- [ ] **Step 4: Ligar no laço de login**

Substituir o laço de `handle_open_court_login` (dentro do `with`):

```python
        deadline = time.monotonic() + LOGIN_WAIT_SECONDS
        inconclusive_since: float | None = None
        while time.monotonic() < deadline:
            state = "inconclusive" if profile is None else detect_page_state(page, profile)
            if state == "authenticated":
                return {
                    "session_ready": True,
                    "version_marker": None,
                    "evidence": {
                        "final_url_host": _safe_host(page.url),
                        "confirmed_by": "selector",
                    },
                }
            if state == "captcha":
                return {"session_ready": False, "error_code": "captcha_required"}
            if state == "inconclusive":
                now = time.monotonic()
                if inconclusive_since is None:
                    inconclusive_since = now
                elif now - inconclusive_since >= INCONCLUSIVE_BEFORE_PROMPT_SECONDS:
                    _install_confirm_banner(page)
                    if _confirm_clicked(page):
                        return {
                            "session_ready": True,
                            "version_marker": None,
                            "evidence": {
                                "final_url_host": _safe_host(page.url),
                                "confirmed_by": "human",
                            },
                        }
            else:
                inconclusive_since = None
            time.sleep(POLL_SECONDS)
```

- [ ] **Step 5: Rodar testes**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_login_human_confirm.py tests/test_agent_login_detection.py -q
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/local_agent/handlers.py backend/tests/test_login_human_confirm.py
git commit -m "feat(agent): confirmacao humana quando a deteccao e inconclusiva"
```

**Deliverable:** tribunal sem perfil verificado funciona, com um clique a mais — nunca com `login_timeout`.

---

### Task 7: Remover os vieses de PJe

**Files:**
- Modify: `backend/app/capture/court_routing.py`
- Modify: `backend/app/connectors/assistant.py`
- Modify: `backend/app/connectors/pje/session.py`
- Create: `backend/tests/test_sem_viés_pje.py`

**Interfaces:**
- Produces: `resolve_route` devolve `sistema="DESCONHECIDO"` para tribunal não mapeado; `validate_training_base_url` passa a valer para os 4 sistemas via `CAUSOR_COURT_ALLOW_PROD` (aceitando `CAUSOR_PJE_ALLOW_PROD` por compatibilidade).

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_sem_vies_pje.py`:

```python
"""PJe não pode ser o palpite silencioso para tribunal desconhecido."""

import pytest

from app.capture.court_routing import resolve_route
from app.connectors.pje.session import PjeSessionError, validate_training_base_url


def test_tribunal_desconhecido_nao_vira_pje():
    route = resolve_route("TJXX", "1")
    assert route is not None
    assert route.sistema == "DESCONHECIDO"
    assert route.verificado is False


def test_tribunal_conhecido_mantem_o_sistema():
    assert resolve_route("TJTO", "1").sistema == "EPROC"
    assert resolve_route("TJSP", "1").sistema == "e-SAJ"


def test_producao_bloqueada_para_eproc_tambem(monkeypatch):
    """Antes só o PJe tinha trava: eproc/e-SAJ/Projudi abriam produção sem
    nenhuma barreira."""
    monkeypatch.delenv("CAUSOR_COURT_ALLOW_PROD", raising=False)
    monkeypatch.delenv("CAUSOR_PJE_ALLOW_PROD", raising=False)
    with pytest.raises(PjeSessionError):
        validate_training_base_url("https://eproc1.tjto.jus.br/eprocV2_prod_1grau/")


def test_homologacao_continua_liberada(monkeypatch):
    monkeypatch.delenv("CAUSOR_COURT_ALLOW_PROD", raising=False)
    monkeypatch.delenv("CAUSOR_PJE_ALLOW_PROD", raising=False)
    validate_training_base_url("https://pje-homolog.tjxx.jus.br/pje/")


def test_flag_nova_libera(monkeypatch):
    monkeypatch.setenv("CAUSOR_COURT_ALLOW_PROD", "1")
    validate_training_base_url("https://eproc1.tjto.jus.br/eprocV2_prod_1grau/")


def test_flag_antiga_continua_valendo(monkeypatch):
    """Compatibilidade: o .env de quem já rodava não pode quebrar."""
    monkeypatch.delenv("CAUSOR_COURT_ALLOW_PROD", raising=False)
    monkeypatch.setenv("CAUSOR_PJE_ALLOW_PROD", "1")
    validate_training_base_url("https://eproc1.tjto.jus.br/eprocV2_prod_1grau/")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_sem_vies_pje.py -q`
Expected: FAIL — `assert 'PJe' == 'DESCONHECIDO'`

- [ ] **Step 3: Tirar o default de `court_routing.py`**

Em `backend/app/capture/court_routing.py`, no `resolve_route`, trocar o bloco `if cfg is None`:

```python
    cfg = _ROUTES.get(sigla)
    if cfg is None:
        # Sem palpite de sistema: chutar "PJe" mandava tribunal de e-SAJ/eproc
        # para o fluxo errado silenciosamente. Desconhecido é explícito e o
        # cadastro/DataJud confirma depois.
        return CourtRoute(
            tribunal=sigla, grau=grau, sistema="DESCONHECIDO",
            url_login=None, url_peticionamento=None, verificado=False,
        )
```

- [ ] **Step 4: Tirar o default de `assistant.py`**

Em `backend/app/connectors/assistant.py`, no `route_for`:

```python
def route_for(processo: models.Processo, grau: str) -> dict:
    route = resolve_route(processo.tribunal, grau)
    # Sem default de PJe: o sistema vem do processo, da rota conhecida, ou é
    # declaradamente desconhecido.
    sistema = processo.sistema or (route.sistema if route else None) or "DESCONHECIDO"
    tribunal = route.tribunal if route else (processo.tribunal or "DESCONHECIDO")
    return {"sistema": sistema, "tribunal": tribunal, "grau": grau}
```

- [ ] **Step 5: Generalizar a trava de produção**

Em `backend/app/connectors/pje/session.py`, trocar o início de `validate_training_base_url`:

```python
def validate_training_base_url(base_url: str) -> None:
    """Recusa URL de produção salvo liberação explícita.

    Vale para os quatro sistemas: antes só o PJe tinha essa trava, e
    eproc/e-SAJ/Projudi abriam portal de produção sem barreira nenhuma.
    ``CAUSOR_PJE_ALLOW_PROD`` continua aceito por compatibilidade.
    """

    if os.getenv("CAUSOR_COURT_ALLOW_PROD") == "1" or os.getenv("CAUSOR_PJE_ALLOW_PROD") == "1":
        return
```

- [ ] **Step 6: Rodar a suíte inteira**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sem_vies_pje.py -q
.\.venv\Scripts\python.exe -m pytest -q
```
Expected: novos PASS; suíte inteira verde. Testes que assumiam `"PJe"` para tribunal desconhecido precisam ser atualizados para `"DESCONHECIDO"` — a mudança é intencional.

- [ ] **Step 7: Commit**

```bash
.\.venv\Scripts\python.exe -m ruff check app/ tests/
git add backend/app/capture/court_routing.py backend/app/connectors/assistant.py backend/app/connectors/pje/session.py backend/tests/test_sem_vies_pje.py
git commit -m "fix(routing): sem palpite de PJe e trava de producao para os quatro sistemas"
```

**Deliverable:** nenhum default silencioso de PJe; eproc/e-SAJ/Projudi ganham a trava de produção que só o PJe tinha.

> **Desvio registrado na execução (2026-07-29).** Tirar o default derrubou 3
> testes legados e a investigação mostrou que o problema era maior que o spec
> previa: o default não cobria só "sigla inexistente" — **10 TJs** (TJAM,
> TJAP, TJES, TJPB, TJPI, TJRJ, TJRN, TJRO, TJRR, TJSE), **TST**, **TSE**, os
> **27 TREs** e o **TRF2** dependiam dele. São tribunais reais; deixá-los cair
> em `DESCONHECIDO` seria uma regressão pior que o bug original.
>
> Em vez de afrouxar o teste ou reverter, o palpite silencioso virou **tabela
> explícita**. Isso corrigiu um erro que o default escondia: **o TRF2 é eproc**,
> e o default o classificava como PJe. TJAP/TJES/TJPI/TJRR entraram com
> evidência — os endpoints MNI `/pje/` deles responderam WSDL na varredura de
> 2026-07-22 registrada em `areas/mni-credenciamento.md`.
>
> Também foi corrigido um teste que passava pelo motivo errado:
> `test_flag_nova_libera` não removia `CAUSOR_PJE_ALLOW_PROD`, que o `.env` de
> dev traz — a flag nova nem era exercitada.

---

### Task 8: Validação live no eproc do TJTO e promoção do perfil (👤 Arthur)

**External gate:** conta de advogado no eproc do TJTO. Esta task é a **única** que exige credencial real e **quem a executa é o Arthur**, na máquina dele.

**Files:**
- Modify: `backend/app/connectors/login_profiles.py` (só o perfil EPROC)
- Modify: `docs/superpowers/specs/2026-07-29-login-multissistema-design.md` (§7)

- [ ] **Step 1: Rodar o agente contra o TJTO real**

```powershell
cd backend
$env:CAUSOR_COURT_ALLOW_PROD='1'
.\.venv\Scripts\python.exe -m app.local_agent run
```
Na UI do Causor: Configurações → Acesso aos tribunais → conectar `EPROC · TJTO · 1º grau`. O agente abre o navegador; o Arthur loga.

Expected: um dos dois desfechos, e ambos são informação útil —
- confirma sozinho (`confirmed_by: "selector"`) → os seletores estão certos;
- pede o banner "Já estou logado" → os seletores **não** batem, e o Step 2 corrige.

- [ ] **Step 2: Coletar os seletores reais**

Com a sessão aberta, no DevTools do navegador (F12 → Console), no painel logado:

```javascript
// marcador de autenticado que realmente existe
document.querySelectorAll("a[href*='logout'], a[href*='Sair'], #infraBarraSuperior").length
// confirmar que NÃO há campo de senha no painel
document.querySelectorAll("input[type='password']").length   // deve ser 0
```

Anotar quais seletores retornaram > 0 no painel e quais retornam > 0 na tela de login.

- [ ] **Step 3: Atualizar o perfil EPROC com o observado**

Em `backend/app/connectors/login_profiles.py`, substituir o registro do EPROC pelos seletores confirmados e promover:

```python
_register(
    LoginProfile(
        sistema="EPROC",
        authenticated_selectors=("<seletores confirmados no Step 2>",),
        login_selectors=("<seletores confirmados no Step 2>",),
        captcha_selectors=("iframe[src*='recaptcha']", ".g-recaptcha"),
        verificado=True,
        evidencia="TJTO 1º grau, eproc V2, observado em <data> por Arthur",
    )
)
```

- [ ] **Step 4: Confirmar que a trava de evidência aceita**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_login_profiles.py -q
```
Expected: PASS — `test_perfil_verificado_exige_evidencia_registrada` só passa com `evidencia` preenchida.

- [ ] **Step 5: Reconectar e confirmar detecção automática**

Repetir o Step 1. Expected: `confirmed_by: "selector"`, sem banner.

- [ ] **Step 6: Atualizar o spec e commitar**

Em `docs/superpowers/specs/2026-07-29-login-multissistema-design.md` §7, marcar EPROC como verificado com a data real.

```bash
git add backend/app/connectors/login_profiles.py docs/superpowers/specs/2026-07-29-login-multissistema-design.md
git commit -m "feat(login): perfil EPROC verificado contra o TJTO real"
```

**Deliverable:** o primeiro perfil do Causor confirmado contra tribunal real — e o primeiro pedaço de conector que deixa de ser suposição.

---

## Self-review (cobertura do spec)

| Requisito do spec | Task |
|---|---|
| §3.1 falso negativo (`handlers.py`) | 1 (regra), 3 (uso) |
| §3.2 falso positivo (`pje/pages/login.py`) | 1 (regra), 4 (dedup) |
| §3.3 seletor em vez de substring | 1, 3 |
| §4.1 `login_profiles.py` + função pura | 1 |
| §4.2 agente por seletor + `check_court_session` | 3, 5 |
| §4.3 dedup do conector PJe | 4 |
| §4.4 `request_session_check` / `apply_session_check_result` + gatilhos | 5 |
| §4.5 banner de confirmação humana | 6 |
| §5 vieses de PJe (2 defaults + trava de produção) | 7 |
| §6 MNI sem segundo ponto de decisão | 5 (docstring + exclusão por construção) |
| §7 política de `verificado` + trava por evidência | 1 (trava), 8 (promoção) |
| §8 testes puros / simulador / live | 1, 2, 8 |
| §11 lock de perfil vira `inconclusive` | 5 |

**Correção feita em relação ao spec:** §7 previa EPROC nascendo `verificado=True`. Como a observação do portal real ainda não aconteceu, os quatro perfis nascem `verificado=False` na Task 1, e a Task 8 promove o EPROC após validação live. Marcar antes seria o erro de 2026-07-21 que o próprio spec existe para prevenir.

**Fora de escopo confirmado:** leitura de autos, protocolo, varredura de webservice multi-sistema, cron periódico de checagem, remoção do `PjeBrowserSession` morto.
