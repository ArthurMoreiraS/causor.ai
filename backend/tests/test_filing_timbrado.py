"""Timbrado: normalização do logo e carga a partir do SOR."""

import io

import pytest
from PIL import Image

from app.filing.timbrado import (
    LogoInvalidoError,
    TimbradoEscritorio,
    load_timbrado,
    normalize_logo,
)
from app.sor import models


def _imagem(formato: str, largura: int = 100, altura: int = 40) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), "navy").save(buf, format=formato)
    return buf.getvalue()


def test_normalize_logo_reencoda_jpeg_para_png():
    resultado = normalize_logo(_imagem("JPEG"))
    assert resultado.startswith(b"\x89PNG")


def test_normalize_logo_redimensiona_acima_de_1000px():
    resultado = normalize_logo(_imagem("PNG", largura=1500, altura=300))
    with Image.open(io.BytesIO(resultado)) as img:
        assert img.width == 1000
        assert img.height == 200


def test_normalize_logo_rejeita_formato_nao_suportado():
    with pytest.raises(LogoInvalidoError):
        normalize_logo(b"GIF89a" + b"\x00" * 32)


def test_normalize_logo_rejeita_acima_de_2mb():
    grande = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024)
    with pytest.raises(LogoInvalidoError):
        normalize_logo(grande)


def test_normalize_logo_rejeita_bytes_corrompidos():
    with pytest.raises(LogoInvalidoError):
        normalize_logo(b"\x89PNG\r\n\x1a\n" + b"lixo")


def test_load_timbrado_sem_configuracao_retorna_none(db_session):
    esc = models.Escritorio(nome="Esc")
    db_session.add(esc)
    db_session.flush()

    assert load_timbrado(db_session, esc.id) is None
    assert load_timbrado(db_session, None) is None


def test_load_timbrado_monta_dataclass(db_session):
    esc = models.Escritorio(
        nome="Moura & Santos",
        timbrado_cabecalho="Av. Paulista, 1000",
        timbrado_rodape="OAB/SP 123.456",
        timbrado_logo=normalize_logo(_imagem("PNG")),
        timbrado_logo_mime="image/png",
    )
    db_session.add(esc)
    db_session.flush()

    timbrado = load_timbrado(db_session, esc.id)

    assert timbrado == TimbradoEscritorio(
        nome="Moura & Santos",
        cabecalho="Av. Paulista, 1000",
        rodape="OAB/SP 123.456",
        logo=esc.timbrado_logo,
        logo_mime="image/png",
    )
