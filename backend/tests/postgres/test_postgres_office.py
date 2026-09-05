"""New office workflows against actual migrated FK/locking semantics."""
from tests.test_office_workflows import (  # noqa: F401
    test_client_registration_and_process_link,
    test_notice_becomes_task_without_creating_a_legal_deadline,
    test_task_cannot_reference_other_office,
    test_ai_alert_has_verified_origin_and_is_not_duplicated,
    test_task_listing_paginates_and_does_not_expose_other_office,
    test_changing_client_is_blocked_while_a_draft_is_approved,
    test_task_reopening_and_reassignment_preserve_source,
    test_task_client_follows_process_and_rejects_mismatched_sources,
)

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.office_routes import TarefaIn, create_task
from app.auth.jwt_auth import CurrentUser
from app.sor import models


def test_concurrent_alert_conversion_is_idempotent(pg_engine, db_session, seeded):
    draft = models.Peticao(escritorio_id=seeded.escritorio_id, processo_id=seeded.id,
                           dossie={"alertas": ["Documento ausente"]})
    db_session.add(draft)
    db_session.commit()
    user = db_session.scalars(select(models.Usuario)).first()
    current = CurrentUser(usuario_id=user.id, escritorio_id=seeded.escritorio_id, email=user.email)
    payload = TarefaIn(titulo="Solicitar documento", peticao_id=draft.id,
                       alerta_indice=0, alerta_texto_esperado="Documento ausente")
    barrier = Barrier(2)

    def convert():
        with Session(pg_engine) as session:
            barrier.wait(timeout=5)
            response = Response(status_code=201)
            task = create_task(payload, response, session, current)
            return task.id, response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: convert(), range(2)))
    assert results[0][0] == results[1][0]
    assert sorted(code for _, code in results) == [200, 201]
    assert db_session.scalar(select(func.count()).select_from(models.Tarefa)) == 1


def test_removing_source_detaches_task_without_losing_alert(pg_engine, db_session, seeded):
    draft = models.Peticao(escritorio_id=seeded.escritorio_id, processo_id=seeded.id)
    db_session.add(draft)
    db_session.flush()
    task = models.Tarefa(escritorio_id=seeded.escritorio_id, titulo="Providência", peticao_id=draft.id,
                         origem="alerta_minuta", origem_texto="Comprovante ausente")
    db_session.add(task)
    db_session.commit()
    task_id = task.id
    db_session.execute(delete(models.Peticao).where(models.Peticao.id == draft.id))
    db_session.commit()
    with Session(pg_engine) as session:
        retained = session.get(models.Tarefa, task_id)
        assert retained.peticao_id is None and retained.origem_texto == "Comprovante ausente"
