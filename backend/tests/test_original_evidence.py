from hashlib import sha256

import pytest

from app.agent.evidence import select_evidence
from app.autos.context import ContextBundle
from app.sor import models as m


def sources(db_session, seeded):
    instance = m.ProcessoInstancia(escritorio_id=seeded.escritorio_id, processo_id=seeded.id, sistema="PJe", tribunal="TJSP", grau="1")
    db_session.add(instance)
    db_session.flush()
    capture = m.CapturaAutos(escritorio_id=seeded.escritorio_id, processo_instancia_id=instance.id, generation=1, status="complete")
    db_session.add(capture)
    db_session.flush()
    documents = []
    for index, content in enumerate(("O pagamento foi integralmente realizado em março.", "Pagamento de outro documento excluído do manifesto.")):
        doc = m.Documento(escritorio_id=seeded.escritorio_id, processo_id=seeded.id, nome=f"arquivo-{index}.pdf")
        db_session.add(doc)
        db_session.flush()
        version = m.DocumentoArquivo(documento_id=doc.id, captura_id=capture.id, sha256=str(index) * 64,
            storage_key=f"evidence/{index}", uri="test", mime_type="application/pdf", size_bytes=10, page_count=900,
            extraction_status="complete", atual=True)
        db_session.add(version)
        db_session.flush()
        chunk = m.DocumentoTrecho(documento_arquivo_id=version.id, pagina=899, indice=0, texto=content,
            texto_sha256=sha256(content.encode()).hexdigest(), char_count=len(content))
        db_session.add(chunk)
        db_session.flush()
        documents.append((doc, version, chunk))
    context = m.ContextoProcesso(escritorio_id=seeded.escritorio_id, processo_id=seeded.id, status="ready",
        source_fingerprint="frozen", inventario=[{"documento_arquivo_id": documents[0][1].id}], citations=[], cobertura={})
    db_session.add(context)
    db_session.flush()
    bundle = ContextBundle(context.id, "frozen", "Inventário do primeiro documento", "Resumo sem menção ao pagamento.", "", ())
    return bundle, documents


def test_recovers_fact_absent_from_summary_and_excludes_non_manifest_version(db_session, seeded):
    bundle, documents = sources(db_session, seeded)
    result = select_evidence(db_session, processo=seeded, bundle=bundle, query="pagamento", max_bytes=8000)
    assert documents[0][2].texto in result.text
    assert documents[1][2].texto not in result.text
    assert result.citations[0]["pagina"] == 899
    assert result.citations[0]["sha256"] == documents[0][1].sha256
    assert result.citations[0]["texto_sha256"]


def test_pinned_source_must_belong_to_snapshot(db_session, seeded):
    bundle, documents = sources(db_session, seeded)
    with pytest.raises(ValueError, match="fonte fixada"):
        select_evidence(db_session, processo=seeded, bundle=bundle, query="", max_bytes=8000,
                        pinned=(documents[1][2].id,))
    result = select_evidence(db_session, processo=seeded, bundle=bundle, query="tema diferente", max_bytes=8000,
                             pinned=(documents[0][2].id,))
    assert result.citations[0]["fixada"]
