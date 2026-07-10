"""Configuração local do agente (máquina do advogado).

O arquivo ``agent.json`` guarda apenas dados não-secretos (URL da API, id e
nome da instalação). O token do agente vai para o keyring do Windows; nunca
para arquivo, log ou Git.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

import keyring

_SERVICE = "causor-agent"


def config_root() -> Path:
    base = os.environ.get("CAUSOR_AGENT_HOME")
    if base:
        return Path(base)
    local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local_app_data) / "Causor"


def profiles_root() -> Path:
    return config_root() / "profiles"


def _config_file() -> Path:
    return config_root() / "agent.json"


@dataclass
class AgentConfig:
    api_url: str
    installation_id: int
    installation_name: str


def save_config(config: AgentConfig) -> None:
    path = _config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")


def load_config() -> AgentConfig | None:
    path = _config_file()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return AgentConfig(
        api_url=data["api_url"],
        installation_id=int(data["installation_id"]),
        installation_name=data["installation_name"],
    )


def save_token(installation_id: int, token: str) -> None:
    keyring.set_password(_SERVICE, str(installation_id), token)


def load_token(installation_id: int) -> str | None:
    return keyring.get_password(_SERVICE, str(installation_id))


def delete_token(installation_id: int) -> None:
    try:
        keyring.delete_password(_SERVICE, str(installation_id))
    except keyring.errors.PasswordDeleteError:
        pass
