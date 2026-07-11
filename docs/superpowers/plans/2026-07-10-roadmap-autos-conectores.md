# Autos integrais e conectores nacionais — Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar captura autenticada, íntegra e verificável dos autos e conectores reais PJe/eproc/e-SAJ/Projudi, mantendo a redação bloqueada quando o contexto do processo não estiver completo.

**Architecture:** O backend continua como SOR e coordenador; um agente Windows executa Playwright na máquina do advogado, onde ficam sessão, certificado e assinadores. Cada sistema implementa contratos separados de leitura (`CourtReaderDriver`) e protocolo (`FilingDriver`). PDFs privados entram por URL pré-assinada no storage, são verificados por hash, extraídos/OCR, indexados e transformados em um dossiê citado somente após prova de completude.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy/Alembic, PostgreSQL, Playwright, S3/Supabase Storage privado, boto3, PyMuPDF, Tesseract, PostgreSQL Full Text Search, Next.js/TypeScript.

## Global Constraints

- Nenhuma senha, PIN, OTP, certificado, cookie ou perfil Playwright entra em prompt, log, job ou banco do backend.
- A sessão autenticada vive no agente local; o backend recebe somente comandos, metadados, evidências e arquivos capturados.
- Captura autenticada dos autos do próprio advogado é uma capacidade separada da captura pública DJEN/DataJud; nenhuma rota pública será raspada.
- Documento só fica `verified` depois de download, validação de formato, recomputação SHA-256 no backend e persistência privada.
- Captura de uma instância só fica `complete` quando enumeração inicial e enumeração de conferência forem idênticas e todos os itens possuírem versão verificada.
- Processo só fica `complete` quando todas as instâncias solicitadas (`1`, `2`) estiverem `complete` ou `not_applicable` com evidência do conector.
- Redação e protocolo são fail-closed: contexto incompleto bloqueia a ação; override exige advogado, justificativa e `AuditLog` imutável.
- Todo conector real começa read-only; ações irreversíveis permanecem atrás do Gate OAB.
- `CAUSOR_FILING_MODE=sandbox` continua sendo o default até cada perfil possuir teste live aprovado.
- Testes live nunca rodam na CI e nunca usam processo com prazo ativo ou risco operacional.
- Não usar embeddings pagos no caminho inicial; busca textual PostgreSQL e resumos citados são suficientes para o primeiro corte.
- Storage é privado, sem URL pública; acesso é por URL assinada curta e auditada.

---

## Planos executáveis

1. [Fundação de automação judicial e agente local](2026-07-10-fundacao-automacao-judicial-agente-local.md)
2. [Autos integrais, OCR, contexto citado e bloqueio fail-closed](2026-07-10-autos-integra-contexto-citado.md)
3. [Conectores reais PJe, eproc, e-SAJ e Projudi](2026-07-10-conectores-reais-multissistema.md)

## Dependências

```text
Plano 1 — Fundação
  ├── instâncias/graus por processo
  ├── contratos genéricos
  ├── storage privado + upload tickets
  └── agente local + comandos
          │
          ├───────────────┐
          ▼               ▼
Plano 2 — Autos       Plano 3 — Conectores
  ├── manifesto          ├── perfis reais
  ├── hashes/OCR         ├── PJe
  ├── chunks/FTS         ├── eproc
  └── dossiê/gate        ├── e-SAJ
          │              └── Projudi
          └───────┬───────────┘
                  ▼
          Homologação nacional
```

## Marcos de entrega

### Marco A — Fundação pronta

Critérios cumulativos:

- Agente Windows pareado com token revogável.
- Perfil persistente de navegador criado por `(usuario, sistema, tribunal, grau)`.
- Backend publica comando, agente reivindica uma única vez e devolve resultado idempotente.
- Upload direto para storage privado funciona sem expor credenciais S3 ao agente.
- `ProcessoInstancia` representa primeiro e segundo grau sem depender de `getattr(..., "grau")`.
- Testes unitários, API e integração local verdes.

### Marco B — Primeiro processo PJe integral

Critérios cumulativos:

- PJe enumera todos os documentos e anexos de uma instância real.
- Todos os arquivos possuem SHA-256 recomputado, versão imutável e URI privada.
- Nova enumeração após download confirma que o conjunto não mudou.
- PDFs textuais e digitalizados produzem trechos por página.
- Dossiê mostra inventário de 100% dos documentos e citações verificáveis.
- Minuta fica bloqueada quando um item falha e liberada quando a captura fica completa.

### Marco C — Quatro famílias reais

Critérios cumulativos:

- Um perfil live aprovado para PJe, eproc, e-SAJ e Projudi.
- Cada família lê autos e prepara petição intermediária até o gate.
- PJe não usa mais `page.wait_for_text`; comprovante é identificado por locator real e armazenado.
- e-SAJ/eproc coexistentes no TJSP são resolvidos por processo/instância, não apenas por tribunal.
- Falha de layout produz `layout_unknown`, evidência e bloqueio; nunca sucesso presumido.

### Marco D — Cobertura nacional publicável

Critérios cumulativos:

- Matriz de cobertura lista tribunal, sistema, grau, versão/perfil e última validação live.
- Todo tribunal comercialmente suportado possui leitura testada em 1º e 2º grau ou evidência de não aplicabilidade.
- Casos sigilosos foram testados em cada família com advogado autorizado.
- Health checks read-only detectam expiração de sessão e mudança de layout.
- Taxa de captura completa e causas de incompletude são observáveis por sistema/perfil.
- O lançamento não anuncia tribunal/perfil em estado `experimental`, `degraded` ou `blocked`.

## Ordem de execução

- [x] **Passo 1:** Executar integralmente o Plano 1 e aprovar o Marco A. ✅ 2026-07-10 (merged em `main`; backend 334 passed, frontend 32 passed, typecheck/build verdes)
- [x] **Passo 2:** Executar as tarefas genéricas do Plano 2 usando `FakeCourtReaderDriver`. ✅ 2026-07-10 (Tasks 1–10 em `main`; backend 385 passed, ruff ok, frontend 37 passed, typecheck/build verdes)
- [ ] **Passo 3:** Executar as Tasks 1–5 do Plano 3 (perfis/registry, login unificado no agente, remoção do vault de sessão, simuladores, split servidor/agente) e, com a conta PJe do advisor, o perfil PJe read-only (Task 6).
- [ ] **Passo 4:** Voltar ao Plano 2 e homologar o primeiro processo PJe integral (Marco B).
- [ ] **Passo 5:** Corrigir e homologar o protocolo PJe até `ready_to_sign`; manter `submit=False` no primeiro live.
- [ ] **Passo 6:** Repetir leitura e protocolo, nesta ordem, para eproc, e-SAJ e Projudi.
- [ ] **Passo 7:** Aprovar o Marco C com os quatro acessos do advisor.
- [ ] **Passo 8:** Abrir ondas de perfis por tribunal/grau e preencher a matriz até o Marco D.

## O que pode começar agora e o que depende do advisor

**Executável imediatamente:** Plano 1 completo; Tasks 1–9 genéricas do Plano 2 usando driver fake; Tasks 1–5 e 10–11 do Plano 3 com simuladores, registry, login unificado no agente, remoção do vault de sessão e assistente JIT.

**Bloqueado por acesso real:** Tasks 6–9 (PJe/eproc/e-SAJ/Projudi) do Plano 3, homologação do Marco B e promoção de qualquer perfil a `supported`.

**Faixa de calendário, assumindo acesso sem interrupções:** fundação em 1–2 semanas; pipeline genérico de autos/contexto em 2–3 semanas; primeiro PJe integral em mais 1–2 semanas; cada nova família de referência em 1–3 semanas. A certificação nacional permanece trabalho de meses porque o gargalo é acesso e variação de portal, não escrita de código.

## Regras para as contas reais

Para cada acesso fornecido pelo advisor, registrar antes do teste:

```yaml
sistema: PJe | EPROC | e-SAJ | Projudi
tribunal: SIGLA
grau: "1" | "2"
url_login: https://...
url_processo: https://... | null
processo_teste: numero CNJ
sigiloso: true | false
permite_leitura: true
permite_upload_rascunho: true | false
permite_protocolo: false
assinador: PJeOffice | WebSigner | outro | nenhum
responsavel_juridico: nome interno
janela_de_teste: ISO-8601
```

O arquivo preenchido contém dado operacional e fica fora do Git. No repositório entra apenas fixture sanitizada, sem número real, partes, CPF/CNPJ, teor ou cookies.

## Stop conditions

Interromper a automação e devolver controle ao advogado quando ocorrer qualquer um:

- CAPTCHA ou desafio não previsto.
- Sessão expirada, perfil inadequado ou acesso negado.
- Documento sigiloso listado mas não baixável.
- Paginação sem marcador confiável de término.
- Contagem ou fingerprint diferente na enumeração de conferência.
- Download vazio, HTML no lugar de PDF ou hash divergente.
- Layout sem perfil aprovado.
- Assinador solicita PIN/OTP fora da janela do advogado.
- Comprovante ou número de protocolo não pode ser verificado.

## Verificação global antes do lançamento

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
cd ..\frontend
pnpm test
pnpm typecheck
pnpm build
```

Esperado: todos os comandos retornam código `0`; testes live continuam opt-in e são registrados separadamente na matriz de cobertura.
