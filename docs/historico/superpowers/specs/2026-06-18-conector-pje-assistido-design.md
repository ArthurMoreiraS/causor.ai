# Conector PJe assistido (Playwright) — Spec + Plano de Execução

**Data:** 2026-06-18
**Autor:** Arthur + Claude (brainstorming)
**Status:** aprovado para execução; falta rodar o spike no treino
**Escopo:** preencher o miolo Playwright do conector PJe, mantendo o gate humano antes do ato irreversível.

---

## 0. Resumo de uma frase

Transformar `PjeAssistedConnector.prepare_filing` (hoje um stub que só devolve um
checkpoint) num fluxo real de navegador que **reaproveita a sessão do advogado**,
localiza um processo PJe existente, abre uma **petição intermediária**, anexa a
minuta em PDF e **para em `ready_to_sign`** — sem nunca assinar nem protocolar.

---

## 1. Motivação e posicionamento de mercado (por que vale a pena)

- O **fosso** do Causor é a **ação autônoma** (operar o tribunal), não o
  monitoramento (commodity: Astrea, Projuris, Legal One, Digesto, Escavador).
- A minuta também está virando commodity (Jusbrasil Jus IA, AdvTechPro). O
  capital está indo para agentes de ação: **Enter** (Série A R$200M, Sequoia +
  Founders Fund, contencioso de massa).
- Já existem players de **protocolo automático** (e-Protocol, doc9, DWRPA,
  Finch), mas no modelo **RPA-bureau** com a falha grave de guardar senha/cert
  do advogado em script/planilha. **O Causor ganha por segurança** (vault, sem
  senha, gate humano, auditoria imutável).
- **Pressão regulatória crescente** valida a arquitetura: Resolução CNJ
  **615/2025** (governança + supervisão humana) e o caso do **STJ (mai/2026)**
  que flagrou *prompt injection* em petições. Quem fizer "robô que assina
  sozinho" apanha; quem tem gate + auditoria, não.

**Veredito:** seguir. Mas **começar pelo spike** (passo mais barato que mais
reduz risco) antes do build completo.

---

## 2. Restrições inegociáveis (do CLAUDE.md + docs/protocolo-pje-vault.md)

1. **Nunca guardar senha do PJe, certificado, `.pfx`, chave privada ou OTP.** O
   advogado autentica ele mesmo no PJe real; o Causor guarda só o
   `storage_state` (cookies/sessão) no vault criptografado.
   - ⚠️ **Correção de uma decisão anterior:** a ideia de "login gov.br/CPF+senha
     guardado no vault" foi **descartada**. Vale o modelo de sessão assistida.
2. **Gate humano antes de qualquer ato irreversível** (assinar/protocolar). O
   conector **não implementa** o clique final de assinar no v1 — o botão nem é
   mapeado, então é impossível cometer o ato por bug.
3. **Auditoria imutável** em cada passo (já existe via `_audit` em `queue/jobs.py`).
4. **APIs oficiais antes de scraping**; Playwright é só para **ação**, com
   fallback humano quando captcha/layout bloquear. **Não burlar captcha.**

---

## 3. O que JÁ está pronto (não reconstruir)

| Peça | Arquivo | Estado |
|---|---|---|
| Orquestração do job + gate de aprovação + auditoria | `backend/app/queue/jobs.py` → `run_pje_assisted_protocol_job` | ✅ pronto |
| Confirmação manual do protocolo final | `queue/jobs.py` → `confirm_manual_protocol` | ✅ pronto |
| Executor fake (mantém máquina de estados) | `queue/jobs.py` → `run_fake_protocol_job` | ✅ pronto |
| Montagem do pacote a partir do SOR | `backend/app/filing/package.py` → `build_pje_package` | ✅ pronto |
| Dataclasses do pacote/checkpoint | `backend/app/connectors/pje/connector.py` | ✅ pronto |
| Endpoints `protocolar/async`, `protocolar/confirmar`, `pje-sessoes` | `backend/app/api/main.py` + `schemas.py` | ✅ pronto |
| Vault que rejeita campos de senha/cert; guarda `storage_state` | `backend/app/vault/service.py` | ✅ pronto |

**O único stub real:** `PjeAssistedConnector.prepare_filing` em
`connectors/pje/connector.py` — devolve checkpoint sem abrir navegador.

---

## 4. Arquitetura-alvo

