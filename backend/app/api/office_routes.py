"""Client records and human-controlled work linked to existing legal entities."""

from datetime import date, datetime, timezone
from hashlib import sha256
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.auth.jwt_auth import CurrentUser, get_current_user
from app.auth.tenant import get_owned_or_404, tenant_select
from app.sor import models
from app.sor.db import get_session
from app.api.schemas import PeticaoOut

router = APIRouter(tags=["escritorio"])
TaskStatus = Literal["aberta", "em_andamento", "aguardando", "concluida", "cancelada"]
TaskKind = Literal["providencia", "documento", "revisao", "atendimento"]
Priority = Literal["normal", "alta", "urgente"]


@router.get("/peticoes/{peticao_id}", response_model=PeticaoOut)
def get_draft(peticao_id: int, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    return get_owned_or_404(session, models.Peticao, peticao_id, current)


class ClienteIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nome: str = Field(min_length=1, max_length=255)
    documento: str | None = Field(default=None, max_length=20)


class ClienteOut(ClienteIn):
    id: int
    processos_count: int = 0


class ClientesOut(BaseModel):
    items: list[ClienteOut]
    total: int


class ClienteLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cliente_id: int | None = Field(ge=1)


class TarefaIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    titulo: str = Field(min_length=1, max_length=255)
    descricao: str | None = Field(default=None, max_length=10000)
    tipo: TaskKind = "providencia"
    prioridade: Priority = "normal"
    data_prevista: date | None = None
    processo_id: int | None = Field(default=None, ge=1)
    cliente_id: int | None = Field(default=None, ge=1)
    intimacao_id: int | None = Field(default=None, ge=1)
    peticao_id: int | None = Field(default=None, ge=1)
    alerta_indice: int | None = Field(default=None, ge=0)
    alerta_texto_esperado: str | None = Field(default=None, max_length=20000)
    responsavel_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def alert_origin(self):
        if (self.peticao_id is None) != (self.alerta_indice is None):
            raise ValueError("informe a minuta e o índice do alerta juntos")
        if (self.peticao_id is None) != (self.alerta_texto_esperado is None):
            raise ValueError("informe o texto do alerta apresentado para revisão")
        return self


class TarefaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    versao: int = Field(ge=1)
    titulo: str | None = Field(default=None, min_length=1, max_length=255)
    descricao: str | None = Field(default=None, max_length=10000)
    tipo: TaskKind | None = None
    prioridade: Priority | None = None
    status: TaskStatus | None = None
    data_prevista: date | None = None
    responsavel_id: int | None = Field(default=None, ge=1)

    @field_validator("titulo", "tipo", "prioridade", "status")
    @classmethod
    def required_if_present(cls, value):
        if value is None:
            raise ValueError("campo não pode ser nulo")
        return value


class TarefaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    titulo: str
    descricao: str | None
    tipo: str
    status: str
    prioridade: str
    data_prevista: date | None
    processo_id: int | None
    cliente_id: int | None
    intimacao_id: int | None
    peticao_id: int | None
    responsavel_id: int | None
    origem: str
    origem_texto: str | None
    versao: int
    concluida_em: datetime | None
    processo_numero: str | None = None
    cliente_nome: str | None = None
    responsavel_nome: str | None = None


class TarefasOut(BaseModel):
    items: list[TarefaOut]
    total: int


def audit(session, current, action, entity, entity_id, detail=None):
    session.add(models.AuditLog(escritorio_id=current.escritorio_id, ator=f"usuario:{current.usuario_id}",
                               acao=action, entidade=entity, entidade_id=entity_id, detalhe=detail or {}))


@router.get("/clientes", response_model=ClientesOut)
def list_clients(q: str = Query("", max_length=200), limit: int = Query(50, ge=1, le=200),
                 offset: int = Query(0, ge=0), session: Session = Depends(get_session),
                 current: CurrentUser = Depends(get_current_user)):
    base = tenant_select(models.Cliente, current)
    if q.strip():
        base = base.where(models.Cliente.nome.icontains(q.strip(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    clients = session.scalars(base.order_by(models.Cliente.nome, models.Cliente.id).limit(limit).offset(offset)).all()
    counts = dict(session.execute(select(models.Processo.cliente_id, func.count()).where(
        models.Processo.escritorio_id == current.escritorio_id, models.Processo.cliente_id.in_([c.id for c in clients]),
    ).group_by(models.Processo.cliente_id)).all())
    return {"total": total, "items": [ClienteOut(id=c.id, nome=c.nome, documento=c.documento,
                                                 processos_count=counts.get(c.id, 0)) for c in clients]}


@router.post("/clientes", response_model=ClienteOut, status_code=201)
def create_client(payload: ClienteIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    customer = models.Cliente(escritorio_id=current.escritorio_id, **payload.model_dump())
    session.add(customer)
    session.flush()
    audit(session, current, "cliente_criado", "cliente", customer.id)
    session.commit()
    return ClienteOut(id=customer.id, nome=customer.nome, documento=customer.documento)


@router.put("/processos/{processo_id}/cliente")
def link_client(processo_id: int, payload: ClienteLink, session: Session = Depends(get_session),
                current: CurrentUser = Depends(get_current_user)):
    process = session.scalar(tenant_select(models.Processo, current).where(models.Processo.id == processo_id).with_for_update())
    if process is None:
        raise HTTPException(404, "processo não encontrado")
    if payload.cliente_id is not None:
        get_owned_or_404(session, models.Cliente, payload.cliente_id, current)
    if process.cliente_id != payload.cliente_id:
        protected = session.scalar(select(models.Peticao.id).where(
            models.Peticao.processo_id == process.id, models.Peticao.status.in_(["aprovada", "protocolando"]),
        ).limit(1))
        if protected:
            raise HTTPException(409, "Há minuta aprovada ou em protocolo. Revise a aprovação antes de alterar a parte representada.")
        before = process.cliente_id
        process.cliente_id = payload.cliente_id
        audit(session, current, "processo_cliente_vinculado", "processo", process.id,
              {"cliente_anterior_id": before, "cliente_id": payload.cliente_id})
        session.commit()
    return {"processo_id": process.id, "cliente_id": process.cliente_id}


def task_query(current):
    t, p, c, u = models.Tarefa, models.Processo, models.Cliente, models.Usuario
    return select(t, p.numero, c.nome, u.nome, c.id).outerjoin(p, and_(p.id == t.processo_id, p.escritorio_id == t.escritorio_id)).outerjoin(
        c, and_(c.id == func.coalesce(p.cliente_id, t.cliente_id), c.escritorio_id == t.escritorio_id),
    ).outerjoin(u, and_(u.id == t.responsavel_id, u.escritorio_id == t.escritorio_id)).where(t.escritorio_id == current.escritorio_id)


def task_out(row):
    task, number, client_name, owner, customer_id = row
    result = TarefaOut.model_validate(task)
    result.processo_numero, result.cliente_nome, result.responsavel_nome = number, client_name, owner
    result.cliente_id = customer_id
    return result


@router.get("/tarefas", response_model=TarefasOut)
def list_tasks(q: str = Query("", max_length=200), status: TaskStatus | None = None,
               processo_id: int | None = Query(None, ge=1), cliente_id: int | None = Query(None, ge=1),
               responsavel_id: int | None = Query(None, ge=1), limit: int = Query(50, ge=1, le=200),
               offset: int = Query(0, ge=0), session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    stmt = task_query(current)
    if q.strip():
        stmt = stmt.where(or_(models.Tarefa.titulo.icontains(q.strip(), autoescape=True),
                              models.Tarefa.descricao.icontains(q.strip(), autoescape=True)))
    for field, value in ((models.Tarefa.status, status), (models.Tarefa.processo_id, processo_id),
                         (models.Cliente.id, cliente_id), (models.Tarefa.responsavel_id, responsavel_id)):
        if value is not None:
            stmt = stmt.where(field == value)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.execute(stmt.order_by(models.Tarefa.id.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [task_out(row) for row in rows]}


@router.post("/tarefas", response_model=TarefaOut, status_code=201)
def create_task(payload: TarefaIn, response: Response, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    values = payload.model_dump(exclude={"alerta_indice", "alerta_texto_esperado"})
    source_text = None
    for model, field in ((models.Cliente, "cliente_id"), (models.Usuario, "responsavel_id"),
                         (models.Intimacao, "intimacao_id"), (models.Peticao, "peticao_id")):
        if values[field] is None:
            continue
        entity = get_owned_or_404(session, model, values[field], current)
        if field in {"intimacao_id", "peticao_id"}:
            if values["processo_id"] is not None and values["processo_id"] != entity.processo_id:
                raise HTTPException(422, "origem e processo não correspondem")
            values["processo_id"] = entity.processo_id
        if field == "peticao_id":
            alerts = (entity.dossie or {}).get("alertas") or []
            if not isinstance(alerts, list) or payload.alerta_indice >= len(alerts) or not isinstance(alerts[payload.alerta_indice], str):
                raise HTTPException(422, "alerta não encontrado na minuta")
            source_text = alerts[payload.alerta_indice]
            if source_text.strip() != payload.alerta_texto_esperado:
                raise HTTPException(409, "O alerta mudou. Abra a minuta atual antes de criar a pendência.")
    if values["processo_id"] is not None:
        process = session.scalar(tenant_select(models.Processo, current).where(models.Processo.id == values["processo_id"]).with_for_update())
        if process is None:
            raise HTTPException(404, "processo não encontrado")
        if values["cliente_id"] is not None and values["cliente_id"] != process.cliente_id:
            raise HTTPException(422, "cliente e processo não correspondem")
        values["cliente_id"] = None  # The process is the owner of its represented-party association.
    origin_key = sha256(f"{payload.peticao_id}:{source_text}".encode()).hexdigest() if source_text is not None else None
    if origin_key:
        existing = session.execute(task_query(current).where(models.Tarefa.origem_key == origin_key)).first()
        if existing:
            response.status_code = 200
            return task_out(existing)
    task = models.Tarefa(escritorio_id=current.escritorio_id, **values, origem_key=origin_key,
                        origem="alerta_minuta" if source_text is not None else "intimacao" if payload.intimacao_id else "manual",
                        origem_texto=source_text)
    session.add(task)
    session.flush()
    audit(session, current, "tarefa_criada", "tarefa", task.id,
          {"origem": task.origem, "processo_id": task.processo_id, "peticao_id": task.peticao_id})
    session.commit()
    return task_out(session.execute(task_query(current).where(models.Tarefa.id == task.id)).one())


@router.patch("/tarefas/{tarefa_id}", response_model=TarefaOut)
def update_task(tarefa_id: int, payload: TarefaPatch, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    task = session.scalar(tenant_select(models.Tarefa, current).where(models.Tarefa.id == tarefa_id).with_for_update())
    if task is None:
        raise HTTPException(404, "tarefa não encontrada")
    if task.versao != payload.versao:
        raise HTTPException(409, "A tarefa foi alterada. Atualize a lista antes de salvar novamente.")
    changes = payload.model_dump(exclude_unset=True, exclude={"versao"})
    if changes.get("responsavel_id") is not None:
        get_owned_or_404(session, models.Usuario, changes["responsavel_id"], current)
    changes = {key: value for key, value in changes.items() if getattr(task, key) != value}
    if changes:
        for key, value in changes.items():
            setattr(task, key, value)
        if "status" in changes:
            task.concluida_em = datetime.now(timezone.utc) if task.status == "concluida" else None
        task.versao += 1
        audit(session, current, "tarefa_atualizada", "tarefa", task.id, {"campos": sorted(changes), "versao": task.versao})
        session.commit()
    return task_out(session.execute(task_query(current).where(models.Tarefa.id == task.id)).one())
