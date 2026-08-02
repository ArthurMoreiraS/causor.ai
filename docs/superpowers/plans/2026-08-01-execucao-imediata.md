# Execução imediata — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** tirar de zero a única métrica que o plano de 90 dias declarou decisiva — minutas geradas pelo Causor que um advogado assinou com edição menor — colocando em produção a promessa de prazo e criando a peça que abre a conversa com um advogado sem pedir credencial nenhuma.

**Architecture:** nada de superfície nova. A Task 1 é operação (migration + SMTP + cron numa VPS que já roda). A Task 2 monta um relatório em cima do que a captura DJEN já grava no SOR, reusando a regra de alerta existente em vez de recalculá-la. A Task 3 acrescenta um sinal externo (movimentos do DataJud) à evidência da captura por upload, sem alterar o pipeline de integridade.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · pytest · Docker Compose na VPS · DJEN/Comunica e DataJud (APIs públicas do CNJ).

**Origem:** [`docs/areas/analise-competitiva-2026-08-01.md`](../../areas/analise-competitiva-2026-08-01.md) §5, que revisa [`docs/areas/plano-90-dias-2026-07-30.md`](../../areas/plano-90-dias-2026-07-30.md). Aquele plano continua valendo; este detalha as duas semanas seguintes dele.

## Global Constraints

- Comandos de backend rodam de `/backend` com `./.venv/Scripts/python.exe` (Windows) ou `.venv/bin/python` (Linux/macOS).
- TDD: teste que falha primeiro, implementação mínima depois, commit ao fim de cada tarefa.
- `ruff check .` limpo antes de todo commit.
- **Regra de decisão única (AGENTS.md):** classificação de nível de prazo vem de `app.alertas.radar.classificar`. Nunca reimplementar a regra num segundo lugar.
- **Gate humano é intocável.** Nada nesta plano executa ato irreversível; protocolo continua parando em `ready_to_sign`.
- **Nunca vender declaração como prova.** Captura por upload afirma "recebemos exatamente estes arquivos, íntegros" — jamais "os autos estão completos" (`app/autos/upload.py`).
- Modelos Claude: Haiku para chat/classificação, Sonnet para minuta. Nenhum modelo premium no caminho padrão.
- Mensagens de commit em português, no padrão do repositório (`feat(escopo): ...`, `fix(escopo): ...`, `chore(escopo): ...`).

---

## Gate G1 — a raia (owner: Arthur, não é código, ~1 hora)

**Não é tarefa de engenharia e por isso não tem passos de código — mas bloqueia a Fase 2 do plano de 90 dias.** A pesquisa de 01/08 mostra que Garfield, Enter, Eve e EvenUp escolheram uma raia única; o Causor ainda é "qualquer intimação, qualquer área", e é isso que faz a minuta precisar de reescrita.

- [ ] Escolher **uma** área e escrever a escolha em `docs/areas/analise-competitiva-2026-08-01.md` como seção nova, datada.

Critério de escolha, em ordem: (a) volume repetitivo de intimações por processo; (b) peças com estrutura estável; (c) acesso a pelo menos um advogado que atue nela. Candidatas naturais pelo material já levantado: consumidor/bancário do lado do autor, trabalhista reclamante, previdenciário.

**Por que não existe uma tarefa de código para "ajustar o drafter à raia" neste plano:** escrever passos para uma raia não escolhida seria codificar palpite — o mesmo erro registrado em `docs/estado.md` sobre o `MniFilingDriver`. Depois de G1, essa tarefa ganha spec própria.

---

## Task 1: Produção honra a promessa de prazo

O produto promete "você não perde prazo". Hoje, em produção, o alerta não sai: a migration não foi aplicada, não há SMTP e o cron não está confirmado. Enquanto isso for verdade não existe piloto — existe demo.

**Files:**
- Modify (na VPS): `/opt/causor/.env`
- Create (na VPS): `/etc/cron.d/causor` (ou acrescentar linhas às existentes)
- Modify: [`DEPLOY-VPS.md`](../../../DEPLOY-VPS.md) — seção de crons, registrando o que ficou agendado
- Modify: [`docs/estado.md`](../../estado.md) — item 6 de "Trilha do piloto"

**Interfaces:**
- Consumes: `python -m app.cli notificar-prazos`, `capture-due`, `process-autos-due` (já existem, `app/cli.py:211`, `:128`, `:164`)
- Produces: alerta de prazo chegando por e-mail em produção; log de cron em `/var/log/causor-cron.log`

- [ ] **Step 1: Aplicar a migration pendente**

```bash
ssh -i ~/.ssh/causor_deploy deploy@179.197.70.156 '
cd /opt/causor
docker compose --env-file .env --env-file .image_tag.env run --rm migrate'
```

Esperado: saída do Alembic terminando em `Running upgrade ... -> a3e7b1c9d2f8`, exit code 0.