```
peticao aprovada (SOR)
  → run_pje_assisted_protocol_job (queue/jobs.py)  [JÁ EXISTE]
      → build_pje_package                          [JÁ EXISTE]
      → render_minuta_pdf(peticao.conteudo)        [NOVO]  app/filing/render.py
      → PjeAssistedConnector.prepare_filing(...)   [REESCREVER]
            → PjeBrowserSession (storage_state do vault)  [NOVO]
            → ProcessoPage.localizar(numero)              [NOVO]
            → PeticionarPage.abrir_intermediaria()        [NOVO]
            → PeticionarPage.selecionar_tipo(tipo)        [NOVO]
            → PeticionarPage.anexar_pdf(pdf_bytes)        [NOVO]
            → captura evidências (screenshots)            [NOVO]
            → PARA em ready_to_sign  (nunca assina)
      → grava resultado + auditoria                [JÁ EXISTE]
  → advogado assina/envia no PJe/PJeOffice
  → confirm_manual_protocol(protocolo)             [JÁ EXISTE]
```

### Componentes novos (cada um testável isolado)

1. **`backend/app/filing/render.py`** — `render_minuta_pdf(texto: str, *, meta: dict) -> bytes`.
   Função pura: texto da minuta → PDF. Sugestão de lib: `reportlab` (puro
   Python, sem dependência de navegador headless) ou `weasyprint` (HTML→PDF, se
   quiser layout mais rico). **Decisão pendente** — ver seção 8.
2. **`backend/app/connectors/pje/session.py`** — `PjeBrowserSession`:
   - sobe Playwright (`chromium`), cria contexto a partir do `storage_state`
     recuperado do vault;
   - **guard treino-only**: recusa rodar se a `base_url` não estiver na allowlist
     de homologação, salvo `CAUSOR_PJE_ALLOW_PROD=1` explícito;
   - garante teardown (context manager).
3. **`backend/app/connectors/pje/pages/`** — page objects, um por etapa, com os
   seletores isolados:
   - `login.py` → `LoginPage` (apenas detectar se a sessão está válida; **não**
     faz login com senha);
   - `processo.py` → `ProcessoPage.localizar(numero_processo)`;
   - `peticionar.py` → `PeticionarPage` (abrir petição intermediária, selecionar
     tipo, anexar PDF, ler estado da tela de assinatura **sem clicar**).
4. **`connector.py` reescrito** — `prepare_filing` passa a orquestrar
   session + pages, captura evidência e devolve `PjeFilingCheckpoint` com
   `checkpoint="ready_to_sign"`, `irreversible=False`, e `evidence` incluindo
   caminhos/URIs das screenshots e a URL do rascunho (se o PJe persistir).

### Decisão empírica do spike (o "pulo do gato")

Confirmar no treino: **o PJe guarda a petição anexada mas não assinada como
rascunho recuperável?**
- **Guarda** → Caminho A pleno: anexa + salva rascunho; advogado abre o PJe dele
  e assina. `evidence.draft_url` aponta pro rascunho.
- **Não guarda** → mesmo conector cai para modo "evidência" (Caminho C):
  retorna checkpoint provando que chegou na tela, sem rascunho persistido.

---

## 5. Máquina de estados (do gate)

```
prepared → session_ok → processo_localizado → peticionamento_aberto
  → tipo_selecionado → minuta_anexada → ready_to_sign
        ⟂ FIM DO ROBÔ
  [advogado assina no PJe] → confirm_manual_protocol → protocolada
```

Estados de falha que **param com segurança** (gravam motivo + evidência no audit,
status de job `failed`, sem retry cego):
- `sessao_invalida` (storage_state expirou → pedir nova sessão assistida);
- `captcha_detectado` (→ `precisa_do_advogado`, nunca burlar);
- `processo_nao_encontrado`;
- `layout_desconhecido` (seletor não casou → page object precisa atualização).

---

## 6. UI alvo (frontend) — modal "Protocolo PJe"

(De `docs/proximas-sessoes-pje-assistido.md`.) Timeline com etapas:
Login no PJe → Processo localizado → Peticionamento aberto → Minuta anexada →
Pronto para assinatura (`ready_to_sign`) → Protocolo confirmado.

Estados por etapa: `pendente` · `executando` · `concluido` · `bloqueado` ·
`precisa_do_advogado`.

Botões: `Abrir sessão PJe` · `Continuar automação` · `Assumir manualmente` ·
`Registrar protocolo final` · `Ver auditoria` · `Cancelar job`.

> O frontend é **fase 2** desta entrega; o spec foca no backend/conector.

---

## 7. Estratégia de testes (TDD)

1. **Unitário sem navegador** (`backend/tests/`): `page` e `session` fakes
   verificam a orquestração de `prepare_filing` — transições de estado, que
   **para** em `ready_to_sign`, que grava auditoria, que **nenhum segredo vaza
   em log/payload** (assert sobre conteúdo de audit/payload).
