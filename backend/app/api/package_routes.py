"""Package review, assisted export and explicitly attributed receipt confirmation."""
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.office_routes import audit
from app.api.work_routes import locked_work
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.auth.tenant import get_owned_or_404, tenant_select
from app.capture.normalize import canonical_numero
from app.filing import packages
from app.sor import models as m
from app.sor.db import get_session
from app.storage.objects import get_object_store

router = APIRouter(tags=["pacotes-protocolo"])


class TargetIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    tribunal: str = Field(min_length=2, max_length=50)
    grau: Literal["1", "2"]
    orgao: str = Field(min_length=2, max_length=255)
    tipo_ato: str = Field(min_length=2, max_length=100)
    sistema: str | None = Field(None, max_length=50)


class AttachmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    versao_id: int = Field(ge=1)
    nome: str | None = Field(None, min_length=1, max_length=180)


class PackageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao_trabalho: int = Field(ge=1)
    destino: TargetIn
    anexos: list[AttachmentIn] = Field(default_factory=list, max_length=49)


class FingerprintIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(min_length=64, max_length=64)


class AttemptIn(FingerprintIn):
    idempotency_key: str = Field(min_length=8, max_length=120)


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    versao: int = Field(ge=1)
    protocolo: str = Field(min_length=1, max_length=150)
    data_ato: AwareDatetime


class ReceiptReviewIn(ReportIn):
    numero_processo: str = Field(min_length=20, max_length=25)
    observacoes: str = Field(min_length=20, max_length=3000)


class CancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    versao: int = Field(ge=1)
    motivo: str = Field(min_length=20, max_length=1000)


def conflict(exc):
    return HTTPException(409, str(exc))


def package_out(session, package):
    try:
        packages.package_current(session, package, require_approval=package.aprovada_em is not None)
        current, reason = True, None
    except ValueError as exc:
        current, reason = False, str(exc)
    return {"id": package.id, "trabalho_id": package.trabalho_id, "peticao_id": package.peticao_id,
        "versao": package.versao, "fingerprint": package.fingerprint, "aprovada_em": package.aprovada_em,
        "atual": current, "motivo": reason, "destino": package.dados["destino"],
        "items": [{k: v for k, v in item.items() if k != "storage_key"} for item in package.dados["items"]]}


def locked_package(session, current, package_id):
    package = get_owned_or_404(session, m.PacoteProtocolo, package_id, current)
    if package.trabalho_id:
        work = get_owned_or_404(session, m.TrabalhoJuridico, package.trabalho_id, current)
        locked_work(session, current, work.id, work.versao)
    return session.scalar(tenant_select(m.PacoteProtocolo, current).where(m.PacoteProtocolo.id == package_id)
                          .with_for_update().execution_options(populate_existing=True))


def locked_attempt(session, current, attempt_id, version):
    attempt = get_owned_or_404(session, m.TentativaProtocolo, attempt_id, current)
    package = locked_package(session, current, attempt.pacote_id)
    attempt = session.scalar(tenant_select(m.TentativaProtocolo, current).where(m.TentativaProtocolo.id == attempt_id)
                             .with_for_update().execution_options(populate_existing=True))
    if attempt.versao != version:
        raise HTTPException(409, "A tentativa mudou. Atualize antes de registrar o resultado.")
    return attempt, package


def attempt_out(session, attempt):
    receipts = session.scalars(select(m.ComprovanteProtocolo).where(
        m.ComprovanteProtocolo.escritorio_id == attempt.escritorio_id,
        m.ComprovanteProtocolo.tentativa_id == attempt.id).order_by(m.ComprovanteProtocolo.id.desc())).all()
    return {"id": attempt.id, "pacote_id": attempt.pacote_id, "canal": attempt.canal, "status": attempt.status,
        "versao": attempt.versao, "dados": attempt.dados, "created_at": attempt.created_at,
        "comprovantes": [{"id": r.id, "nome": r.nome, "sha256": r.sha256, "status": r.status, "dados": r.dados} for r in receipts]}