- [ ] **Step 2: Confirmar que o banco está na head**

```bash
ssh -i ~/.ssh/causor_deploy deploy@179.197.70.156 '
cd /opt/causor
docker compose --env-file .env --env-file .image_tag.env run --rm migrate alembic current'
```

Esperado: o hash impresso é o mesmo de `alembic heads` local. Se divergir, **pare** — é a armadilha de 27/07 (banco atrás do código, sintoma disfarçado de "backend offline").

- [ ] **Step 3: Configurar SMTP no `.env` da VPS**

```bash
ssh -i ~/.ssh/causor_deploy deploy@179.197.70.156 '
cd /opt/causor
cat >> .env <<EOF
CAUSOR_SMTP_HOST=<host>
CAUSOR_SMTP_PORT=587
CAUSOR_SMTP_USER=<usuario>
CAUSOR_SMTP_PASSWORD=<senha>
CAUSOR_SMTP_FROM=alertas@causorai.com
EOF
chmod 600 .env'
```

Sem essas variáveis o aviso cai no `ConsoleSender` e **nada quebra** — que é exatamente o motivo de isso ter passado despercebido.

- [ ] **Step 4: Enviar um alerta de verdade, para si mesmo**

```bash
ssh -i ~/.ssh/causor_deploy deploy@179.197.70.156 '
cd /opt/causor
docker compose --env-file .env --env-file .image_tag.env run --rm backend python -m app.cli notificar-prazos --escritorio 1'
```

Esperado: exit code 0 **e** o e-mail na caixa de entrada. Exit code 0 sem e-mail significa que o SMTP não pegou — o comando degrada para log de propósito.

- [ ] **Step 5: Agendar os três comandos**

```bash
ssh -i ~/.ssh/causor_deploy deploy@179.197.70.156 '
cat > /etc/cron.d/causor <<EOF
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
0 * * * * deploy cd /opt/causor && docker compose --env-file .env --env-file .image_tag.env run --rm backend python -m app.cli capture-due >> /var/log/causor-cron.log 2>&1 || echo "FALHA capture-due \$(date -Is)" >> /var/log/causor-cron.log
*/5 * * * * deploy cd /opt/causor && docker compose --env-file .env --env-file .image_tag.env run --rm backend python -m app.cli process-autos-due >> /var/log/causor-cron.log 2>&1 || echo "FALHA process-autos-due \$(date -Is)" >> /var/log/causor-cron.log
30 7 * * * deploy cd /opt/causor && docker compose --env-file .env --env-file .image_tag.env run --rm backend python -m app.cli notificar-prazos >> /var/log/causor-cron.log 2>&1 || echo "FALHA notificar-prazos \$(date -Is)" >> /var/log/causor-cron.log
EOF
chmod 644 /etc/cron.d/causor'
```

- [ ] **Step 6: Observar dois ciclos antes de declarar pronto**

```bash
ssh -i ~/.ssh/causor_deploy deploy@179.197.70.156 'tail -n 100 /var/log/causor-cron.log'
```

Esperado: duas execuções de `capture-due` sem a linha `FALHA`. Sem isso, este item **não** está feito.

- [ ] **Step 7: Registrar nos documentos e commitar**

Em `docs/estado.md`, no item 6 de "Trilha do piloto", trocar "**Falta em producao:** aplicar a migration ..." por uma linha datada dizendo o que foi aplicado, o horário do cron e onde ficou o log. Em `DEPLOY-VPS.md`, atualizar a tabela de crons com as três entradas reais.

```bash
git add docs/estado.md DEPLOY-VPS.md
git commit -m "chore(operacao): alerta de prazo e crons ativos em producao"
```

---

## Task 2: `dossie-oab` — a demo que não pede nada ao advogado

O DJEN é público e nacional. Com o número da OAB dá para mostrar a um advogado o quadro real da carteira dele — intimações capturadas, prazo calculado, o que vence esta semana — sem pareamento, sem credencial e sem conector. É a peça de prospecção e é o T3' do plano de 90 dias ao mesmo tempo.

**Files:**
- Create: `backend/app/relatorios/__init__.py`
- Create: `backend/app/relatorios/dossie_oab.py`
- Modify: `backend/app/cli.py` (novo subcomando, junto dos demais em `_build_parser` e um ramo em `main`)
- Test: `backend/tests/test_dossie_oab.py`

**Interfaces:**
- Consumes: `models.Intimacao`, `models.Prazo` (`app/sor/models.py:289`, `:316`); `radar.classificar` e `radar.JANELA_DIAS` (`app/alertas/radar.py:35`, `:23`)
- Produces: `montar_dossie(session, *, escritorio_id, oab, uf, hoje, janela_dias=15) -> Dossie`, `renderizar_markdown(dossie: Dossie) -> str`, dataclasses `Dossie` e `LinhaDossie`, subcomando `dossie-oab`

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_dossie_oab.py`:

```python
"""Dossiê de uma OAB — o quadro real da carteira, sem pedir credencial.

O nível de alerta tem que sair da mesma função que o painel e o e-mail usam;
uma segunda regra faria o dossiê discordar da tela sobre o mesmo prazo.
"""

