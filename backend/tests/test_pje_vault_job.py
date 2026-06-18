"""Tests for loading assisted PJe sessions into the filing job."""

from app.connectors.pje.connector import PjeFilingCheckpoint
from app.queue.jobs import confirm_manual_protocol, run_pje_assisted_protocol_job
from app.sor import models
from app.vault.service import (
    load_pje_session_payload,
    store_pje_session_reference,
    store_signature_reference,
)


def _seed_approved_pje_petition(db_session):
    escritorio = models.Escritorio(nome="Escritorio PJe")
    db_session.add(escritorio)
    db_session.flush()
    usuario = models.Usuario(
        escritorio_id=escritorio.id,
        nome="Adv PJe",
        email="pje@example.com",
    )
    db_session.add(usuario)
    db_session.flush()
    processo = models.Processo(
        escritorio_id=escritorio.id,
        numero="0000001-00.2024.8.26.0100",
        tribunal="TJSP",
        sistema="PJe",
    )
    db_session.add(processo)
    db_session.flush()
    peticao = models.Peticao(
        escritorio_id=escritorio.id,
        processo_id=processo.id,
        tipo="Manifestacao",
        conteudo="minuta",
        status="aprovada",
        aprovada_por=usuario.id,
    )
    db_session.add(peticao)
    db_session.flush()
    return usuario, peticao


class InspectingConnector:
    def __init__(self):
        self.package = None

    def prepare_filing(self, package):
        self.package = package
        return PjeFilingCheckpoint(
            checkpoint="ready_to_sign",
            modo="pje_assistido_playwright",
            irreversible=False,
            evidence={"states": ["ready_to_sign"]},
        )


def test_load_pje_session_payload_from_localdev_vault(db_session):
    usuario, _peticao = _seed_approved_pje_petition(db_session)
    storage_state = {"cookies": [{"name": "JSESSIONID", "value": "secret-cookie"}]}
    credencial = store_pje_session_reference(
        db_session,
        usuario_id=usuario.id,
        tribunal="TJSP",
        url_base="https://pje-treinamento.tjsp.jus.br/pje",
        storage_state=storage_state,
    )

    payload = load_pje_session_payload(db_session, credencial_id=credencial.id)

    assert payload["url_base"] == "https://pje-treinamento.tjsp.jus.br/pje"
    assert payload["storage_state"] == storage_state
    assert "secret-cookie" not in credencial.referencia_vault


def test_run_pje_assisted_job_passes_vault_session_to_connector(db_session):
    usuario, peticao = _seed_approved_pje_petition(db_session)
    storage_state = {"cookies": [{"name": "JSESSIONID", "value": "secret-cookie"}]}
    credencial = store_pje_session_reference(
        db_session,
        usuario_id=usuario.id,
        tribunal="TJSP",
        url_base="https://pje-treinamento.tjsp.jus.br/pje",
        storage_state=storage_state,
    )
    connector = InspectingConnector()

    job = run_pje_assisted_protocol_job(
        db_session,
        peticao.id,
        credencial_id=credencial.id,
        connector=connector,
    )

    assert job.status == "completed"
    assert connector.package.pje_base_url == "https://pje-treinamento.tjsp.jus.br/pje"
    assert connector.package.storage_state == storage_state
    assert connector.package.pdf_bytes.startswith(b"%PDF")
    assert "secret-cookie" not in str(job.payload)
    assert "secret-cookie" not in str(job.resultado)


def _audit_rows(session, peticao_id):
    return [
        a
        for a in session.query(models.AuditLog).all()
        if a.entidade == "peticao" and a.entidade_id == peticao_id
    ]


def test_job_attaches_signature_handoff_and_leaks_no_secret(db_session):
    usuario, peticao = _seed_approved_pje_petition(db_session)
    storage_state = {"cookies": [{"name": "JSESSIONID", "value": "secret-cookie"}]}
    credencial = store_pje_session_reference(
        db_session,
        usuario_id=usuario.id,
        tribunal="TJSP",
        url_base="https://pje-treinamento.tjsp.jus.br/pje",
        storage_state=storage_state,
    )

    job = run_pje_assisted_protocol_job(
        db_session,
        peticao.id,
        credencial_id=credencial.id,
        connector=InspectingConnector(),
    )

    handoff = job.resultado["evidence"]["handoff"]
    assert handoff["acoes"] == ["abrir_pje", "ja_assinei", "cancelar"]
    assert handoff["mensagem"]
    # PJeSession is not a signing provider -> generic handoff.
    assert handoff["provedor"] == "generico"
    # No vault secret leaks into result or audit.
    assert "secret-cookie" not in str(job.resultado)
    audits = _audit_rows(db_session, peticao.id)
    assert "secret-cookie" not in str([a.detalhe for a in audits])


def test_job_birdid_manual_handoff_without_session(db_session):
    usuario, peticao = _seed_approved_pje_petition(db_session)
    credencial = store_signature_reference(
        db_session,
        usuario_id=usuario.id,
        provedor="birdid",
        external_ref="adv@birdid.example",
    )

    # No PJe session stored -> connector takes the manual checkpoint path
    # (no browser) and the job still produces a BirdID-tailored handoff.
    job = run_pje_assisted_protocol_job(
        db_session, peticao.id, credencial_id=credencial.id
    )

    assert job.status == "completed"
    handoff = job.resultado["evidence"]["handoff"]
    assert handoff["provedor"] == "birdid"
    assert "BirdID" in handoff["mensagem"]


def test_confirm_manual_protocol_audit_has_provedor_modo(db_session):
    usuario, peticao = _seed_approved_pje_petition(db_session)
    credencial = store_signature_reference(
        db_session,
        usuario_id=usuario.id,
        provedor="birdid",
        external_ref="adv@birdid.example",
    )

    confirm_manual_protocol(
        db_session,
        peticao.id,
        protocolo="PJE-2026-123",
        credencial_id=credencial.id,
    )
    db_session.flush()

    audits = _audit_rows(db_session, peticao.id)
    protocolada = next(a for a in audits if a.acao == "peticao_protocolada")
    assert protocolada.detalhe["provedor"] == "birdid"
    assert protocolada.detalhe["modo"] == "manual_handoff"
