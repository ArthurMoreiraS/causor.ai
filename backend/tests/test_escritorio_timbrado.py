"""Colunas de timbrado no Escritorio persistem no SOR."""

from app.sor import models


def test_escritorio_persiste_campos_de_timbrado(db_session):
    esc = models.Escritorio(
        nome="Esc",
        timbrado_logo=b"\x89PNG\r\n\x1a\nfake",
        timbrado_logo_mime="image/png",
        timbrado_cabecalho="Av. Paulista, 1000",
        timbrado_rodape="OAB/SP 123.456",
    )
    db_session.add(esc)
    db_session.flush()
    db_session.expire(esc)

    salvo = db_session.get(models.Escritorio, esc.id)
    assert salvo.timbrado_logo == b"\x89PNG\r\n\x1a\nfake"
    assert salvo.timbrado_logo_mime == "image/png"
    assert salvo.timbrado_cabecalho == "Av. Paulista, 1000"
    assert salvo.timbrado_rodape == "OAB/SP 123.456"
