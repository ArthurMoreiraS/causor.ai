"""Um 500 precisa chegar ao browser COMO 500, não como falha de rede.

O `ServerErrorMiddleware` do Starlette fica por fora do `CORSMiddleware`, então
uma exceção não tratada sai sem `Access-Control-Allow-Origin`. O browser não
consegue ler essa resposta e reporta `TypeError: Failed to fetch` — que o
`humanError` do frontend traduz para "verifique sua internet". Resultado: o
advogado vai conferir o wi-fi enquanto o servidor está quebrado.
"""

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.settings import settings

ORIGIN = settings.cors_origins.split(",")[0].strip()


def _app_with_boom() -> TestClient:
    app = create_app()

    @app.get("/_boom_test")
    def _boom():
        raise RuntimeError("falha interna qualquer")

    return TestClient(app, raise_server_exceptions=False)


def test_erro_interno_responde_500_com_cabecalho_cors():
    client = _app_with_boom()

    response = client.get("/_boom_test", headers={"Origin": ORIGIN})

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_erro_interno_devolve_json_sem_vazar_a_excecao():
    client = _app_with_boom()

    response = client.get("/_boom_test", headers={"Origin": ORIGIN})

    body = response.json()
    assert body["detail"]["code"] == "internal_error"
    # Mensagem de exceção pode conter caminho, SQL ou segredo: nunca sai na resposta.
    assert "falha interna qualquer" not in response.text