from datetime import date

import pytest

from app.relatorios.dossie_oab import montar_dossie, renderizar_markdown
from app.sor import models

HOJE = date(2026, 8, 4)


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Dossiê")
    db_session.add(esc)
    db_session.flush()
    return esc


def _intimacao_com_prazo(
    db_session,
    escritorio,
    *,
    fonte_id: str,
    publicacao: date,
    data_fatal: date | None,
    cumprido: bool = False,
):
    processo = models.Processo(
        escritorio_id=escritorio.id,
        numero=f"0000{fonte_id}-11.2026.8.27.2729",
        tribunal="TJTO",
        sistema="EPROC",
    )
    db_session.add(processo)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=processo.id,
        escritorio_id=escritorio.id,
        fonte="DJEN",
        fonte_id=fonte_id,
        numero_processo=processo.numero,
        tribunal="TJTO",
        tipo_comunicacao="Intimação",
        data_publicacao=publicacao,
    )
    db_session.add(intimacao)
    db_session.flush()
    if data_fatal is not None:
        db_session.add(
            models.Prazo(
                processo_id=processo.id,
                intimacao_id=intimacao.id,
                escritorio_id=escritorio.id,
                descricao="Manifestação",
                data_inicio=publicacao,
                dias=15,
                dias_uteis=True,
                data_fatal=data_fatal,
                cumprido=cumprido,
            )
        )
        db_session.flush()
    return intimacao


def test_dossie_traz_prazo_calculado_e_nivel_do_radar(db_session, escritorio):
    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="1",
        publicacao=date(2026, 8, 3),
        data_fatal=date(2026, 8, 5),
    )

    dossie = montar_dossie(
        db_session, escritorio_id=escritorio.id, oab="12345", uf="TO", hoje=HOJE
    )

    assert dossie.total_intimacoes == 1
    assert dossie.total_com_prazo == 1
    assert dossie.total_em_alerta == 1
    linha = dossie.linhas[0]
    assert linha.data_fatal == date(2026, 8, 5)
    assert linha.dias_para_vencer == 1
    assert linha.nivel == "d1"


def test_dossie_ignora_intimacao_fora_da_janela(db_session, escritorio):
    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="2",
        publicacao=date(2026, 6, 1),
        data_fatal=date(2026, 6, 20),
    )

    dossie = montar_dossie(
        db_session,
        escritorio_id=escritorio.id,
        oab="12345",
        uf="TO",
        hoje=HOJE,
        janela_dias=15,
    )

    assert dossie.total_intimacoes == 0
    assert dossie.linhas == []


def test_dossie_lista_intimacao_sem_prazo_sem_marcar_alerta(db_session, escritorio):
    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="3",
        publicacao=date(2026, 8, 1),
        data_fatal=None,
    )

    dossie = montar_dossie(
        db_session, escritorio_id=escritorio.id, oab="12345", uf="TO", hoje=HOJE
    )

    assert dossie.total_intimacoes == 1
    assert dossie.total_com_prazo == 0
    assert dossie.total_em_alerta == 0
    assert dossie.linhas[0].nivel is None


def test_dossie_ordena_do_prazo_mais_urgente_para_o_menos(db_session, escritorio):
    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="4",
        publicacao=date(2026, 8, 1),
        data_fatal=date(2026, 8, 20),
    )
    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="5",
        publicacao=date(2026, 8, 2),
        data_fatal=date(2026, 8, 6),
    )

    dossie = montar_dossie(
        db_session, escritorio_id=escritorio.id, oab="12345", uf="TO", hoje=HOJE
    )

    assert [linha.data_fatal for linha in dossie.linhas] == [
        date(2026, 8, 6),
        date(2026, 8, 20),
    ]


def test_markdown_tem_cabecalho_numeros_e_a_linha(db_session, escritorio):
    intimacao = _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="6",
        publicacao=date(2026, 8, 3),
        data_fatal=date(2026, 8, 5),
    )

    texto = renderizar_markdown(
        montar_dossie(
            db_session, escritorio_id=escritorio.id, oab="12345", uf="TO", hoje=HOJE
        )
    )

    assert "12345/TO" in texto
    assert intimacao.numero_processo in texto
    assert "2026-08-05" in texto
    # A frase que separa o Causor de "mais uma IA que escreve petição".
    assert "determinístico" in texto


