"""Idempotent demo seed.

Paints the full story the landing page tells: capture -> deadline -> draft ->
approval -> (simulated) filing -> audit. Dates are relative to ``today`` so the
demo always shows live risk states (overdue, D-1, D-3, comfortable).

Re-running replaces the previous demo dataset instead of duplicating it. The
deterministic marker is the office name below.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.queue.jobs import run_fake_protocol_job
from app.sor import models
from app.vault.service import store_signature_reference

DEMO_ESCRITORIO_NOME = "Moreira & Caldas Advogados (Demo)"


@dataclass
class SeedDemoResult:
    escritorio_id: int
    usuarios: int
    processos: int
    intimacoes: int
    prazos: int
    peticoes: int


def _audit(
    session: Session,
    *,
    acao: str,
    entidade: str,
    entidade_id: int,
    ator: str,
    escritorio_id: int,
    detalhe: dict | None = None,
) -> None:
    session.add(
        models.AuditLog(
            escritorio_id=escritorio_id,
            ator=ator,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhe=detalhe or {},
        )
    )


def _wipe_previous_demo(session: Session, escritorio: models.Escritorio) -> None:
    """Remove every row from a previous seed run, including its audit trail.

    Demo data is synthetic by definition; replacing its audit entries keeps the
    panel coherent without touching real (non-demo) escritorios.
    """

    processo_ids = list(
        session.scalars(
            select(models.Processo.id).where(models.Processo.escritorio_id == escritorio.id)
        )
    )
    usuario_ids = list(
        session.scalars(
            select(models.Usuario.id).where(models.Usuario.escritorio_id == escritorio.id)
        )
    )
    peticao_ids = list(
        session.scalars(
            select(models.Peticao.id).where(models.Peticao.processo_id.in_(processo_ids))
        )
    )
    job_ids = list(
        session.scalars(
            select(models.JobExecucao.id).where(
                or_(
                    (models.JobExecucao.entidade == "peticao")
                    & models.JobExecucao.entidade_id.in_(peticao_ids),
                    (models.JobExecucao.entidade == "escritorio")
                    & (models.JobExecucao.entidade_id == escritorio.id),
                )
            )
        )
    )

    audit_conditions = [models.AuditLog.escritorio_id == escritorio.id]
    for entidade, ids in (
        ("peticao", peticao_ids),
        ("processo", processo_ids),
        ("job_execucao", job_ids),
    ):
        if ids:
            audit_conditions.append(
                (models.AuditLog.entidade == entidade) & models.AuditLog.entidade_id.in_(ids)
            )
    session.execute(delete(models.AuditLog).where(or_(*audit_conditions)))

    if job_ids:
        session.execute(
            delete(models.JobExecucao).where(models.JobExecucao.id.in_(job_ids))
        )
    if peticao_ids:
        session.execute(
            delete(models.Documento).where(models.Documento.peticao_id.in_(peticao_ids))
        )
        session.execute(delete(models.Peticao).where(models.Peticao.id.in_(peticao_ids)))
    if processo_ids:
        session.execute(delete(models.Prazo).where(models.Prazo.processo_id.in_(processo_ids)))
        session.execute(
            delete(models.Intimacao).where(models.Intimacao.processo_id.in_(processo_ids))
        )
        session.execute(
            delete(models.Andamento).where(models.Andamento.processo_id.in_(processo_ids))
        )
        session.execute(
            delete(models.Documento).where(models.Documento.processo_id.in_(processo_ids))
        )
        session.execute(delete(models.Processo).where(models.Processo.id.in_(processo_ids)))
    if usuario_ids:
        session.execute(
            delete(models.CredencialAssinatura).where(
                models.CredencialAssinatura.usuario_id.in_(usuario_ids)
            )
        )
    session.execute(
        delete(models.TemplatePeticao).where(
            models.TemplatePeticao.escritorio_id == escritorio.id
        )
    )
    session.execute(
        delete(models.Cliente).where(models.Cliente.escritorio_id == escritorio.id)
    )
    if usuario_ids:
        session.execute(delete(models.Usuario).where(models.Usuario.id.in_(usuario_ids)))
    session.flush()


# Each spec: (sequencial, ano, segmento J, tribunal TR, origem, classe, tribunal,
# orgao, sistema, cliente)
_PROCESSOS = [
    ("0801234", "2025", "8", "26", "0100", "Procedimento Comum Cível", "TJSP",
     "3ª Vara Cível - Foro Central", "e-SAJ", "Transportes Andrade Ltda"),
    ("0703451", "2025", "8", "19", "0001", "Procedimento Comum Cível", "TJRJ",
     "12ª Vara Cível da Capital", "PJe", "Construtora Mar Azul S/A"),
    ("0512098", "2024", "8", "13", "0024", "Cumprimento de Sentença", "TJMG",
     "2ª Vara Empresarial de Belo Horizonte", "PJe", "Mineração Serra Verde"),
    ("0098123", "2025", "5", "02", "0011", "Ação Trabalhista - Rito Ordinário", "TRT2",
     "45ª Vara do Trabalho de São Paulo", "PJe", "Padaria Pão Dourado ME"),
    ("0045678", "2025", "5", "01", "0042", "Recurso Ordinário Trabalhista", "TRT1",
     "Gabinete da 4ª Turma", "PJe", "Hotel Costa do Sol"),
    ("1002345", "2024", "4", "03", "6100", "Procedimento Comum Cível", "TRF3",
     "1ª Vara Federal de São Paulo", "PJe", "Importadora Oliveira"),
    ("0823456", "2025", "8", "26", "0011", "Execução de Título Extrajudicial", "TJSP",
     "8ª Vara Cível - Foro Regional Santana", "e-SAJ", "Banco Regional Paulista"),
    ("0654321", "2024", "8", "19", "0203", "Despejo por Falta de Pagamento", "TJRJ",
     "5ª Vara Cível de Niterói", "PJe", "Imobiliária Horizonte"),
    ("0734512", "2025", "8", "13", "0079", "Procedimento Comum Cível", "TJMG",
     "1ª Vara Cível de Contagem", "PJe", "Farmácia Saúde Plena"),
    ("0911223", "2025", "8", "26", "0577", "Embargos à Execução", "TJSP",
     "4ª Vara Cível de Campinas", "e-SAJ", "Auto Peças Rodrigues"),
]


def _numero_cnj(seq: str, ano: str, segmento: str, tribunal: str, origem: str) -> str:
    base = f"{seq}{ano}{segmento}{tribunal}{origem}"
    resto = int(base) % 97
    dv = 98 - ((resto * 100) % 97)
    return f"{seq}-{dv:02d}.{ano}.{segmento}.{tribunal}.{origem}"


def seed_demo(session: Session, *, today: date | None = None) -> SeedDemoResult:
    today = today or date.today()

    escritorio = session.scalars(
        select(models.Escritorio).where(models.Escritorio.nome == DEMO_ESCRITORIO_NOME)
    ).one_or_none()
    if escritorio is not None:
        _wipe_previous_demo(session, escritorio)
    else:
        escritorio = models.Escritorio(nome=DEMO_ESCRITORIO_NOME, cnpj="12345678000190")
        session.add(escritorio)
        session.flush()

    advogada = models.Usuario(
        escritorio_id=escritorio.id,
        nome="Dra. Helena Moreira",
        email="helena.moreira@demo.causor.com.br",
        oab="123456",
        oab_uf="SP",
    )
    apoio = models.Usuario(
        escritorio_id=escritorio.id,
        nome="Rafael Caldas",
        email="rafael.caldas@demo.causor.com.br",
    )
    session.add_all([advogada, apoio])
    session.flush()

    clientes: dict[str, models.Cliente] = {}
    processos: list[models.Processo] = []
    for seq, ano, seg, trib_cod, origem, classe, tribunal, orgao, sistema, cliente_nome in (
        _PROCESSOS
    ):
        cliente = clientes.get(cliente_nome)
        if cliente is None:
            cliente = models.Cliente(escritorio_id=escritorio.id, nome=cliente_nome)
            session.add(cliente)
            session.flush()
            clientes[cliente_nome] = cliente
        processo = models.Processo(
            escritorio_id=escritorio.id,
            cliente_id=cliente.id,
            numero=_numero_cnj(seq, ano, seg, trib_cod, origem),
            classe=classe,
            tribunal=tribunal,
            orgao_julgador=orgao,
            sistema=sistema,
            data_ajuizamento=today - timedelta(days=120 + len(processos) * 17),
        )
        session.add(processo)
        processos.append(processo)
    session.flush()

    def _intimacao(
        processo: models.Processo,
        *,
        idx: int,
        tipo: str,
        teor: str,
        dias_atras: int,
    ) -> models.Intimacao:
        intimacao = models.Intimacao(
            processo_id=processo.id,
            fonte="DJEN",
            fonte_id=f"demo-{processo.numero}-{idx}",
            numero_processo=processo.numero,
            tribunal=processo.tribunal,
            tipo_comunicacao=tipo,
            teor=teor,
            data_disponibilizacao=today - timedelta(days=dias_atras),
            data_publicacao=today - timedelta(days=dias_atras - 1),
            payload={"origem": "seed_demo"},
        )
        session.add(intimacao)
        return intimacao

    def _prazo(
        processo: models.Processo,
        intimacao: models.Intimacao | None,
        *,
        descricao: str,
        vence_em: int,
        dias: int = 15,
        cumprido: bool = False,
    ) -> models.Prazo:
        prazo = models.Prazo(
            processo_id=processo.id,
            intimacao_id=intimacao.id if intimacao is not None else None,
            descricao=descricao,
            data_inicio=today + timedelta(days=vence_em) - timedelta(days=dias),
            dias=dias,
            dias_uteis=True,
            data_fatal=today + timedelta(days=vence_em),
            cumprido=cumprido,
        )
        session.add(prazo)
        return prazo

    # 1. Contestação D-1 (alto risco) — minuta em revisão, como no hero da landing.
    int_citacao = _intimacao(
        processos[0],
        idx=1,
        tipo="Citação",
        teor=(
            "Fica a parte ré CITADA para, querendo, apresentar contestação no prazo "
            "de 15 (quinze) dias úteis, sob pena de revelia, nos termos do art. 335 "
            "do CPC."
        ),
        dias_atras=19,
    )
    _prazo(processos[0], int_citacao, descricao="Contestação", vence_em=1)
    pet_contestacao = models.Peticao(
        processo_id=processos[0].id,
        prazo_id=None,
        tipo="Contestação",
        status="em_revisao",
        conteudo=(
            "EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 3ª VARA CÍVEL DO FORO "
            "CENTRAL DA COMARCA DE SÃO PAULO\n\nTRANSPORTES ANDRADE LTDA, já "
            "qualificada nos autos do processo em epígrafe, vem, respeitosamente, "
            "por sua advogada, apresentar CONTESTAÇÃO, pelos fundamentos de fato e "
            "de direito a seguir expostos.\n\nI - DOS FATOS\n[...]"
        ),
    )
    session.add(pet_contestacao)

    # 2. Manifestação sobre laudo pericial D-3 (médio risco) — minuta rascunho.
    int_pericia = _intimacao(
        processos[1],
        idx=1,
        tipo="Intimação",
        teor=(
            "Intimadas as partes para se manifestarem sobre o laudo pericial "
            "juntado aos autos, no prazo comum de 15 (quinze) dias úteis, nos "
            "termos do art. 477, §1º, do CPC."
        ),
        dias_atras=17,
    )
    _prazo(
        processos[1], int_pericia, descricao="Manifestação sobre laudo pericial", vence_em=3
    )
    session.add(
        models.Peticao(
            processo_id=processos[1].id,
            tipo="Manifestação sobre laudo pericial",
            status="rascunho",
            conteudo=(
                "MERITÍSSIMO JUÍZO DA 12ª VARA CÍVEL DA CAPITAL\n\nCONSTRUTORA MAR "
                "AZUL S/A vem manifestar-se sobre o laudo pericial de fls., "
                "destacando os pontos que demandam esclarecimento do expert.\n[...]"
            ),
        )
    )

    # 3. Embargos de declaração — minuta pronta aguardando aprovação (gate humano).
    int_sentenca = _intimacao(
        processos[2],
        idx=1,
        tipo="Intimação de Sentença",
        teor=(
            "Intimada a parte autora da sentença de procedência parcial publicada "
            "nesta data. Prazo de 5 (cinco) dias úteis para embargos de declaração, "
            "art. 1.023 do CPC."
        ),
        dias_atras=2,
    )
    _prazo(
        processos[2],
        int_sentenca,
        descricao="Embargos de declaração",
        vence_em=5,
        dias=5,
    )
    pet_embargos = models.Peticao(
        processo_id=processos[2].id,
        tipo="Embargos de declaração",
        status="aprovada",
        aprovada_por=advogada.id,
        conteudo=(
            "EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 2ª VARA EMPRESARIAL "
            "DE BELO HORIZONTE\n\nMINERAÇÃO SERRA VERDE, nos autos em epígrafe, "
            "opõe EMBARGOS DE DECLARAÇÃO em face da r. sentença, ante a omissão "
            "quanto aos juros de mora sobre a parcela incontroversa.\n[...]"
        ),
    )
    session.add(pet_embargos)

    # 4. Réplica protocolada com comprovante simulado (job + auditoria reais).
    int_replica = _intimacao(
        processos[3],
        idx=1,
        tipo="Intimação",
        teor=(
            "Intimada a parte reclamante para apresentar réplica à contestação no "
            "prazo de 15 (quinze) dias úteis."
        ),
        dias_atras=12,
    )
    _prazo(
        processos[3],
        int_replica,
        descricao="Réplica",
        vence_em=4,
        cumprido=True,
    )
    pet_replica = models.Peticao(
        processo_id=processos[3].id,
        tipo="Réplica",
        status="aprovada",
        aprovada_por=advogada.id,
        conteudo=(
            "EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DA 45ª VARA DO TRABALHO DE SÃO "
            "PAULO\n\nPADARIA PÃO DOURADO ME apresenta RÉPLICA à contestação, "
            "impugnando especificamente os documentos juntados pela reclamada.\n[...]"
        ),
    )
    session.add(pet_replica)
    session.flush()

    # 5. Prazo vencido (near-miss visível no radar).
    int_pagamento = _intimacao(
        processos[4],
        idx=1,
        tipo="Intimação de Pagamento",
        teor=(
            "Intimada a executada para efetuar o pagamento voluntário do débito no "
            "prazo de 15 (quinze) dias, sob pena de multa de 10% e penhora, nos "
            "termos do art. 523 do CPC."
        ),
        dias_atras=20,
    )
    _prazo(
        processos[4],
        int_pagamento,
        descricao="Pagamento voluntário / impugnação",
        vence_em=-2,
    )

    # 6+. Prazos confortáveis e processos de carteira.
    int_despacho = _intimacao(
        processos[5],
        idx=1,
        tipo="Despacho",
        teor=(
            "Vistos. Especifiquem as partes, em 15 (quinze) dias úteis, as provas "
            "que pretendem produzir, justificando sua pertinência."
        ),
        dias_atras=5,
    )
    _prazo(
        processos[5],
        int_despacho,
        descricao="Especificação de provas",
        vence_em=8,
    )
    int_recurso = _intimacao(
        processos[6],
        idx=1,
        tipo="Intimação de Sentença",
        teor=(
            "Publicada sentença de improcedência dos embargos. Prazo de 15 "
            "(quinze) dias úteis para apelação, art. 1.009 do CPC."
        ),
        dias_atras=3,
    )
    _prazo(processos[6], int_recurso, descricao="Apelação", vence_em=12)

    for processo in processos:
        session.add(
            models.Andamento(
                processo_id=processo.id,
                codigo=26,
                descricao="Distribuição por sorteio",
                data=datetime.combine(
                    processo.data_ajuizamento or today, time(10, 0), tzinfo=timezone.utc
                ),
            )
        )
    session.flush()

    session.add(
        models.TemplatePeticao(
            escritorio_id=escritorio.id,
            tipo="Contestação",
            area="Cível",
            nome="Contestação cível padrão do escritório",
            conteudo=(
                "EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA {{vara}}\n\n"
                "{{cliente}}, já qualificado, vem apresentar CONTESTAÇÃO.\n\n"
                "I - DOS FATOS\n{{fatos}}\n\nII - DO DIREITO\n{{fundamentos}}\n\n"
                "III - DOS PEDIDOS\n{{pedidos}}"
            ),
            ativo=True,
        )
    )

    intimacoes_seed = [
        int_citacao, int_pericia, int_sentenca, int_replica, int_pagamento,
        int_despacho, int_recurso,
    ]
    for intimacao in intimacoes_seed:
        _audit(
            session,
            acao="intimacao_capturada",
            entidade="intimacao",
            entidade_id=intimacao.id,
            ator="agent:capture",
            escritorio_id=escritorio.id,
            detalhe={"fonte": "DJEN", "tipo": intimacao.tipo_comunicacao},
        )
    for peticao in (pet_contestacao, pet_embargos, pet_replica):
        _audit(
            session,
            acao="minuta_gerada",
            entidade="peticao",
            entidade_id=peticao.id,
            ator="agent:drafting",
            escritorio_id=escritorio.id,
            detalhe={"tipo": peticao.tipo},
        )
    for peticao in (pet_embargos, pet_replica):
        _audit(
            session,
            acao="peticao_aprovada",
            entidade="peticao",
            entidade_id=peticao.id,
            ator=f"usuario:{advogada.id}",
            escritorio_id=escritorio.id,
            detalhe={"tipo": peticao.tipo},
        )

    # Protocola a réplica pelo mesmo caminho do produto (job + gate + auditoria).
    run_fake_protocol_job(session, pet_replica.id)

    store_signature_reference(
        session,
        usuario_id=advogada.id,
        provedor="BirdID",
        external_ref="demo-cert-helena-001",
    )
    session.flush()

    return SeedDemoResult(
        escritorio_id=escritorio.id,
        usuarios=2,
        processos=len(processos),
        intimacoes=len(intimacoes_seed),
        prazos=7,
        peticoes=4,
    )