@router.get("/envios-assistidos")
def assisted_history(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                     session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    stmt = select(m.TentativaProtocolo, m.PacoteProtocolo, m.TrabalhoJuridico).join(m.PacoteProtocolo).outerjoin(
        m.TrabalhoJuridico, m.TrabalhoJuridico.id == m.PacoteProtocolo.trabalho_id).where(
        m.TentativaProtocolo.escritorio_id == current.escritorio_id,
        m.PacoteProtocolo.escritorio_id == current.escritorio_id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.execute(stmt.order_by(m.TentativaProtocolo.id.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [{**attempt_out(session, a), "trabalho_id": w.id if w else None,
        "providencia": w.providencia if w else "Trabalho removido", "destino": p.dados["destino"], "versao_pacote": p.versao}
        for a, p, w in rows]}


@router.post("/trabalhos/{work_id}/pacotes", status_code=201)
def create_package(work_id: int, payload: PackageIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    work = locked_work(session, current, work_id, payload.versao_trabalho)
    try:
        package = packages.build_package(session, work=work, target=payload.destino.model_dump(), attachments=[a.model_dump() for a in payload.anexos])
    except ValueError as exc:
        session.rollback()
        raise conflict(exc) from exc
    audit(session, current, "pacote_preparado", "pacote_protocolo", package.id, {"fingerprint": package.fingerprint})
    session.commit()
    return package_out(session, package)


@router.get("/trabalhos/{work_id}/pacotes")
def list_packages(work_id: int, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                  session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    get_owned_or_404(session, m.TrabalhoJuridico, work_id, current)
    rows = session.scalars(tenant_select(m.PacoteProtocolo, current).where(m.PacoteProtocolo.trabalho_id == work_id)
        .order_by(m.PacoteProtocolo.versao.desc()).limit(limit).offset(offset)).all()
    return {"items": [package_out(session, package) for package in rows]}


@router.post("/pacotes/{package_id}/aprovar")
def approve_package(package_id: int, payload: FingerprintIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    package = locked_package(session, current, package_id)
    if package.fingerprint != payload.fingerprint:
        raise HTTPException(409, "O pacote apresentado diverge da versão a aprovar")
    try:
        packages.approve_package(session, package=package, user_id=current.usuario_id)
    except ValueError as exc:
        session.rollback()
        raise conflict(exc) from exc
    audit(session, current, "pacote_aprovado", "pacote_protocolo", package.id, {"fingerprint": package.fingerprint})
    session.commit()
    return package_out(session, package)


@router.get("/pacotes/{package_id}/exportar")
def export_package(package_id: int, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    package = locked_package(session, current, package_id)
    try:
        data = packages.export_package(session, package)
    except ValueError as exc:
        raise conflict(exc) from exc
    audit(session, current, "pacote_exportado", "pacote_protocolo", package.id, {"fingerprint": package.fingerprint})
    session.commit()
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="pacote-{package.id}-v{package.versao}.zip"'})


@router.get("/pacotes/{package_id}/arquivos/{index}")
def preview_item(package_id: int, index: int, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    package = get_owned_or_404(session, m.PacoteProtocolo, package_id, current)
    if not 0 <= index < len(package.dados["items"]):
        raise HTTPException(404, "Arquivo não encontrado")
    try:
        data = packages.item_bytes(package, package.dados["items"][index])
    except ValueError as exc:
        raise conflict(exc) from exc
    audit(session, current, "arquivo_pacote_consultado", "pacote_protocolo", package.id, {"indice": index})
    session.commit()
    return Response(data, media_type="application/pdf")


@router.post("/pacotes/{package_id}/tentativas", status_code=201)
def start_external_attempt(package_id: int, payload: AttemptIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    package = locked_package(session, current, package_id)
    if package.fingerprint != payload.fingerprint or package.aprovada_em is None:
        raise HTTPException(409, "Aprove o pacote exato antes de registrar uma tentativa")
    existing = session.scalar(tenant_select(m.TentativaProtocolo, current).where(m.TentativaProtocolo.idempotency_key == payload.idempotency_key))
    if existing:
        if existing.pacote_id != package_id:
            raise HTTPException(409, "Chave de tentativa já usada em outro pacote")
        return attempt_out(session, existing)
    try:
        packages.package_current(session, package, require_approval=True)
    except ValueError as exc:
        raise conflict(exc) from exc
    active = session.scalar(tenant_select(m.TentativaProtocolo, current).where(m.TentativaProtocolo.pacote_id == package.id,
        m.TentativaProtocolo.status.not_in(["cancelado", "falha_confirmada"])))
    if active:
        return attempt_out(session, active)
    attempt = m.TentativaProtocolo(escritorio_id=current.escritorio_id, pacote_id=package.id,
        idempotency_key=payload.idempotency_key, canal="externo", dados={"iniciada_por": current.usuario_id})
    session.add(attempt)
    session.flush()
    audit(session, current, "envio_externo_iniciado", "tentativa_protocolo", attempt.id, {"pacote_id": package.id})
    session.commit()
    return attempt_out(session, attempt)


@router.get("/pacotes/{package_id}/tentativas")
def list_attempts(package_id: int, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    get_owned_or_404(session, m.PacoteProtocolo, package_id, current)
    rows = session.scalars(tenant_select(m.TentativaProtocolo, current).where(m.TentativaProtocolo.pacote_id == package_id).order_by(m.TentativaProtocolo.id.desc())).all()
    return {"items": [attempt_out(session, attempt) for attempt in rows]}


@router.post("/tentativas/{attempt_id}/informar-envio")
def report_external(attempt_id: int, payload: ReportIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    attempt, _ = locked_attempt(session, current, attempt_id, payload.versao)
    if attempt.status not in {"aguardando_envio_externo", "envio_informado"}:
        raise HTTPException(409, "Esta tentativa não aceita alteração da declaração")
    attempt.status = "envio_informado"
    attempt.dados = {**(attempt.dados or {}), "declaracao": payload.model_dump(mode="json", exclude={"versao"}),
        "declarado_por": current.usuario_id, "declarado_em": datetime.now(timezone.utc).isoformat()}
    attempt.versao += 1
    audit(session, current, "envio_informado", "tentativa_protocolo", attempt.id, {"origem": "declaracao_manual"})
    session.commit()
    return attempt_out(session, attempt)


@router.post("/tentativas/{attempt_id}/cancelar")
def cancel_external(attempt_id: int, payload: CancelIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    attempt, _ = locked_attempt(session, current, attempt_id, payload.versao)
    if attempt.status != "aguardando_envio_externo" or (attempt.dados or {}).get("comprovante_id"):
        raise HTTPException(409, "Há envio informado ou evidência recebida. Reconcilie o resultado; cancelar não desfaz protocolo.")
    attempt.status = "cancelado"
    attempt.versao += 1
    attempt.dados = {**(attempt.dados or {}), "cancelamento": {"motivo": payload.motivo, "usuario_id": current.usuario_id}}
    audit(session, current, "tentativa_cancelada", "tentativa_protocolo", attempt.id, {"motivo": payload.motivo})
    session.commit()
    return attempt_out(session, attempt)


@router.post("/tentativas/{attempt_id}/comprovantes", status_code=201)
async def receive_receipt(attempt_id: int, arquivo: UploadFile, versao: int = Query(..., ge=1),
                          session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    get_owned_or_404(session, m.TentativaProtocolo, attempt_id, current)
    data = await arquivo.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024 or not data.startswith(b"%PDF-"):
        raise HTTPException(422, "Envie um comprovante PDF de até 20 MB")
    import fitz
    try:
        with fitz.open(stream=data, filetype="pdf") as document:
            if document.needs_pass or len(document) > 100:
                raise ValueError("Recibo protegido ou com mais de 100 páginas")
            parts, remaining = [], 100000
            for page in document:
                part = page.get_text()[:remaining]
                parts.append(part)
                remaining -= len(part)
                if remaining <= 0:
                    break
            extracted = "\n".join(parts)
    except Exception as exc:
        raise HTTPException(422, "Comprovante PDF inválido") from exc
    attempt, package = locked_attempt(session, current, attempt_id, versao)
    if attempt.status not in {"aguardando_envio_externo", "envio_informado", "resultado_incerto"}:
        raise HTTPException(409, "A tentativa já está encerrada")
    digest = sha256(data).hexdigest()
    latest = session.get(m.ComprovanteProtocolo, (attempt.dados or {}).get("comprovante_id")) if (attempt.dados or {}).get("comprovante_id") else None
    if latest and latest.sha256 == digest:
        return attempt_out(session, attempt)
    key = f"tenant/{current.escritorio_id}/receipts/{attempt.id}/{digest}.pdf"
    get_object_store().put_bytes(key, data, "application/pdf")
    numbers = sorted({canonical_numero(n) for n in re.findall(r"\b[0-9]{7}-[0-9]{2}\.[0-9]{4}\.[0-9]\.[0-9]{2}\.[0-9]{4}\b|\b[0-9]{20}\b", extracted)})
    expected = canonical_numero(package.dados["destino"]["numero_processo"])
    receipt = m.ComprovanteProtocolo(escritorio_id=current.escritorio_id, tentativa_id=attempt.id,
        sha256=digest, storage_key=key, nome=packages.safe_name(arquivo.filename or "comprovante.pdf"),
        status="divergente" if numbers and expected not in numbers else "recebido",
        dados={"numeros_extraidos": numbers, "numero_esperado": expected, "texto_disponivel": bool(extracted.strip()),
               "protocolos_sugeridos": re.findall(r"(?im)^\s*(?:n[uú]mero\s+(?:do\s+)?)?protocolo\s*[:#]\s*([^\n]{1,150})", extracted)[:5],
               "datas_sugeridas": list(dict.fromkeys(re.findall(r"\b\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?\b", extracted)))[:10],
               "recebido_por": current.usuario_id, "origem": "upload_advogado"})
    session.add(receipt)
    session.flush()
    attempt.dados = {**(attempt.dados or {}), "comprovante_id": receipt.id}
    attempt.versao += 1
    audit(session, current, "comprovante_recebido", "comprovante_protocolo", receipt.id, {"sha256": digest, "tentativa_id": attempt.id})
    session.commit()
    return attempt_out(session, attempt)


@router.get("/comprovantes/{receipt_id}/arquivo")
def receipt_file(receipt_id: int, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    receipt = get_owned_or_404(session, m.ComprovanteProtocolo, receipt_id, current)
    data = get_object_store().get_bytes(receipt.storage_key)
    if sha256(data).hexdigest() != receipt.sha256:
        raise HTTPException(409, "O arquivo diverge do comprovante recebido")
    audit(session, current, "comprovante_consultado", "comprovante_protocolo", receipt.id, {})
    session.commit()
    return Response(data, media_type="application/pdf")


@router.post("/comprovantes/{receipt_id}/conferir")
def confirm_receipt(receipt_id: int, payload: ReceiptReviewIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    receipt = get_owned_or_404(session, m.ComprovanteProtocolo, receipt_id, current)
    attempt, package = locked_attempt(session, current, receipt.tentativa_id, payload.versao)
    if attempt.status not in {"aguardando_envio_externo", "envio_informado", "resultado_incerto"}:
        raise HTTPException(409, "Tentativa encerrada")
    if (attempt.dados or {}).get("comprovante_id") != receipt.id:
        raise HTTPException(409, "Confira o comprovante mais recente desta tentativa")
    if receipt.status == "divergente" or canonical_numero(payload.numero_processo) != canonical_numero(package.dados["destino"]["numero_processo"]):
        raise HTTPException(409, "Comprovante ou número informado diverge do processo. Receba o documento correto.")
    data = get_object_store().get_bytes(receipt.storage_key)
    if sha256(data).hexdigest() != receipt.sha256:
        raise HTTPException(409, "Comprovante armazenado diverge do recebido")
    receipt.status = "conferido_advogado"
    receipt.dados = {**(receipt.dados or {}), "conferencia": payload.model_dump(mode="json", exclude={"versao"}),
        "conferido_por": current.usuario_id, "conferido_em": datetime.now(timezone.utc).isoformat(), "metodo": "conferencia_humana"}
    attempt.status = "envio_confirmado"
    attempt.versao += 1
    draft = session.get(m.Peticao, package.peticao_id) if package.peticao_id else None
    if draft:
        draft.status = "protocolada"
        draft.protocolada_em = payload.data_ato
        draft.dossie = {**(draft.dossie or {}), "protocolo_registrado": {"protocolo": payload.protocolo,
            "origem": "conferencia_humana", "comprovante_status": receipt.status, "comprovante_id": receipt.id,
            "pacote_id": package.id, "tentativa_id": attempt.id}}
    audit(session, current, "comprovante_conferido", "comprovante_protocolo", receipt.id,
          {"metodo": "conferencia_humana", "pacote_id": package.id})
    session.commit()
    return attempt_out(session, attempt)
