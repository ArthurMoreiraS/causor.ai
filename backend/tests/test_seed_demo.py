"""TDD for the idempotent demo seed (Etapa 0 of the demo-alignment spec).

The seed must paint every visual state the landing page promises: deadlines
overdue / D-1 / D-3 / comfortable, petitions in every lifecycle phase, a
simulated filing receipt, a vault credential and a coherent audit trail.
"""

from datetime import date

from sqlalchemy import select

from app.sor import models
from app.sor.seed_demo import DEMO_ESCRITORIO_NOME, seed_demo

TODAY = date(2026, 6, 11)


def _seed(db_session):
    result = seed_demo(db_session, today=TODAY)
    db_session.commit()
    return result


def test_seed_creates_office_users_and_processes(db_session):
    _seed(db_session)

    escritorio = db_session.scalars(
        select(models.Escritorio).where(models.Escritorio.nome == DEMO_ESCRITORIO_NOME)
    ).one()
    usuarios = db_session.scalars(
        select(models.Usuario).where(models.Usuario.escritorio_id == escritorio.id)
    ).all()
    processos = db_session.scalars(
        select(models.Processo).where(models.Processo.escritorio_id == escritorio.id)
    ).all()

    assert len(usuarios) >= 2
    assert any(u.oab for u in usuarios), "advogado responsavel precisa de OAB"
    assert len(processos) >= 10
    # CNJ format: NNNNNNN-DD.AAAA.J.TR.OOOO
    for processo in processos:
        parts = processo.numero.split(".")
        assert len(parts) == 5, processo.numero
        assert "-" in parts[0], processo.numero


def test_seed_covers_all_deadline_risk_states(db_session):
    _seed(db_session)

    prazos = db_session.scalars(select(models.Prazo)).all()
    abertos = [p for p in prazos if not p.cumprido]
    deltas = {(p.data_fatal - TODAY).days for p in abertos}

    assert any(d < 0 for d in deltas), "precisa de prazo vencido"
    assert 1 in deltas, "precisa de prazo D-1 (alto risco)"
    assert 3 in deltas, "precisa de prazo D-3 (medio risco)"
    assert any(d >= 5 for d in deltas), "precisa de prazo confortavel"


def test_seed_covers_all_petition_phases_and_receipt(db_session):
    _seed(db_session)

    peticoes = db_session.scalars(select(models.Peticao)).all()
    statuses = {p.status for p in peticoes}
    assert {"rascunho", "em_revisao", "aprovada", "protocolada"} <= statuses

    protocolada = next(p for p in peticoes if p.status == "protocolada")
    assert protocolada.protocolada_em is not None

    job = db_session.scalars(
        select(models.JobExecucao).where(
            models.JobExecucao.entidade == "peticao",
            models.JobExecucao.entidade_id == protocolada.id,
        )
    ).one()
    assert job.status == "completed"
    assert job.resultado and job.resultado.get("protocolo")


def test_seed_creates_intimacoes_vault_credential_and_audit(db_session):
    _seed(db_session)

    intimacoes = db_session.scalars(select(models.Intimacao)).all()
    assert len(intimacoes) >= 4
    teores = " ".join((i.teor or "").lower() for i in intimacoes)
    assert "cita" in teores or "intima" in teores

    credenciais = db_session.scalars(select(models.CredencialAssinatura)).all()
    assert any(c.ativo for c in credenciais)
    assert all(c.referencia_vault.startswith("localdev://") for c in credenciais)

    acoes = {a.acao for a in db_session.scalars(select(models.AuditLog)).all()}
    assert "peticao_protocolada" in acoes
    assert "credencial_assinatura_cadastrada" in acoes


def test_seed_is_idempotent(db_session):
    _seed(db_session)
    counts_first = {
        model: db_session.scalars(select(model)).all().__len__()
        for model in (
            models.Escritorio,
            models.Usuario,
            models.Processo,
            models.Intimacao,
            models.Prazo,
            models.Peticao,
            models.CredencialAssinatura,
        )
    }

    _seed(db_session)
    for model, first in counts_first.items():
        again = len(db_session.scalars(select(model)).all())
        assert again == first, f"{model.__tablename__} duplicou: {first} -> {again}"


def test_cli_has_seed_demo_subcommand():
    from app.cli import _build_parser

    args = _build_parser().parse_args(["seed-demo"])
    assert args.command == "seed-demo"