def test_cli_dossie_oab_grava_arquivo(db_session, escritorio, monkeypatch, tmp_path):
    import app.cli as cli

    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="7",
        publicacao=date(2026, 8, 3),
        data_fatal=date(2026, 8, 5),
    )
    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    saida = tmp_path / "dossie.md"

    rc = cli.main(
        [
            "dossie-oab",
            "--escritorio",
            str(escritorio.id),
            "--oab",
            "12345",
            "--uf",
            "to",
            "--hoje",
            "2026-08-04",
            "--saida",
            str(saida),
        ]
    )

    assert rc == 0
    assert "12345/TO" in saida.read_text(encoding="utf-8")
```

- [ ] **Step 2: Rodar os testes para vê-los falhar**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_dossie_oab.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.relatorios'`

- [ ] **Step 3: Criar o módulo**

Criar `backend/app/relatorios/__init__.py` vazio e `backend/app/relatorios/dossie_oab.py`:

```python
"""Dossiê de uma OAB: o que já existe na carteira do advogado, hoje.

Serve a duas coisas ao mesmo tempo. É o T3' do plano de 90 dias — provar que o
entregável presta, com material real — e é a peça de prospecção: o DJEN é
público e nacional, então o quadro de intimações e prazos de um advogado se monta
sem credencial, sem pareamento e sem conector. É o único artefato do produto que
não pede nada a quem ainda não é cliente.

**Não recalcula a regra de alerta.** O nível vem de ``alertas.radar.classificar``,
a mesma função que o painel (``GET /alertas``) e o e-mail consomem. Um segundo
ponto de decisão faria o dossiê discordar da tela sobre o mesmo prazo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alertas import radar
from app.sor import models

JANELA_PADRAO_DIAS = 15


@dataclass(frozen=True)
class LinhaDossie:
    numero_processo: str | None
    tribunal: str | None
    tipo_comunicacao: str | None
    data_publicacao: date | None
    data_fatal: date | None
    dias_para_vencer: int | None
    nivel: str | None


@dataclass(frozen=True)
class Dossie:
    oab: str
    uf: str
    hoje: date
    janela_dias: int
    total_intimacoes: int
    total_com_prazo: int
    total_em_alerta: int
    linhas: list[LinhaDossie]


def _prazo_aberto_mais_proximo(intimacao: models.Intimacao) -> models.Prazo | None:
    abertos = [prazo for prazo in intimacao.prazos if not prazo.cumprido]
    if not abertos:
        return None
    return min(abertos, key=lambda prazo: prazo.data_fatal)


def montar_dossie(
    session: Session,
    *,
    escritorio_id: int,
    oab: str,
    uf: str,
    hoje: date,
    janela_dias: int = JANELA_PADRAO_DIAS,
) -> Dossie:
    """Monta o quadro da carteira dentro da janela, do prazo mais urgente ao menos."""
    inicio = hoje - timedelta(days=janela_dias)
    stmt = select(models.Intimacao).where(
        models.Intimacao.escritorio_id == escritorio_id
    )

    linhas: list[LinhaDossie] = []
    com_prazo = 0
    em_alerta = 0
    for intimacao in session.scalars(stmt):
        # Publicação é o que o advogado enxerga; disponibilização é o fallback de
        # quem publica sem a data final preenchida.
        publicacao = intimacao.data_publicacao or intimacao.data_disponibilizacao
        if publicacao is None or publicacao < inicio:
            continue
        prazo = _prazo_aberto_mais_proximo(intimacao)
        dias: int | None = None
        nivel: str | None = None
        if prazo is not None:
            com_prazo += 1
            dias = (prazo.data_fatal - hoje).days
            if dias <= radar.JANELA_DIAS:
                nivel = radar.classificar(dias)
                em_alerta += 1
        linhas.append(
            LinhaDossie(
                numero_processo=intimacao.numero_processo,
                tribunal=intimacao.tribunal,
                tipo_comunicacao=intimacao.tipo_comunicacao,
                data_publicacao=publicacao,
                data_fatal=prazo.data_fatal if prazo is not None else None,
                dias_para_vencer=dias,
                nivel=nivel,
            )
        )

    linhas.sort(key=lambda linha: (linha.data_fatal is None, linha.data_fatal or date.max))
    return Dossie(
        oab=oab,
        uf=uf.upper(),
        hoje=hoje,
        janela_dias=janela_dias,
        total_intimacoes=len(linhas),
        total_com_prazo=com_prazo,
        total_em_alerta=em_alerta,
        linhas=linhas,
    )


def _celula(valor: object) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def renderizar_markdown(dossie: Dossie) -> str:
    """Uma página que cabe num WhatsApp e não promete o que não foi conferido."""
    linhas = [
        f"# Intimações da OAB {dossie.oab}/{dossie.uf}",
        "",
        f"Janela: últimos {dossie.janela_dias} dias · referência {dossie.hoje.isoformat()}",
        "",
        f"- Intimações capturadas: **{dossie.total_intimacoes}**",
        f"- Com prazo calculado: **{dossie.total_com_prazo}**",
        f"- Vencendo em até {radar.JANELA_DIAS} dias: **{dossie.total_em_alerta}**",
        "",
        "| Processo | Tribunal | Comunicação | Publicação | Prazo fatal | Dias | Nível |",
        "|---|---|---|---|---|---|---|",
    ]
    for linha in dossie.linhas:
        linhas.append(
            "| {} | {} | {} | {} | {} | {} | {} |".format(
                _celula(linha.numero_processo),
                _celula(linha.tribunal),
                _celula(linha.tipo_comunicacao),
                _celula(linha.data_publicacao),
                _celula(linha.data_fatal),
                _celula(linha.dias_para_vencer),
                _celula(linha.nivel),
            )
        )
    linhas += [
        "",
        "Fonte: DJEN (Diário de Justiça Eletrônico Nacional, CNJ), captura por API "
        "oficial. Os prazos acima são calculados por código determinístico — "
        "contagem em dias úteis, feriados e suspensões — e não por IA.",
    ]
    return "\n".join(linhas) + "\n"
```

