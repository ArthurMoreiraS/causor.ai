"""Local development seed data.

Run from ``backend/`` with a local SQLite database configured:

    $env:CAUSOR_DATABASE_URL="sqlite:///./causor_dev.db"
    python -m app.dev_seed
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.sor import models
from app.sor.db import Base, SessionLocal, engine


def _today(offset: int = 0) -> date:
    return date.today() + timedelta(days=offset)


def seed() -> None:
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        if session.scalar(select(models.Escritorio).limit(1)) is not None:
            print("Banco local ja possui dados. Seed ignorado.")
            return

        escritorio = models.Escritorio(nome="Causor Demo Advocacia", cnpj="00000000000100")
        session.add(escritorio)
        session.flush()

        usuario = models.Usuario(
            escritorio_id=escritorio.id,
            nome="Advogado Responsavel",
            email="piloto@causor.ai",
            oab="123456",
            oab_uf="SP",
        )
        cliente = models.Cliente(
            escritorio_id=escritorio.id,
            nome="Cliente Piloto Ltda.",
            documento="00000000000199",
        )
        session.add_all([usuario, cliente])
        session.flush()

        processos = [
            models.Processo(
                escritorio_id=escritorio.id,
                cliente_id=cliente.id,
                numero="10018428820258260100",
                classe="Procedimento Comum Civel",
                tribunal="TJSP",
                orgao_julgador="12a Vara Civel",
                sistema="e-SAJ",
                data_ajuizamento=_today(-120),
            ),
            models.Processo(
                escritorio_id=escritorio.id,
                cliente_id=cliente.id,
                numero="00073412120255020031",
                classe="Reclamacao Trabalhista",
                tribunal="TRT2",
                orgao_julgador="31a Vara do Trabalho",
                sistema="PJe",
                data_ajuizamento=_today(-80),
            ),
            models.Processo(
                escritorio_id=escritorio.id,
                cliente_id=cliente.id,
                numero="50123894420254036100",
                classe="Mandado de Seguranca",
                tribunal="TRF3",
                orgao_julgador="6a Vara Federal",
                sistema="PJe",
                data_ajuizamento=_today(-45),
            ),
        ]
        session.add_all(processos)
        session.flush()

        intimacoes = [
            models.Intimacao(
                processo_id=processos[0].id,
                fonte="DJEN",
                fonte_id="demo-001",
                numero_processo=processos[0].numero,
                tribunal="TJSP",
                tipo_comunicacao="Intimacao para manifestacao",
                teor="A parte autora fica intimada para se manifestar sobre os documentos juntados.",
                data_disponibilizacao=_today(-1),
                data_publicacao=_today(),
            ),
            models.Intimacao(
                processo_id=processos[1].id,
                fonte="DJEN",
                fonte_id="demo-002",
                numero_processo=processos[1].numero,
                tribunal="TRT2",
                tipo_comunicacao="Intimacao para contestar",
                teor="Fica a parte reclamada intimada para apresentar contestacao.",
                data_disponibilizacao=_today(-4),
                data_publicacao=_today(-3),
            ),
            models.Intimacao(
                processo_id=processos[2].id,
                fonte="DJEN",
                fonte_id="demo-003",
                numero_processo=processos[2].numero,
                tribunal="TRF3",
                tipo_comunicacao="Intimacao de decisao liminar",
                teor="Fica a autoridade coatora intimada da decisao liminar.",
                data_disponibilizacao=_today(-7),
                data_publicacao=_today(-6),
            ),
        ]
        session.add_all(intimacoes)
        session.flush()

        prazos = [
            models.Prazo(
                processo_id=processos[0].id,
                intimacao_id=intimacoes[0].id,
                descricao="Manifestacao sobre documentos",
                data_inicio=_today(),
                dias=15,
                dias_uteis=True,
                data_fatal=_today(12),
            ),
            models.Prazo(
                processo_id=processos[1].id,
                intimacao_id=intimacoes[1].id,
                descricao="Contestacao trabalhista",
                data_inicio=_today(-3),
                dias=15,
                dias_uteis=True,
                data_fatal=_today(2),
            ),
            models.Prazo(
                processo_id=processos[2].id,
                intimacao_id=intimacoes[2].id,
                descricao="Pedido de reconsideracao",
                data_inicio=_today(-6),
                dias=5,
                dias_uteis=True,
                data_fatal=_today(-1),
            ),
        ]
        session.add_all(prazos)
        session.flush()

        session.add_all(
            [
                models.Peticao(
                    processo_id=processos[1].id,
                    prazo_id=prazos[1].id,
                    tipo="Contestacao",
                    conteudo=(
                        "Minuta estruturada com sintese dos fatos, preliminares aplicaveis "
                        "e pedidos. Aguardando revisao do advogado responsavel."
                    ),
                    status="rascunho",
                ),
                models.Peticao(
                    processo_id=processos[0].id,
                    prazo_id=prazos[0].id,
                    tipo="Manifestacao",
                    conteudo=(
                        "Manifestacao preparada a partir da intimacao capturada no DJEN "
                        "e dos metadados do processo no SOR."
                    ),
                    status="aprovada",
                    aprovada_por=usuario.id,
                ),
            ]
        )

        session.commit()
        print("Banco local criado e populado com dados demo.")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
