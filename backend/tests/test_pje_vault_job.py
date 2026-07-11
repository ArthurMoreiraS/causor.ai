"""Job de protocolo sem cookie no backend: sessão vem do agente local.

O vault guarda apenas referências de assinatura (``cloud_cert``); o gate de
sessão do tribunal usa ``CourtSessionState`` alimentado pelo login no agente.
"""

from app.connectors.pje.connector import PjeFilingCheckpoint
from app.queue.jobs import confirm_manual_protocol, run_pje_protocol_job
from app.sor import models
from app.vault.service import store_signature_reference
from tests.conftest import seed_connected_court_session, seed_filing_ready


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
    seed_filing_ready(db_session, peticao)
    return usuario, peticao


class InspectingConnector:
    def __init__(self):
        self.package = None

    def prepare_filing(self, package, *, submit=False):
        self.package = package
        return PjeFilingCheckpoint(
            checkpoint="ready_to_sign",
            modo="pje_assistido_playwright",
            irreversible=False,
            evidence={"states": ["ready_to_sign"]},
        )


def test_job_runs_without_cookie_when_agent_session_connected(db_session):
    usuario, peticao = _seed_approved_pje_petition(db_session)
    seed_connected_court_session(
        db_session, escritorio_id=peticao.escritorio_id, sistema="PJe",
        tribunal="TJSP", grau="1",
    )
    connector = InspectingConnector()

    job = run_pje_protocol_job(
        db_session,
        peticao.id,
        usuario_id=usuario.id,
        connector=connector,
        submit=False,
    )

    assert job.status == "completed"
    # O pacote não carrega mais cookie/sessão; o agente usa o perfil local.
    assert connector.package.storage_state is None
    assert connector.package.pdf_bytes.startswith(b"%PDF")
    assert "storage_state" not in str(job.payload)
    assert "cookie" not in str(job.resultado).lower()


def _audit_rows(session, peticao_id):
    return [
        a
        for a in session.query(models.AuditLog).all()
        if a.entidade == "peticao" and a.entidade_id == peticao_id
    ]


def test_job_attaches_signature_handoff_and_leaks_no_secret(db_session):
    usuario, peticao = _seed_approved_pje_petition(db_session)
    seed_connected_court_session(
        db_session, escritorio_id=peticao.escritorio_id, sistema="PJe",
        tribunal="TJSP", grau="1",
    )

    job = run_pje_protocol_job(
        db_session,
        peticao.id,
        usuario_id=usuario.id,
        connector=InspectingConnector(),
        submit=False,
    )

    handoff = job.resultado["evidence"]["handoff"]
    assert handoff["acoes"] == ["abrir_pje", "ja_assinei", "cancelar"]
    assert handoff["mensagem"]
    # Sem credencial de assinatura -> handoff generico.
    assert handoff["provedor"] == "generico"
    assert "storage_state" not in str(job.resultado)
    audits = _audit_rows(db_session, peticao.id)
    assert "storage_state" not in str([a.detalhe for a in audits])


def test_job_birdid_manual_handoff_without_session(db_session):
    # Handoff manual não abre o tribunal: funciona sem sessão conectada.
    usuario, peticao = _seed_approved_pje_petition(db_session)
    credencial = store_signature_reference(
        db_session,
        usuario_id=usuario.id,
        provedor="birdid",
        external_ref="adv@birdid.example",
    )

    job = run_pje_protocol_job(
        db_session, peticao.id, credencial_id=credencial.id, submit=False
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