2. **Page objects contra HTML salvo**: baixar HTML real do treino e testar os
   seletores contra os fixtures (`backend/tests/fixtures/pje/*.html`).
3. **`render.py`**: PDF gerado tem o texto esperado (extrair texto do PDF e
   conferir); bytes começam com `%PDF`.
4. **Live opt-in** (`RUN_LIVE_PJE=1`): roda contra o treino com sessão
   descartável; **fora do CI** padrão. Espelha o padrão `RUN_LIVE` já usado em
   `tests/test_live_integration.py`.

Meta de disciplina: escrever os testes de orquestração **antes** de reescrever
`prepare_filing`.

---

## 8. Decisões pendentes (resolver no início da execução)

| # | Decisão | Recomendação inicial |
|---|---|---|
| D1 | Lib de PDF | `reportlab` (sem headless extra; minuta é texto simples). Reavaliar se precisar de formatação rica. |
| D2 | Versão do PJe alvo | confirmar 1º ou 2º grau no treino; começar pelo **1º grau**. |
| D3 | Tipo de petição intermediária do 1º fluxo | definir 1 tipo só (ex.: "Petição (outras)" / "Manifestação"). |
| D4 | Onde guardar screenshots de evidência | bucket/Storage (Supabase Storage) com URI no audit; em dev, pasta local. |

---

## 9. Informações necessárias para rodar o spike (BLOQUEADORES)

Sem isto, o spike não roda (de `docs/proximas-sessoes-pje-assistido.md`):
- [ ] **URL do PJe treino/homologação** usado.
- [ ] **1º grau ou 2º grau.**
- [ ] **Processo de teste** existente nesse ambiente (número).
- [ ] **Tipo de petição intermediária** do primeiro fluxo.
- [ ] Como o advogado abre a **sessão assistida** (PJeOffice na máquina? login
      gov.br no navegador do worker?).
- [ ] Credencial **descartável** de treino para o login manual da sessão.

---

## 10. Plano de execução em fases

### Fase 0 — Spike de descoberta (treino) ⟵ COMEÇAR AQUI
**Objetivo:** mapear o fluxo real e responder a pergunta da seção 4.
- Subir Playwright local, abrir o PJe treino, **logar manualmente**, exportar
  `storage_state`.
- Reabrir contexto só com o `storage_state` e confirmar que a sessão persiste.
- Navegar até um processo existente; abrir peticionamento intermediário;
  selecionar tipo; anexar um PDF dummy.
- **Responder:** o PJe guarda rascunho não assinado? Salvar HTML/prints de cada
  etapa como fixtures.
- **Entregável:** relatório curto + fixtures em `backend/tests/fixtures/pje/`.
- **Não** escrever conector "de produção" ainda — só descobrir.

### Fase 1 — `render.py` (minuta → PDF)
- TDD: teste primeiro. Implementar `render_minuta_pdf`. Plugar no job
  (passar `pdf_bytes` ao pacote/conector).

### Fase 2 — `PjeBrowserSession` + guard treino-only
- TDD do guard (recusa prod sem flag). Implementar sessão a partir do vault
  `storage_state`. Context manager + teardown.

### Fase 3 — Page objects (com base nos fixtures da Fase 0)
- `ProcessoPage`, `PeticionarPage`. Testes contra HTML salvo.

### Fase 4 — Reescrever `prepare_filing`
- Orquestrar session + pages + evidência; **parar** em `ready_to_sign`.
- Garantir que `run_pje_assisted_protocol_job` continua passando no gate e
  auditoria. Testes de orquestração (fakes) primeiro.

### Fase 5 — Teste live opt-in (treino)
- `RUN_LIVE_PJE=1` ponta a ponta no treino, sessão descartável.

### Fase 6 — Frontend modal "Protocolo PJe" (fase 2 do produto)
- Timeline + botões da seção 6, consumindo os endpoints existentes.

---

## 11. Fora de escopo (não fazer agora)

Petição inicial · custas · múltiplos anexos complexos · segredo de justiça ·
múltiplos tribunais · captcha automatizado · assinatura em nuvem
(`cloud_certificate` é modo **futuro**) · fallback A1 cifrado · A3/token físico.

---

## 12. Como retomar (checklist para a próxima sessão)

1. Ler este doc + `docs/protocolo-pje-vault.md` + `docs/proximas-sessoes-pje-assistido.md`.
2. Coletar os bloqueadores da seção 9.
3. Resolver D1–D4 (seção 8).
4. Rodar **Fase 0 (spike)** e atualizar a seção 4 com o resultado da persistência.
5. Seguir Fases 1→5 em TDD; frontend (Fase 6) por último.
6. Transformar este spec em plano detalhado com a skill `writing-plans` se quiser
   granularidade por tarefa.
