from tests.test_document_library import (  # noqa: F401
    local_store as local_store,
    test_complement_preserves_inventory_links_task_and_versions,
    test_stale_or_mismatched_task_rejects_upload_atomically,
    test_library_is_paginated_and_tenant_scoped,
    test_complement_rejects_incomplete_base,
    test_failed_batch_does_not_change_context_or_task,
    test_supplement_worker_updates_context_and_cited_pages,
)

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.autos.upload import ArquivoEnviado, ingerir_autos_enviados
from app.sor import models
from app.storage.objects import LocalObjectStore
from tests.test_autos_upload_api import PDF_OK, _arquivo


def test_concurrent_complements_preserve_both_files(client, db_session, seeded, local_store, pg_engine):
    assert client.post(f"/processos/{seeded.id}/autos/upload", files=[_arquivo("base.pdf")]).status_code == 200
    instance_id = db_session.scalar(select(models.ProcessoInstancia.id))
    user_id = db_session.scalar(select(models.Usuario.id))
    barrier = Barrier(2)

    def upload(name):
        with Session(pg_engine) as session:
            instance = session.get(models.ProcessoInstancia, instance_id)
            barrier.wait(timeout=5)
            capture = ingerir_autos_enviados(session, processo_instancia=instance, usuario_id=user_id,
                arquivos=[ArquivoEnviado(nome=name, conteudo=PDF_OK)], object_store=LocalObjectStore(local_store), complementar=True)
            generation = capture.generation
            session.commit()
            return generation

    with ThreadPoolExecutor(max_workers=2) as pool:
        generations = list(pool.map(upload, ["primeiro.pdf", "segundo.pdf"]))
    assert sorted(generations) == [2, 3]
    latest = db_session.scalars(select(models.CapturaAutos).order_by(models.CapturaAutos.generation.desc())).first()
    assert latest.expected_count == 3
    assert client.get("/documentos").json()["total"] == 3
