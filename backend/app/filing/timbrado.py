"""Timbrado por escritório: dados para o renderer e normalização do logo.

O renderer é função pura; este módulo faz a ponte com o SOR (load_timbrado)
e garante na entrada (normalize_logo) que todo logo armazenado é um PNG
pequeno e válido — o render nunca falha por imagem ruim e o PDF fica dentro
dos limites de tamanho dos tribunais.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image
from sqlalchemy.orm import Session

from app.sor import models

MAX_LOGO_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_LOGO_LARGURA_PX = 1000
# Limites de linhas do timbrado: fonte única usada pelo validador de entrada
# (app.api.schemas) e pelo clamp defensivo do renderer (app.filing.render).
# Sem cap, fpdf2 não tem guarda contra recursão em header()/footer() quando o
# conteúdo não cabe na página (RecursionError) e o rodapé pode ser empurrado
# para fora da área visível.
MAX_CABECALHO_LINHAS = 8
MAX_RODAPE_LINHAS = 4


class LogoInvalidoError(ValueError):
    """Upload de logo rejeitado (formato, tamanho ou bytes corrompidos)."""


@dataclass(frozen=True)
class TimbradoEscritorio:
    nome: str
    cabecalho: str | None = None
    rodape: str | None = None
    logo: bytes | None = None
    logo_mime: str | None = None


def normalize_logo(data: bytes) -> bytes:
    """Valida e re-encoda o logo para PNG sem metadados, largura <= 1000px."""
    if len(data) > MAX_LOGO_UPLOAD_BYTES:
        raise LogoInvalidoError("logo acima do limite de 2MB")
    eh_png = data.startswith(b"\x89PNG\r\n\x1a\n")
    eh_jpeg = data.startswith(b"\xff\xd8\xff")
    if not (eh_png or eh_jpeg):
        raise LogoInvalidoError("logo deve ser PNG ou JPEG")
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                img = img.convert("RGB")
            if img.width > MAX_LOGO_LARGURA_PX:
                proporcao = MAX_LOGO_LARGURA_PX / img.width
                img = img.resize((MAX_LOGO_LARGURA_PX, max(1, round(img.height * proporcao))))
            saida = io.BytesIO()
            img.save(saida, format="PNG", optimize=True)
            return saida.getvalue()
    except LogoInvalidoError:
        raise
    except Exception as exc:
        raise LogoInvalidoError("logo inválido ou corrompido") from exc


def load_timbrado(session: Session, escritorio_id: int | None) -> TimbradoEscritorio | None:
    """Monta o timbrado do escritório; None quando nada foi configurado."""
    if escritorio_id is None:
        return None
    esc = session.get(models.Escritorio, escritorio_id)
    if esc is None:
        return None
    if not (esc.timbrado_logo or esc.timbrado_cabecalho or esc.timbrado_rodape):
        return None
    return TimbradoEscritorio(
        nome=esc.nome,
        cabecalho=esc.timbrado_cabecalho,
        rodape=esc.timbrado_rodape,
        logo=esc.timbrado_logo,
        logo_mime=esc.timbrado_logo_mime,
    )
