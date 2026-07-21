"""Driver de leitura MNI: contrato CourtReaderDriver sobre o cliente SOAP.

A enumeração vem inteira numa chamada (MNI não pagina); ``cursor_complete``
só é True com resposta ``sucesso``. O fingerprint cobre id/tipo/dataHora/
mimetype ordenados — mudança no conjunto entre as duas enumerações reprova a
captura no ``finalize_capture`` do Plano 2.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256

from app.connectors.contracts import (
    CourtDocumentRef,
    CourtManifestSnapshot,
    CourtTarget,
)
from app.connectors.mni.client import MniDocumentoMeta
from app.settings import settings


def _parse_data(data_hora: str | None) -> date | None:
    if not data_hora or len(data_hora) < 8:
        return None
    try:
        return datetime.strptime(data_hora[:8], "%Y%m%d").date()
    except ValueError:
        return None


class MniReaderDriver:
    sistema = "MNI"

    def __init__(self, client, *, batch_size: int | None = None):
        self._client = client
        self._batch = batch_size or settings.mni_download_batch
        self._cache: dict[str, bytes] = {}

    def enumerate_documents(self, target: CourtTarget) -> CourtManifestSnapshot:
        result = self._client.consultar_processo(target.numero_processo)
        refs = tuple(
            self._to_ref(meta, ordem) for ordem, meta in enumerate(result.documentos, start=1)
        )
        fingerprint = sha256(
            "|".join(
                f"{m.id};{m.tipo};{m.data_hora};{m.mimetype}"
                for m in sorted(result.documentos, key=lambda m: m.id)
            ).encode("utf-8")
        ).hexdigest()
        return CourtManifestSnapshot(
            target=target,
            documentos=refs,
            cursor_complete=result.sucesso,
            source_fingerprint=f"sha256:{fingerprint}",
            captured_at=datetime.now(timezone.utc),
            evidence={
                "fonte": "mni",
                "documentos": len(refs),
                "conteudo_inline": result.conteudo_inline,
                "mensagem": result.mensagem,
            },
        )

    def prefetch(self, target: CourtTarget, refs: tuple[CourtDocumentRef, ...]) -> None:
        pending = [ref.external_id for ref in refs if ref.external_id not in self._cache]
        for start in range(0, len(pending), self._batch):
            batch = pending[start : start + self._batch]
            self._cache.update(self._client.baixar_documentos(target.numero_processo, batch))

    def download_document(self, target: CourtTarget, ref: CourtDocumentRef) -> bytes:
        if ref.external_id not in self._cache:
            self._cache.update(
                self._client.baixar_documentos(target.numero_processo, [ref.external_id])
            )
        return self._cache.pop(ref.external_id)

    @staticmethod
    def _to_ref(meta: MniDocumentoMeta, ordem: int) -> CourtDocumentRef:
        return CourtDocumentRef(
            external_id=meta.id,
            nome=(meta.descricao or meta.id)[:255],
            tipo=meta.tipo,
            ordem=ordem,
            data_documento=_parse_data(meta.data_hora),
            sigiloso=meta.nivel_sigilo > 0,
            mime_type=meta.mimetype,
            size_hint=None,
            download_ref=meta.id,
            parent_external_id=meta.parent_id,
        )
