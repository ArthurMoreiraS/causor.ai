"""Vocabulário único de sistema processual.

O DataJud devolve o rótulo que cada tribunal reporta — e eles divergem entre
si. Gravar o valor bruto fragmentava o filtro da UI ("Eproc" e "EPROC" viravam
duas opções, nenhuma mostrando todos os processos) e chegou a gravar
"Inválido" como se fosse um sistema.
"""

from app.capture.normalize import normalizar_sistema


def test_variacoes_de_caixa_convergem():
    for bruto in ("EPROC", "Eproc", "eproc", "  ePrOc  "):
        assert normalizar_sistema(bruto) == "EPROC", bruto


def test_pje_em_qualquer_caixa():
    for bruto in ("PJe", "PJE", "pje"):
        assert normalizar_sistema(bruto) == "PJe", bruto


def test_esaj_com_e_sem_hifen():
    for bruto in ("e-SAJ", "eSAJ", "ESAJ", "SAJ", "saj"):
        assert normalizar_sistema(bruto) == "e-SAJ", bruto


def test_projudi():
    for bruto in ("Projudi", "PROJUDI", "projudi"):
        assert normalizar_sistema(bruto) == "Projudi", bruto


def test_invalido_do_datajud_nao_vira_sistema():
    """O STJ reportou 'Inválido' e isso foi parar no filtro como se fosse um
    sistema processual. Não mapeia -> None -> o registro decide."""
    for bruto in ("Inválido", "Invalido", "INVÁLIDO", "não informado", "-"):
        assert normalizar_sistema(bruto) is None, bruto


def test_vazio_e_none():
    assert normalizar_sistema(None) is None
    assert normalizar_sistema("") is None
    assert normalizar_sistema("   ") is None


def test_rotulo_desconhecido_nao_e_inventado():
    """Sistema que ainda não conhecemos não pode virar palpite silencioso."""
    assert normalizar_sistema("SistemaNovoDoTribunal") is None


def test_saida_pertence_ao_vocabulario_canonico():
    canonicos = {"PJe", "e-SAJ", "EPROC", "Projudi"}
    for bruto in ("pje", "eproc", "saj", "projudi", "Inválido", None):
        resultado = normalizar_sistema(bruto)
        assert resultado is None or resultado in canonicos