- [ ] **Step 4: Rodar os testes do módulo**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_dossie_oab.py -v -k "not cli"`
Expected: PASS nos cinco testes que não usam a CLI; o teste da CLI continua falhando com `invalid choice: 'dossie-oab'`.

- [ ] **Step 5: Ligar o subcomando na CLI**

Em `backend/app/cli.py`, dentro de `_build_parser`, logo depois do bloco `notificar = sub.add_parser("notificar-prazos", ...)` e antes de `return parser`:

```python
    dossie = sub.add_parser(
        "dossie-oab",
        help="Monta o quadro de intimações e prazos de uma OAB (demo e T3')",
    )
    dossie.add_argument("--escritorio", required=True, type=int)
    dossie.add_argument("--oab", required=True)
    dossie.add_argument("--uf", required=True)
    dossie.add_argument(
        "--janela-dias",
        type=int,
        default=15,
        help="Tamanho da janela em dias, contados de hoje para tras",
    )
    dossie.add_argument("--hoje", help="Data de referencia (YYYY-MM-DD); default hoje")
    dossie.add_argument("--saida", help="Arquivo .md de saida; sem isso imprime na tela")
```

E em `main`, como um novo ramo `if args.command == "dossie-oab":` junto dos demais:

```python
    if args.command == "dossie-oab":
        from app.relatorios.dossie_oab import montar_dossie, renderizar_markdown

        hoje = date.fromisoformat(args.hoje) if args.hoje else date.today()
        session = SessionLocal()
        try:
            dossie = montar_dossie(
                session,
                escritorio_id=args.escritorio,
                oab=args.oab,
                uf=args.uf,
                hoje=hoje,
                janela_dias=args.janela_dias,
            )
        finally:
            session.close()
        texto = renderizar_markdown(dossie)
        if args.saida:
            with open(args.saida, "w", encoding="utf-8") as arquivo:
                arquivo.write(texto)
            print(f"dossie gravado em {args.saida}")
        else:
            print(texto)
        return 0
```

- [ ] **Step 6: Rodar a suíte inteira e o lint**

Run: `./.venv/Scripts/python.exe -m pytest -q && ./.venv/Scripts/python.exe -m ruff check .`
Expected: todos os testes passando (os 6 novos inclusive) e ruff sem apontamentos.

- [ ] **Step 7: Commit**

```bash
git add backend/app/relatorios backend/app/cli.py backend/tests/test_dossie_oab.py
git commit -m "feat(relatorios): dossie por OAB, a demo que nao pede credencial"
```

- [ ] **Step 8: Usar de verdade, uma vez, antes de seguir**

Com a OAB do advogado próximo (**pedindo o "pode?" antes** — é dado público, mas a conversa é B2B):

```bash
./.venv/Scripts/python.exe -m app.cli provision-pilot --escritorio "Demo <nome>" --nome "<nome>" --email "<email>" --oab <numero> --uf <uf>
./.venv/Scripts/python.exe -m app.cli poll --oab <numero> --uf <uf> --escritorio <id>
./.venv/Scripts/python.exe -m app.cli dossie-oab --escritorio <id> --oab <numero> --uf <uf> --saida dossie.md
```

Esperado: `dossie.md` com intimações reais e prazos calculados. **Se vier vazio ou errado, este é o achado mais valioso da semana** — registre em `docs/estado.md` antes de qualquer outra coisa.

---

## Task 3: A completude do upload conferida contra o DataJud

O upload é o único caminho de captura sem gate externo, e é justamente o que produz completude *declarada*. O DataJud é nacional, gratuito e já tem cliente pronto: dá para comparar quantos movimentos de juntada o tribunal registra com quantos arquivos o advogado entregou. Isso não vira prova — vira **sinal conferido contra fonte independente**, que é o que faltava para o upload não corroer o diferencial.

**Files:**
- Create: `backend/app/autos/conferencia.py`
- Modify: `backend/app/autos/upload.py` (parâmetro opcional `datajud` em `ingerir_autos_enviados`)
- Modify: `backend/app/api/autos_routes.py:38-51` (campo novo em `CapturaOut`) e `:209-215` (passar o cliente)
- Test: `backend/tests/test_autos_conferencia.py`

**Interfaces:**
- Consumes: `DatajudClient.consultar_processo(numero, *, tribunal) -> ProcessoDTO | None` e `MovimentoDTO.nome` (`app/capture/datajud.py:111`, `:47`); `models.CapturaAutos.evidence` (`app/sor/models.py:448`)
- Produces: `conferir_upload_com_datajud(session, *, capture, processo, arquivos_recebidos, datajud) -> ConferenciaDatajud`, constante `CHAVE_EVIDENCIA = "conferencia_datajud"`, campo `conferencia_datajud: dict | None` em `CapturaOut`

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_autos_conferencia.py`:

```python
"""Conferência do upload contra o DataJud.

Sinal externo, não prova. Divergência é motivo para perguntar ao advogado se
faltou peça — nunca para marcar a captura como falha, porque o DataJud registra
movimento processual, não a lista de peças dos autos.
"""

from datetime import date

import pytest

from app.autos.conferencia import (
    CHAVE_EVIDENCIA,
    conferir_upload_com_datajud,
)
from app.capture.datajud import MovimentoDTO, ProcessoDTO
from app.sor import models


class DatajudFake:
    """Cliente com a mesma superfície de `DatajudClient` usada aqui."""

    def __init__(self, dto: ProcessoDTO | None):
        self._dto = dto
        self.chamadas: list[tuple[str, str]] = []

    def consultar_processo(self, numero_processo: str, *, tribunal: str):
        self.chamadas.append((numero_processo, tribunal))
        return self._dto


def _dto(nomes: list[str]) -> ProcessoDTO:
    return ProcessoDTO(
        numero_processo="10003333820184014300",
        movimentos=[MovimentoDTO(nome=nome) for nome in nomes],
    )


@pytest.fixture
def cenario(db_session):
    esc = models.Escritorio(nome="Escritório Conferência")
    db_session.add(esc)
    db_session.flush()
    processo = models.Processo(
        escritorio_id=esc.id,
        numero="10003333820184014300",
        tribunal="TRF1",
        sistema="PJe",
    )
    db_session.add(processo)
    db_session.flush()
    instancia = models.ProcessoInstancia(
        processo_id=processo.id,
        escritorio_id=esc.id,
        sistema="PJe",
        tribunal="TRF1",
        grau="1",
    )
    db_session.add(instancia)
    db_session.flush()
    capture = models.CapturaAutos(
        escritorio_id=esc.id,
        processo_instancia_id=instancia.id,
        generation=1,
        status="complete",
        fonte="upload",
        evidence={"initial": {"completude": "declarada_pelo_advogado"}},
    )
    db_session.add(capture)
    db_session.flush()
    return capture, processo


def test_divergencia_quando_o_tribunal_registra_mais_juntadas(db_session, cenario):
    capture, processo = cenario
    datajud = DatajudFake(
        _dto(["Juntada de Petição", "Juntada de Documento", "Conclusão"])
    )

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=1,
        datajud=datajud,
    )

    assert resultado.consultado is True
    assert resultado.movimentos == 3
    assert resultado.juntadas == 2
    assert resultado.divergencia is True
    assert datajud.chamadas == [("10003333820184014300", "TRF1")]


def test_sem_divergencia_quando_recebemos_ao_menos_as_juntadas(db_session, cenario):
    capture, processo = cenario
    datajud = DatajudFake(_dto(["Juntada de Petição", "Conclusão"]))

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=3,
        datajud=datajud,
    )

    assert resultado.divergencia is False


def test_conta_juntada_sem_acento_e_em_caixa_alta(db_session, cenario):
    capture, processo = cenario
    datajud = DatajudFake(_dto(["JUNTADA DE PETICAO", "juntada de documento"]))

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=5,
        datajud=datajud,
    )

    assert resultado.juntadas == 2


def test_processo_ausente_no_datajud_nao_vira_divergencia(db_session, cenario):
    capture, processo = cenario

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=1,
        datajud=DatajudFake(None),
    )

    assert resultado.consultado is False
    assert resultado.divergencia is False
    assert resultado.motivo == "processo_nao_encontrado"


def test_sem_tribunal_nao_consulta(db_session, cenario):
    capture, processo = cenario
    processo.tribunal = None
    db_session.flush()
    datajud = DatajudFake(_dto(["Juntada de Petição"]))

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=1,
        datajud=datajud,
    )

    assert resultado.consultado is False
    assert resultado.motivo == "sem_tribunal"
    assert datajud.chamadas == []


def test_falha_do_datajud_nao_derruba_a_captura(db_session, cenario):
    capture, processo = cenario

    class DatajudQuebrado:
        def consultar_processo(self, numero_processo: str, *, tribunal: str):
            raise RuntimeError("DataJud fora do ar")

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=1,
        datajud=DatajudQuebrado(),
    )

    assert resultado.consultado is False
    assert resultado.motivo == "erro_na_consulta"
    assert capture.status == "complete"


def test_resultado_fica_gravado_na_evidencia_sem_apagar_o_que_havia(db_session, cenario):
    capture, processo = cenario
    datajud = DatajudFake(_dto(["Juntada de Petição"]))

    conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=1,
        datajud=datajud,
    )

    assert capture.evidence["initial"]["completude"] == "declarada_pelo_advogado"
    gravado = capture.evidence[CHAVE_EVIDENCIA]
    assert gravado["juntadas"] == 1
    assert gravado["arquivos_recebidos"] == 1
    assert gravado["divergencia"] is False
```

