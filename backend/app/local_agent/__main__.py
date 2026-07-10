"""CLI do agente local: ``pair``, ``login`` e ``run``.

Roda na máquina do advogado. O token fica no keyring do Windows; o perfil de
navegador (sessão do tribunal) fica em ``%LOCALAPPDATA%\\Causor\\profiles``.
"""

from __future__ import annotations

import argparse
import sys

from app.local_agent import config as agent_config
from app.local_agent.client import AgentApiClient, AgentApiError
from app.local_agent.worker import AgentWorker

AGENT_VERSION = "0.1.0"


def _cmd_pair(args: argparse.Namespace) -> int:
    try:
        paired = AgentApiClient.pair(
            args.api,
            code=args.code,
            installation_name=args.name,
            version=AGENT_VERSION,
        )
    except AgentApiError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    installation = paired["installation"]
    agent_config.save_config(
        agent_config.AgentConfig(
            api_url=args.api,
            installation_id=installation["id"],
            installation_name=installation["nome"],
        )
    )
    agent_config.save_token(installation["id"], paired["token"])
    print(
        f"pareado: instalacao #{installation['id']} ({installation['nome']}); "
        "token salvo no keyring do Windows"
    )
    return 0


def _cmd_login(args: argparse.Namespace) -> int:
    from app.local_agent.browser import persistent_court_context

    print(
        f"abrindo {args.system} · {args.court} · {args.degree}º grau — "
        "faça login no portal; a sessão fica salva no perfil local deste computador."
    )
    with persistent_court_context(
        root=agent_config.profiles_root(),
        sistema=args.system,
        tribunal=args.court,
        grau=args.degree,
        url=args.url,
        headed=True,
    ) as (_context, page):
        print("pressione Enter aqui quando terminar o login...")
        input()
        print(f"sessão salva no perfil local (última URL: {page.url})")
    return 0


def _cmd_run(_args: argparse.Namespace) -> int:
    config = agent_config.load_config()
    if config is None:
        print("agente nao pareado; rode `python -m app.local_agent pair` antes", file=sys.stderr)
        return 1
    token = agent_config.load_token(config.installation_id)
    if not token:
        print("token nao encontrado no keyring; refaça o pareamento", file=sys.stderr)
        return 1
    client = AgentApiClient(config.api_url, token)
    worker = AgentWorker(client)
    print(f"agente #{config.installation_id} ({config.installation_name}) aguardando comandos…")
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        print("encerrado")
    finally:
        client.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.local_agent")
    sub = parser.add_subparsers(dest="command", required=True)

    pair = sub.add_parser("pair", help="parear este computador com o Causor")
    pair.add_argument("--api", required=True, help="URL do backend Causor")
    pair.add_argument("--code", required=True, help="código de pareamento exibido no Causor")
    pair.add_argument("--name", required=True, help="nome desta instalação")
    pair.set_defaults(func=_cmd_pair)

    login = sub.add_parser("login", help="abrir o portal do tribunal e salvar a sessão local")
    login.add_argument("--system", required=True, help="PJe | e-SAJ | EPROC | Projudi")
    login.add_argument("--court", required=True, help="sigla do tribunal (ex.: TJMG)")
    login.add_argument("--degree", required=True, choices=["1", "2"], help="grau (1 ou 2)")
    login.add_argument("--url", required=True, help="URL de login do portal")
    login.set_defaults(func=_cmd_login)

    run = sub.add_parser("run", help="executar o loop de comandos do agente")
    run.set_defaults(func=_cmd_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
