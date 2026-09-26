"""Immutable approved packages shared by export and future court execution."""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import re
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import func, select

from app.agent.work_service import require_current_evidence
from app.filing.approval import _inputs, approve_snapshot, prepare_snapshot
from app.sor import models as m
from app.storage.objects import get_object_store

MAX_PACKAGE_BYTES = 200 * 1024 * 1024


def safe_name(value: str) -> str:
    value = re.sub(r"[^\w .()-]", "_", value, flags=re.UNICODE).strip(" .")[:180]
    return (value or "documento") if value.lower().endswith(".pdf") else (value or "documento") + ".pdf"


def package_current(session, package, *, require_approval: bool = False):
    work = session.get(m.TrabalhoJuridico, package.trabalho_id) if package.trabalho_id else None
    draft = session.get(m.Peticao, package.peticao_id) if package.peticao_id else None
    if work is None or draft is None or work.peticao_id != draft.id:
        raise ValueError("O trabalho ou a minuta mudou. Prepare um novo pacote.")
    latest = session.scalar(select(func.max(m.PacoteProtocolo.versao)).where(m.PacoteProtocolo.trabalho_id == work.id))
    if latest != package.versao:
        raise ValueError("Existe uma versão mais recente do pacote. Confira e aprove a versão atual.")
    _, evidence = require_current_evidence(session, work)
    fingerprint, _ = _inputs(session, draft)
    if fingerprint != package.dados["pdf_input_sha256"] or evidence["work_fingerprint"] != package.dados["work_fingerprint"]:
        raise ValueError("Conteúdo, objetivo, destino ou timbrado mudou. Prepare e aprove um novo pacote.")
    if evidence["source_fingerprint"] != package.dados["source_fingerprint"] or not evidence.get("conferida"):
        raise ValueError("Os documentos mudaram. Revise o contexto e prepare um novo pacote.")
    if require_approval:
        snapshot = (draft.dossie or {}).get("pdf_snapshot") or {}
        if (package.aprovada_em is None or draft.status not in {"aprovada", "protocolada"}
                or not snapshot.get("aprovado") or snapshot.get("input_sha256") != package.dados["pdf_input_sha256"]):
            raise ValueError("A aprovação foi invalidada. Confira e aprove o pacote novamente.")
    return work, draft


def item_bytes(package, item):
    key = item["storage_key"]
    if not key.startswith(f"tenant/{package.escritorio_id}/"):
        raise ValueError("Arquivo fora do escritório do pacote")
    data = get_object_store().get_bytes(key)
    if sha256(data).hexdigest() != item["sha256"] or len(data) != item["size_bytes"]:
        raise ValueError("O arquivo armazenado diverge do pacote. Envio bloqueado.")
    return data


