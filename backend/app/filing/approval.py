"""PDF persistido por versão. Download e envio reutilizam os bytes aprovados."""

from dataclasses import asdict
from hashlib import sha256
import json

from app.filing.render import render_minuta_pdf
from app.filing.timbrado import load_timbrado
from app.storage.objects import get_object_store


class ApprovalSnapshotError(ValueError):
    pass


def _inputs(session, petition):
    process = petition.processo
    letterhead = load_timbrado(session, petition.escritorio_id)
    data = {
        "conteudo": petition.conteudo or "", "tipo": petition.tipo,
        "processo": process.numero, "tribunal": process.tribunal,
        "sistema": process.sistema, "orgao": process.orgao_julgador,
        "grau": (petition.dossie or {}).get("grau", "1"), "anexos": [],
        "source_fingerprint": (petition.dossie or {}).get("source_fingerprint"),
        "revisao_conteudo": (petition.dossie or {}).get("revisao_conteudo", 0),
        "timbrado": asdict(letterhead) if letterhead else None,
    }
    if data["timbrado"] and data["timbrado"]["logo"]:
        data["timbrado"]["logo"] = sha256(data["timbrado"]["logo"]).hexdigest()
    return sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), letterhead


def prepare_snapshot(session, petition) -> dict:
    fingerprint, letterhead = _inputs(session, petition)
    previous = (petition.dossie or {}).get("pdf_snapshot")
    if previous and previous.get("input_sha256") == fingerprint:
        return previous
    process = petition.processo
    pdf = render_minuta_pdf(petition.conteudo or "", meta={
        "processo": process.numero, "tipo": petition.tipo, "tribunal": process.tribunal,
    }, timbrado=letterhead)
    digest = sha256(pdf).hexdigest()
    key = f"tenant/{petition.escritorio_id}/filing/{petition.id}/{digest}.pdf"
    get_object_store().put_bytes(key, pdf, "application/pdf")
    snapshot = {"input_sha256": fingerprint, "pdf_sha256": digest, "object_key": key,
                "grau": (petition.dossie or {}).get("grau", "1"), "anexos": [], "aprovado": False}
    petition.dossie = {**(petition.dossie or {}), "pdf_snapshot": snapshot}
    return snapshot


def approve_snapshot(session, petition) -> dict:
    work_id = (petition.dossie or {}).get("trabalho_id")
    if work_id:
        from app.sor import models
        from app.agent.work_service import require_current_evidence
        work = session.get(models.TrabalhoJuridico, work_id)
        if work is None or work.peticao_id != petition.id or work.escritorio_id != petition.escritorio_id:
            raise ApprovalSnapshotError("A minuta não é a versão atual deste trabalho")
        _, evidence = require_current_evidence(session, work)
        if (not evidence.get("conferida")
                or evidence["work_fingerprint"] != petition.dossie.get("work_fingerprint")
                or evidence["source_fingerprint"] != petition.dossie.get("source_fingerprint")):
            raise ApprovalSnapshotError("Confira novamente o contexto e gere a minuta do trabalho atual")
    snapshot = {**prepare_snapshot(session, petition), "aprovado": True}
    petition.dossie = {**(petition.dossie or {}), "pdf_snapshot": snapshot}
    return snapshot


def snapshot_pdf(session, petition, *, require_approved: bool = True, validate_current: bool = True) -> bytes:
    snapshot = (petition.dossie or {}).get("pdf_snapshot")
    if not snapshot or (require_approved and not snapshot.get("aprovado")):
        raise ApprovalSnapshotError("Revise o PDF e aprove esta versão antes do envio")
    fingerprint, _ = _inputs(session, petition)
    if validate_current and snapshot.get("input_sha256") != fingerprint:
        raise ApprovalSnapshotError("Conteúdo, destino ou timbrado mudou; revise e aprove novamente")
    key = snapshot.get("object_key", "")
    if not key.startswith(f"tenant/{petition.escritorio_id}/filing/{petition.id}/"):
        raise ApprovalSnapshotError("Arquivo fora do escopo da petição")
    pdf = get_object_store().get_bytes(key)
    if sha256(pdf).hexdigest() != snapshot.get("pdf_sha256"):
        raise ApprovalSnapshotError("O PDF armazenado diverge da versão aprovada")
    return pdf
