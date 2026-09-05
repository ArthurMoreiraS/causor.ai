from app.agent.classifier import ClassificacaoIntimacao
from app.sor import models
import pytest


def test_ambiguous_deadline_is_unknown_instead_of_one_day():
    result = ClassificacaoIntimacao(
        tipo="Ciência", peticao_sugerida="Revisar providência", prazo_dias=0,
        dias_uteis=True, confianca=0.2, resumo="Prazo não identificado",
    )
    assert result.prazo_dias is None


def test_editing_approved_petition_requires_new_approval(client, db_session, seeded):
    petition = models.Peticao(
        processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
        conteudo="Versão aprovada", status="aprovada", aprovada_por=1,
    )
    db_session.add(petition)
    db_session.commit()
    response = client.patch(f"/peticoes/{petition.id}", json={"conteudo": "Nova versão"})
    assert response.status_code == 200
    assert response.json()["status"] == "em_revisao"
    assert response.json()["aprovada_por"] is None


def test_preview_approval_and_download_reuse_exact_pdf(client, db_session, seeded, monkeypatch, tmp_path):
    from app.settings import settings
    from app.filing.approval import snapshot_pdf, ApprovalSnapshotError

    monkeypatch.setattr(settings, "object_store_provider", "localdev")
    monkeypatch.setattr(settings, "object_store_local_path", str(tmp_path))
    petition = models.Peticao(processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
                              conteudo="Texto para revisão", status="rascunho")
    db_session.add(petition)
    db_session.commit()
    preview = client.get(f"/peticoes/{petition.id}/pdf")
    assert preview.status_code == 200
    approved = client.post(f"/peticoes/{petition.id}/approve")
    assert approved.status_code == 200
    pdf = client.get(f"/peticoes/{petition.id}/pdf")
    assert pdf.content == preview.content
    assert snapshot_pdf(db_session, petition) == preview.content
    seeded.tribunal = "OUTRO"
    with pytest.raises(ApprovalSnapshotError):
        snapshot_pdf(db_session, petition)


def test_unknown_deadline_drafts_with_review_warning_without_creating_deadline(
    client, db_session, seeded, monkeypatch
):
    from tests.conftest import seed_ready_context
    from app.agent.drafter import MinutaGerada
    from app.settings import settings

    monkeypatch.setattr(settings, "datajud_api_key", "")

    seed_ready_context(db_session, seeded)
    notice = models.Intimacao(processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
                              fonte="DJEN", fonte_id="incerto", teor="Ciência da juntada.")
    db_session.add(notice)
    db_session.commit()
    classification = ClassificacaoIntimacao(tipo="Ciência", peticao_sugerida="Manifestação",
        prazo_dias=None, dias_uteis=True, confianca=0.2, resumo="Sem prazo identificável")
    monkeypatch.setattr("app.agent.service.classify_intimacao", lambda _: classification)
    monkeypatch.setattr("app.agent.service.draft_peticao", lambda **kw: MinutaGerada(
        contexto_consolidado="Teste", analise_providencia="Revisar necessidade",
        minuta="Proposta", alertas=[], confianca=0.2,
    ))
    result = client.post(f"/intimacoes/{notice.id}/draft")
    assert result.status_code == 200
    assert result.json()["prazo"] is None
    assert result.json()["peticao"]["dossie"]["prazo_revisao_pendente"]
    assert db_session.query(models.Prazo).filter_by(intimacao_id=notice.id).count() == 0
    confirmed = client.post(f"/intimacoes/{notice.id}/prazo", json={
        "data_base": "2024-09-09", "dias": 2, "dias_uteis": True,
        "dias_sem_expediente": ["2024-09-10"],
        "justificativa": "Duração e publicação conferidas pelo advogado no documento.",
    })
    assert confirmed.status_code == 200
    assert confirmed.json()["data_fatal"] == "2024-09-12"
    assert db_session.query(models.AuditLog).filter_by(acao="prazo_confirmado").count() == 1