def build_package(session, *, work, target: dict, attachments: list[dict]):
    process, evidence = require_current_evidence(session, work)
    if not work.peticao_id or not evidence.get("conferida"):
        raise ValueError("Gere e revise a minuta com as evidências conferidas antes de preparar o pacote")
    draft = session.get(m.Peticao, work.peticao_id)
    if draft.status in {"protocolada", "protocolando"}:
        raise ValueError("Minuta enviada ou em execução não aceita outro pacote")
    if draft.dossie.get("source_fingerprint") != evidence["source_fingerprint"] or draft.dossie.get("work_fingerprint") != evidence["work_fingerprint"]:
        raise ValueError("A minuta foi gerada com outro contexto. Gere novamente antes de montar o pacote.")
    if target["grau"] != work.grau:
        raise ValueError("O grau do destino deve corresponder ao trabalho revisado")
    if process.tribunal and target["tribunal"].casefold() != process.tribunal.casefold():
        raise ValueError("O tribunal do destino diverge do processo")
    open_attempt = session.scalar(select(m.TentativaProtocolo.id).join(m.PacoteProtocolo).where(
        m.PacoteProtocolo.trabalho_id == work.id,
        m.TentativaProtocolo.status.not_in(["cancelado", "falha_confirmada"])).limit(1))
    if open_attempt:
        raise ValueError("Há uma tentativa em acompanhamento. Reconcilie ou cancele antes de substituir o pacote.")
    snapshot = prepare_snapshot(session, draft)
    pdf = get_object_store().get_bytes(snapshot["object_key"])
    if sha256(pdf).hexdigest() != snapshot["pdf_sha256"]:
        raise ValueError("PDF diverge da revisão armazenada")
    items = [{"nome": "01-peticao.pdf", "tipo": "peticao", "sha256": snapshot["pdf_sha256"],
              "size_bytes": len(pdf), "storage_key": snapshot["object_key"]}]
    valid_versions = {item["documento_arquivo_id"] for item in evidence["inventario"]}
    seen = set()
    for index, attachment in enumerate(attachments, start=2):
        version_id = attachment["versao_id"]
        if version_id in seen or version_id not in valid_versions:
            raise ValueError("Anexo duplicado ou fora do contexto revisado")
        seen.add(version_id)
        version = session.get(m.DocumentoArquivo, version_id)
        document = session.get(m.Documento, version.documento_id) if version else None
        if document is None or document.escritorio_id != work.escritorio_id or document.processo_id != process.id:
            raise ValueError("Anexo não pertence ao processo")
        if version.mime_type != "application/pdf":
            raise ValueError("Este pacote aceita anexos PDF; converta e revise outros formatos antes de anexar")
        data = get_object_store().get_bytes(version.storage_key)
        if sha256(data).hexdigest() != version.sha256:
            raise ValueError("Anexo diverge da versão revisada")
        # Retain approved bytes independently from the mutable document library.
        archive_key = f"tenant/{work.escritorio_id}/filing/{draft.id}/annexes/{version.sha256}.pdf"
        get_object_store().put_bytes(archive_key, data, "application/pdf")
        items.append({"nome": f"{index:02d}-{safe_name(attachment.get('nome') or document.nome)}", "tipo": "anexo",
            "documento_id": document.id, "versao_id": version.id, "sha256": version.sha256,
            "size_bytes": len(data), "storage_key": archive_key})
    if sum(item["size_bytes"] for item in items) > MAX_PACKAGE_BYTES:
        raise ValueError("O pacote excede o limite de 200 MB; reduza os anexos após conferência")
    values = {"destino": {**target, "numero_processo": process.numero}, "items": items,
              "pdf_input_sha256": snapshot["input_sha256"], "source_fingerprint": evidence["source_fingerprint"],
              "work_fingerprint": evidence["work_fingerprint"]}
    digest = sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    previous = session.scalar(select(m.PacoteProtocolo).where(m.PacoteProtocolo.trabalho_id == work.id).order_by(m.PacoteProtocolo.versao.desc()).limit(1))
    if previous and previous.fingerprint == digest:
        return previous
    package = m.PacoteProtocolo(escritorio_id=work.escritorio_id, trabalho_id=work.id, peticao_id=draft.id,
        versao=(previous.versao + 1 if previous else 1), fingerprint=digest, dados=values)
    session.add(package)
    session.flush()
    return package


def approve_package(session, *, package, user_id: int):
    _, draft = package_current(session, package)
    if draft.status in {"protocolada", "protocolando"}:
        raise ValueError("A minuta já está em envio ou foi enviada")
    for item in package.dados["items"]:
        item_bytes(package, item)
    approve_snapshot(session, draft)
    draft.status = "aprovada"
    draft.aprovada_por = user_id
    package.aprovada_por = user_id
    package.aprovada_em = datetime.now(timezone.utc)


def export_package(session, package) -> bytes:
    package_current(session, package, require_approval=True)
    if package.aprovada_em is None:
        raise ValueError("Confira e aprove o pacote antes de exportar para envio")
    output = BytesIO()
    manifest = {"pacote": package.id, "versao": package.versao, "fingerprint": package.fingerprint,
                "destino": package.dados["destino"], "aprovado_em": package.aprovada_em.isoformat(),
                "arquivos": [{k: v for k, v in item.items() if k != "storage_key"} for item in package.dados["items"]]}
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        approved = approved_contract(package)
        for item in approved.files:
            archive.writestr(item.name, item.content)
        archive.writestr("INDICE-PARA-CONFERENCIA-NAO-ANEXAR.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return output.getvalue()


def approved_contract(package):
    """No database mutation and no court routing. Real executors still require homologation."""
    from app.filing.package_contract import ApprovedFile, ApprovedPackage
    if package.aprovada_em is None:
        raise ValueError("Pacote não aprovado")
    result = ApprovedPackage(package.id, package.fingerprint, tuple(sorted(package.dados["destino"].items())),
        tuple(ApprovedFile(item["nome"], item_bytes(package, item), item["sha256"]) for item in package.dados["items"]))
    result.verify(fingerprint=package.fingerprint, destination=package.dados["destino"])
    return result
