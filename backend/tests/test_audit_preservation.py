from datetime import date

from sqlalchemy import select

from app.api.main import _purge_oab_data
from app.sor import models
from app.sor.seed_demo import seed_demo


def test_oab_cleanup_preserves_existing_audit(db_session, seeded):
    notice = db_session.scalars(select(models.Intimacao)).first()
    notice.payload = {"destinatarioadvogados": [{"advogado": {"numero_oab": "123", "uf_oab": "SP"}}]}
    audit = models.AuditLog(escritorio_id=seeded.escritorio_id, ator="usuario:1",
                            acao="minuta_revisada", entidade="processo", entidade_id=seeded.id,
                            detalhe={"evidencia": "preservar"})
    db_session.add(audit)
    db_session.flush()
    audit_id = audit.id
    counts = _purge_oab_data(db_session, escritorio_id=seeded.escritorio_id, oab="123", uf="SP")
    db_session.flush()
    db_session.expire_all()
    assert counts["processos"] == 1
    assert counts["auditoria"] == 0
    assert db_session.get(models.AuditLog, audit_id).detalhe == {"evidencia": "preservar"}


def test_reseeding_demo_preserves_previous_events(db_session):
    seed_demo(db_session, today=date(2026, 9, 4))
    before = set(db_session.scalars(select(models.AuditLog.id)))
    seed_demo(db_session, today=date(2026, 9, 5))
    after = set(db_session.scalars(select(models.AuditLog.id)))
    assert before < after