- [ ] **Step 2: Rodar os testes para vê-los falhar**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_autos_conferencia.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.autos.conferencia'`

- [ ] **Step 3: Implementar o módulo**

Criar `backend/app/autos/conferencia.py`:

```python
"""Sinal externo de completude para a captura por upload.

Numa captura de tribunal, a dupla enumeração prova completude: a lista vem de
fora. No upload (``autos/upload.py``) as duas enumerações são a mesma lista que o
advogado entregou, então ``complete`` afirma só *"recebemos exatamente estes
arquivos, íntegros"*.

Este módulo **não** transforma declaração em prova. Ele busca no DataJud — API
pública nacional, já usada na captura — quantos movimentos de juntada o tribunal
registra no processo, e compara com quantos arquivos chegaram. Movimento
processual não é peça dos autos: um movimento pode juntar várias peças e nem toda
peça gera movimento. Por isso a divergência é motivo para **perguntar ao
advogado**, nunca para reprovar a captura, e por isso a chave gravada se chama
sinal, não prova.

Falha do DataJud é registrada e engolida: a captura já está completa quando esta
conferência roda, e derrubar uma captura íntegra por causa de uma API de terceiro
seria trocar um problema real por um imaginário.
"""

from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.capture.datajud import ProcessoDTO
from app.sor import models

#: Chave sob a qual o resultado vive em ``CapturaAutos.evidence``.
CHAVE_EVIDENCIA = "conferencia_datajud"


class ConsultaDatajud(Protocol):
    def consultar_processo(
        self, numero_processo: str, *, tribunal: str
    ) -> ProcessoDTO | None: ...


@dataclass(frozen=True)
class ConferenciaDatajud:
    consultado: bool
    movimentos: int
    juntadas: int
    arquivos_recebidos: int
    divergencia: bool
    motivo: str | None = None


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto)
    return "".join(
        caractere
        for caractere in normalizado
        if unicodedata.category(caractere) != "Mn"
    ).lower()


def contar_juntadas(movimentos) -> int:
    """Movimentos cujo nome menciona juntada — a redação padrão da TPU/CNJ."""
    return sum(
        1
        for movimento in movimentos
        if movimento.nome and "juntada" in _sem_acento(movimento.nome)
    )


def conferir_upload_com_datajud(
    session: Session,
    *,
    capture: models.CapturaAutos,
    processo: models.Processo,
    arquivos_recebidos: int,
    datajud: ConsultaDatajud,
) -> ConferenciaDatajud:
    """Compara os arquivos entregues com as juntadas que o tribunal registra."""
    resultado = _conferir(
        processo=processo, arquivos_recebidos=arquivos_recebidos, datajud=datajud
    )
    capture.evidence = {**(capture.evidence or {}), CHAVE_EVIDENCIA: asdict(resultado)}
    session.flush()
    return resultado


def _conferir(
    *,
    processo: models.Processo,
    arquivos_recebidos: int,
    datajud: ConsultaDatajud,
) -> ConferenciaDatajud:
    vazio = ConferenciaDatajud(
        consultado=False,
        movimentos=0,
        juntadas=0,
        arquivos_recebidos=arquivos_recebidos,
        divergencia=False,
    )
    if not processo.tribunal:
        return ConferenciaDatajud(**{**asdict(vazio), "motivo": "sem_tribunal"})

    try:
        dto = datajud.consultar_processo(processo.numero, tribunal=processo.tribunal)
    except Exception:  # noqa: BLE001 — API de terceiro não derruba captura íntegra
        return ConferenciaDatajud(**{**asdict(vazio), "motivo": "erro_na_consulta"})

    if dto is None:
        return ConferenciaDatajud(
            **{**asdict(vazio), "motivo": "processo_nao_encontrado"}
        )

    juntadas = contar_juntadas(dto.movimentos)
    return ConferenciaDatajud(
        consultado=True,
        movimentos=len(dto.movimentos),
        juntadas=juntadas,
        arquivos_recebidos=arquivos_recebidos,
        divergencia=juntadas > arquivos_recebidos,
    )
```

