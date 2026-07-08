"""As listas precisam carregar além do teto antigo de 500 por request.

Alvo ~3k processos/conta: com `le=500` as páginas voltavam a subcontar vs. o
dashboard (Intimações travava em 100, Prazos em 200). Estes testes travam o teto
novo (`le=5000`) — antes o request com limit>500 dava 422.
"""

import pytest


@pytest.mark.parametrize(
    "path", ["/intimacoes", "/prazos", "/peticoes", "/review/queue", "/processos"]
)
def test_listas_aceitam_limite_acima_de_500(client, seeded, path):
    resp = client.get(path, params={"limit": 3000})
    assert resp.status_code == 200
