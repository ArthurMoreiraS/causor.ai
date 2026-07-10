from datetime import datetime, timezone

from app.connectors.contracts import (
    CourtDocumentRef,
    CourtManifestSnapshot,
    CourtTarget,
    FilingCheckpoint,
    FilingPackage,
)


def test_contracts_are_system_neutral_and_serializable():
    target = CourtTarget(
        processo_instancia_id=7,
        processo_id=3,
        numero_processo="00000010020248260100",
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://pje.tjmg.jus.br/pje",
    )
    ref = CourtDocumentRef(
        external_id="doc-1",
        nome="Decisão.pdf",
        tipo="Decisão",
        ordem=1,
        data_documento=None,
        sigiloso=False,
        mime_type="application/pdf",
        size_hint=None,
        download_ref="opaque:doc-1",
    )
    snapshot = CourtManifestSnapshot(
        target=target,
        documentos=(ref,),
        cursor_complete=True,
        source_fingerprint="sha256:abc",
        captured_at=datetime.now(timezone.utc),
        evidence={},
    )
    package = FilingPackage(
        peticao_id=9,
        processo_instancia_id=7,
        numero_processo=target.numero_processo,
        tribunal=target.tribunal,
        sistema=target.sistema,
        grau=target.grau,
        tipo_peticao="Manifestação",
        pdf_bytes=b"%PDF-1.4\n%%EOF\n",
    )
    checkpoint = FilingCheckpoint(
        checkpoint="ready_to_sign",
        modo="local_agent",
        irreversible=False,
        evidence={"states": ["minuta_anexada"]},
    )

    assert snapshot.documentos[0].external_id == "doc-1"
    assert package.sistema == "PJe"
    assert checkpoint.irreversible is False