- [ ] **Step 4: Rodar os testes do módulo**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_autos_conferencia.py -v`
Expected: PASS nos sete testes.

- [ ] **Step 5: Ligar no fluxo de upload**

Em `backend/app/autos/upload.py`, acrescentar o parâmetro opcional e a chamada. A assinatura passa a ser:

```python
def ingerir_autos_enviados(
    session: Session,
    *,
    processo_instancia: models.ProcessoInstancia,
    usuario_id: int | None,
    arquivos: list[ArquivoEnviado],
    object_store: ObjectStore,
    datajud: ConsultaDatajud | None = None,
) -> models.CapturaAutos:
```

E o `return` final vira:

```python
    # A enumeração final é a mesma da inicial por construção; a conferência
    # segue rodando porque é ela que valida que todo item ficou `verified`.
    capture = autos_service.finalize_capture(
        session, capture=capture, final_manifest=manifesto
    )
    if datajud is not None:
        # Sinal externo, opcional por desenho: sem cliente injetado o upload
        # continua funcionando exatamente como antes.
        conferir_upload_com_datajud(
            session,
            capture=capture,
            processo=processo_instancia.processo,
            arquivos_recebidos=len(arquivos),
            datajud=datajud,
        )
    return capture
```

Com o import no topo do arquivo:

```python
from app.autos.conferencia import ConsultaDatajud, conferir_upload_com_datajud
```

- [ ] **Step 6: Expor na API**

Em `backend/app/api/autos_routes.py`, acrescentar o campo ao `CapturaOut` (depois de `fonte`, linha 51):

```python
    conferencia_datajud: dict | None = None
```

E, como `evidence` não é serializado inteiro, preencher na rota de upload — trocar o `return capture` de `upload_autos` (linha 223) por:

```python
    session.commit()
    saida = CapturaOut.model_validate(capture)
    return saida.model_copy(
        update={"conferencia_datajud": (capture.evidence or {}).get(CHAVE_EVIDENCIA)}
    )
```

E passar o cliente na chamada (linha 209):

```python
        capture = ingerir_autos_enviados(
            session,
            processo_instancia=instancia,
            usuario_id=current.usuario_id,
            arquivos=enviados,
            object_store=get_object_store(),
            datajud=DatajudClient(),
        )
```

Com os imports:

```python
from app.autos.conferencia import CHAVE_EVIDENCIA
from app.capture.datajud import DatajudClient
```

- [ ] **Step 7: Rodar a suíte inteira e o lint**

Run: `./.venv/Scripts/python.exe -m pytest -q && ./.venv/Scripts/python.exe -m ruff check .`
Expected: tudo verde, incluindo `tests/test_autos_upload.py` e `tests/test_autos_upload_api.py` — que não injetam `datajud` e por isso devem continuar passando sem alteração.

- [ ] **Step 8: Registrar a distinção onde ela é lida**

Em `docs/estado.md`, no item de 2026-07-31 sobre o upload, acrescentar uma frase: a completude segue **declarada**, e agora vem acompanhada de um sinal conferido contra o DataJud (`evidence.conferencia_datajud`), que não a converte em prova.

```bash
git add backend/app/autos/conferencia.py backend/app/autos/upload.py backend/app/api/autos_routes.py backend/tests/test_autos_conferencia.py docs/estado.md
git commit -m "feat(autos): upload conferido contra o DataJud, sinal e nao prova"
```

---

## Ordem, e o que não está aqui

**Ordem:** Task 1 → Task 2 (Steps 1–7) → Step 8 da Task 2 com um advogado de verdade → G1 → Task 3.

A Task 3 vem por último de propósito: ela defende o diferencial durante o piloto, mas não move a métrica que está em zero. Se a semana apertar, é ela que cai.

**Explicitamente fora deste plano** (mantendo o que o plano de 90 dias já parou): Tasks 6–9 de conectores, `MniFilingDriver`, qualquer trabalho novo de MNI, billing, RAG, novos tribunais, novos agentes. Nada disso antes de uma minuta assinada por um advogado real.

**A quinta divergência da pesquisa (reancorar o discurso agora que o Jus IA é gratuito em todos os planos do Jusbrasil) não virou tarefa** porque não é engenharia: ela vive no rodapé do dossiê da Task 2 — *"prazos calculados por código determinístico, não por IA"* — e na âncora de preço do plano de 90 dias (paralegal, R$ 2,5–4 mil/mês; nunca software de gestão). Se aparecer em mais lugares, aparece como texto de tela, não como código novo.

**Critério de parada:** se ao fim da Task 2, Step 8, o dossiê de uma OAB real não mostrar prazo que o advogado reconheça como certo, pare o plano e trate isso como o achado da semana — é a única falha aqui que invalida o produto, e nenhuma das outras tarefas conserta.
