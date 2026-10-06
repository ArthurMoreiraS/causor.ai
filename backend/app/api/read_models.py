"""Project public read fields in SQL; raw court payloads stay in the database."""
from datetime import date, timedelta

from sqlalchemy import and_, case, func, select

from app.api.schemas import IntimacaoOut, PrazoOut
from app.prazo_engine.pipeline import KEY
from app.sor import models


def notice_statement(current):
    fields = [getattr(models.Intimacao, name) for name in IntimacaoOut.model_fields if name != "prazo_analise"]
    return select(*fields, models.Intimacao.payload[KEY].label("prazo_analise")).where(
        models.Intimacao.escritorio_id == current.escritorio_id,
    )


def read_notices(session, statement):
    result = []
    for row in session.execute(statement).mappings():
        values = dict(row)
        if not isinstance(values["prazo_analise"], dict):
            values["prazo_analise"] = None
        result.append(IntimacaoOut.model_validate(values))
    return result


def deadline_statement(current):
    fields = [getattr(models.Prazo, name) for name in PrazoOut.model_fields if name != "revisao_status"]
    return select(*fields, models.Intimacao.payload[KEY].label("analysis")).outerjoin(
        models.Intimacao,
        and_(models.Prazo.intimacao_id == models.Intimacao.id,
             models.Intimacao.escritorio_id == current.escritorio_id),
    ).where(models.Prazo.escritorio_id == current.escritorio_id)


def read_deadlines(session, statement):
    result = []
    for row in session.execute(statement).mappings():
        values = dict(row)
        analysis = values.pop("analysis")
        values["revisao_status"] = (
            analysis.get("status", "pendente")
            if isinstance(analysis, dict) and analysis.get("prazo_id") == values["id"]
            else "pendente"
        )
        result.append(PrazoOut.model_validate(values))
    return result


def operational_counts(session, current, today: date):
    counts = {}
    for key, model in (("processos", models.Processo), ("intimacoes", models.Intimacao)):
        counts[key] = session.scalar(select(func.count()).select_from(model).where(
            model.escritorio_id == current.escritorio_id,
        ))

    analysis = models.Intimacao.payload[KEY]
    pointer = analysis["prazo_id"]
    # Guard the numeric cast: historical/malformed JSON must remain pending.
    if session.get_bind().dialect.name == "postgresql":
        numeric = func.json_typeof(pointer) == "number"
    else:
        numeric = func.json_type(pointer).in_(["integer", "real"])
    confirmed = func.coalesce(and_(
        case((numeric, pointer.as_float()), else_=None) == models.Prazo.id,
        analysis["status"].as_string() == "confirmado",
    ), False)
    pending = models.Prazo.cumprido.is_(False)
    conditions = {
        "prazos": pending,
        "prazos_a_revisar": and_(pending, ~confirmed),
        "risco": and_(pending, confirmed, models.Prazo.data_fatal <= today + timedelta(days=3)),
        "vencidos": and_(pending, confirmed, models.Prazo.data_fatal < today),
    }
    row = session.execute(select(*[
        func.coalesce(func.sum(case((condition, 1), else_=0)), 0).label(key)
        for key, condition in conditions.items()
    ]).select_from(models.Prazo).outerjoin(models.Intimacao, and_(
        models.Prazo.intimacao_id == models.Intimacao.id,
        models.Intimacao.escritorio_id == current.escritorio_id,
    )).where(models.Prazo.escritorio_id == current.escritorio_id)).mappings().one()
    counts.update(row)
    row = session.execute(select(*[
        func.coalesce(func.sum(case((models.Peticao.status == status, 1), else_=0)), 0).label(key)
        for key, status in (("minutas", "rascunho"), ("aprovadas", "aprovada"))
    ]).where(models.Peticao.escritorio_id == current.escritorio_id)).mappings().one()
    counts.update(row)
    return counts
