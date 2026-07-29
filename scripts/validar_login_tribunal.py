"""Valida o perfil de deteccao de login contra o portal real de um tribunal.

Abre o portal na maquina do advogado, espera ele logar e reporta:
  1. o que ``login_profiles`` detecta em cada fase;
  2. quais seletores de autenticado realmente existem no painel logado.

E a ferramenta que promove um ``LoginProfile`` de palpite a ``verificado``:
sem ela, os seletores de sessao autenticada sao suposicao — e suposicao
marcada como verificada foi exatamente o erro de 2026-07-21 com os perfis MNI.

Read-only: nao digita credencial, nao clica em nada, nao envia nada ao
tribunal. So observa a pagina que o proprio advogado abriu.

Uso (de /backend, com a venv):
    .\\.venv\\Scripts\\python.exe ..\\scripts\\validar_login_tribunal.py TJTO 1
    .\\.venv\\Scripts\\python.exe ..\\scripts\\validar_login_tribunal.py TRF1 1
"""

from __future__ import annotations

import sys
import time

# Candidatos a marcador de sessao autenticada. Nao e a tabela de producao — e
# a rede que se lanca no painel real para descobrir o que existe de fato.
CANDIDATOS_AUTENTICADO = [
    "#infraBarraSuperior",
    "#lnkInfraSairSistema",
    "a[href*='acao=logout']",
    "a[href*='logout']",
    "a[href*='Sair']",
    "a[href*='sair']",
    "#painel-usuario",
    "[id*='btnSair']",
    "#usuarioLogado",
    ".sairSistema",
    "#menuPrincipal",
    "#infraAreaTelaD",
    "#divInfraBarraLocalizacao",
    "[id*='Logout']",
    "[class*='logout']",
]

CANDIDATOS_LOGIN = [
    "input[type='password']",
    "#pwdSenha",
    "#txtSenha",
    "#senha",
    "#password",
]

POLL_SECONDS = 2.0
ESPERA_MAXIMA = 300.0


def _visivel(page, seletor: str) -> bool:
    try:
        return page.locator(seletor).first.is_visible(timeout=400)
    except Exception:
        return False


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    tribunal, grau = sys.argv[1].upper(), sys.argv[2]

    from app.capture.court_routing import resolve_route
    from app.connectors.login_profiles import detect_page_state, resolve_login_profile
    from app.local_agent import config as agent_config
    from app.local_agent.browser import persistent_court_context

    route = resolve_route(tribunal, grau)
    if route is None or not route.url_login:
        print(f"ERRO: {tribunal} grau {grau} nao tem url_login no registro.")
        print("Adicione em app/capture/court_routing.py antes de validar.")
        return 1

    profile = resolve_login_profile(route.sistema)
    print(f"tribunal ....... {tribunal} grau {grau}")
    print(f"sistema ........ {route.sistema}")
    print(f"url ............ {route.url_login}")
    if profile is None:
        print("perfil ......... NENHUM (sistema sem LoginProfile registrado)")
    else:
        print(f"perfil ......... verificado={profile.verificado}")
    print()
    print("Abrindo o navegador. Faca o login normalmente; nao feche a janela.")
    print("Quando o painel carregar, este script reporta sozinho.\n")

    with persistent_court_context(
        root=agent_config.profiles_root(),
        sistema=route.sistema,
        tribunal=tribunal,
        grau=grau,
        url=route.url_login,
        headed=True,
    ) as (_context, page):
        deadline = time.monotonic() + ESPERA_MAXIMA
        estado_anterior = None
        while time.monotonic() < deadline:
            na_tela_de_login = any(_visivel(page, s) for s in CANDIDATOS_LOGIN)
            estado = (
                detect_page_state(page, profile) if profile is not None else "sem-perfil"
            )
            if estado != estado_anterior:
                print(f"[{int(time.monotonic() % 10000):5}s] deteccao atual: {estado}")
                estado_anterior = estado
            if not na_tela_de_login and estado != "login":
                break
            time.sleep(POLL_SECONDS)
        else:
            print("\nTempo esgotado — o login nao foi concluido.")
            return 1

        time.sleep(2.0)  # deixa o painel assentar
        print("\n" + "=" * 62)
        print("PAINEL DETECTADO — resultado da validacao")
        print("=" * 62)
        estado_final = (
            detect_page_state(page, profile) if profile is not None else "sem-perfil"
        )
        print(f"\ndeteccao do perfil atual: {estado_final}")
        if estado_final == "authenticated":
            print("  -> OS SELETORES ATUAIS JA FUNCIONAM. Perfil pode ser promovido.")
        else:
            print("  -> os seletores atuais NAO reconhecem este painel; use a lista abaixo.")

        print("\nseletores de AUTENTICADO presentes no painel:")
        achados = [s for s in CANDIDATOS_AUTENTICADO if _visivel(page, s)]
        for seletor in achados:
            print(f"   OK  {seletor}")
        if not achados:
            print("   (nenhum candidato bateu)")

        print("\ncampo de senha ainda visivel? (deve ser NAO):", end=" ")
        print("SIM — cuidado" if any(_visivel(page, s) for s in CANDIDATOS_LOGIN) else "nao")

        try:
            ids = page.evaluate(
                "[...document.querySelectorAll('[id]')].slice(0,40).map(e=>e.id).filter(Boolean)"
            )
            print(f"\nprimeiros ids do painel (para escolher marcador estavel):\n   {ids}")
        except Exception:
            pass

        print("\nMande esta saida para o Claude fechar o perfil.")
        print("A janela fecha em 20s.")
        time.sleep(20)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
