"""Build filing packages from SOR rows."""

from __future__ import annotations

from app.connectors.pje.connector import PjeFilingPackage
from app.sor import models


def build_pje_package(
    peticao: models.Peticao,
    *,
    credencial_id: int | None = None,
) -> PjeFilingPackage:
    processo = peticao.processo
    return PjeFilingPackage(
        peticao_id=peticao.id,
        processo_id=processo.id,
        numero_processo=processo.numero,
        tribunal=processo.tribunal,
        orgao_julgador=processo.orgao_julgador,
        tipo_peticao=peticao.tipo,
        conteudo=peticao.conteudo,
        credencial_id=credencial_id,
    )
