"""TDD do saneamento de texto corrompido na origem (DataJud).

As entradas corrompidas são montadas com ``chr()`` de propósito: escrever o
caractere de controle literal no fonte do teste é frágil (depende do encoding do
arquivo) e ilegível na revisão.
"""

from app.capture.datajud import ProcessoDTO
from app.capture.text import REPLACEMENT_CHAR, sanitize_upstream_text


def _corrompido(prefixo: str, continuacao: int, sufixo: str) -> str:
    """Reproduz o que o DataJud devolve: líder UTF-8 perdido + continuação."""
    return f"{prefixo}{REPLACEMENT_CHAR}{chr(continuacao)}{sufixo}"


def test_reconstroi_letra_com_lider_utf8_perdido():
    # Caso real: STJ, processo 00018704220198140069 (verificado ao vivo).
    assert sanitize_upstream_text(_corrompido("PRESID", 0x8A, "NCIA")) == "PRESIDÊNCIA"


def test_reconstroi_outras_acentuadas_do_portugues():
    # A continuação carrega a caixa da letra: 0x87 -> Ç maiúsculo, 0xA7 -> ç minúsculo.
    assert sanitize_upstream_text(_corrompido("S", 0x89, "RGIO")) == "SÉRGIO"
    assert sanitize_upstream_text(_corrompido("A", 0x87, "AO")) == "AÇAO"
    assert sanitize_upstream_text(_corrompido("A", 0xA7, "ao")) == "Açao"
    assert sanitize_upstream_text(_corrompido("S", 0x83, "O PAULO")) == "SÃO PAULO"
    assert sanitize_upstream_text(_corrompido("S", 0xA3, "o Paulo")) == "São Paulo"


def test_preserva_texto_limpo():
    for limpo in [
        "1ª VICE-PRESIDÊNCIA",
        "Vara Cível de São Paulo",
        "GABINETE 11",
        "Ação de Execução",
    ]:
        assert sanitize_upstream_text(limpo) == limpo


def test_recupera_mojibake_classico():
    mojibake = "AÇÃO".encode("utf-8").decode("cp1252")
    assert sanitize_upstream_text(mojibake) == "AÇÃO"


def test_descarta_marcador_sem_par_recuperavel():
    """Byte perdido sem continuação é irrecuperável — não deixar caixa na UI."""
    assert sanitize_upstream_text(f"PRESID{REPLACEMENT_CHAR}NCIA") == "PRESIDNCIA"


def test_vazio_e_none_passam_intactos():
    assert sanitize_upstream_text(None) is None
    assert sanitize_upstream_text("") == ""


def test_processo_dto_saneia_orgao_julgador_na_ingestao():
    """O saneamento tem de acontecer na borda, senão o lixo entra no SOR e vaza
    para a tela do advogado (foi o que apareceu no piloto)."""
    dto = ProcessoDTO.from_source(
        {
            "numeroProcesso": "00018704220198140069",
            "orgaoJulgador": {"nome": _corrompido("PRESID", 0x8A, "NCIA")},
            "classe": {"nome": _corrompido("A", 0x87, "AO CIVEL")},
        }
    )

    assert dto.orgao_julgador == "PRESIDÊNCIA"
    assert dto.classe == "AÇAO CIVEL"
