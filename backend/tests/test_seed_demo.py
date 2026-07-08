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


def test_seed_links_prazos_to_their_intimacoes(db_session):
    """A fila de revisão junta prazo↔intimação por intimacao_id; sem o vínculo
    a UI mostra tudo como "sem prazo"."""
    _seed(db_session)

    prazos = db_session.scalars(select(models.Prazo)).all()
    assert prazos
    com_vinculo = [p for p in prazos if p.intimacao_id is not None]
    assert len(com_vinculo) == len(prazos), "todo prazo da seed nasce de uma intimação"


def test_seed_covers_all_petition_phases_and_receipt(db_session):
    _seed(db_session)

    peticoes = db_session.scalars(select(models.Peticao)).all()
    statuses = {p.status for p in peticoes}
    assert {"rascunho", "em_revisao", "aprovada", "protocolada"} <= statuses

    protocolada = next(p for p in peticoes if p.status == "protocolada")
    assert protocolada.protocolada_em is not None

    # O seed usa o fallback manual (confirm_manual_protocol), que registra
    # auditoria + protocolo sem disparar o conector PJe real (sem job placebo).
    audit = db_session.scalars(
        select(models.AuditLog).where(
            models.AuditLog.entidade == "peticao",
            models.AuditLog.entidade_id == protocolada.id,
            models.AuditLog.acao == "peticao_protocolada",
        )
    ).one()
    assert audit.detalhe.get("protocolo")


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


def test_seed_has_approved_petition_on_esaj_process_for_demo(db_session):
    """A demo mostra a correção TJSP->e-SAJ: precisa de uma minuta aprovada,
    pronta pra protocolar (via cofre + sandbox), num processo e-SAJ."""
    _seed(db_session)

    aprovadas = db_session.scalars(
        select(models.Peticao).where(models.Peticao.status == "aprovada")
    ).all()
    sistemas = {
        db_session.get(models.Processo, p.processo_id).sistema for p in aprovadas
    }
    assert "e-SAJ" in sistemas, "esperava uma minuta aprovada num processo e-SAJ"


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


def test_seed_sets_tenant_escritorio_on_all_records(db_session):
    """Isolamento por tenant filtra por escritorio_id; sem ele, intimações,
    prazos e petições somem da UI após o login (tenant_select retorna vazio)."""
    result = _seed(db_session)

    for model in (models.Intimacao, models.Prazo, models.Peticao):
        rows = db_session.scalars(select(model)).all()
        assert rows, f"{model.__tablename__} vazio no seed"
        sem_tenant = [r for r in rows if r.escritorio_id is None]
        assert not sem_tenant, (
            f"{model.__tablename__}: {len(sem_tenant)} registros sem escritorio_id"
        )
        assert all(r.escritorio_id == result.escritorio_id for r in rows)


def test_cli_has_seed_demo_subcommand():
    from app.cli import _build_parser

    args = _build_parser().parse_args(["seed-demo"])
    assert args.command == "seed-demo"
