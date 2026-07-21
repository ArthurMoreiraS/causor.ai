# Leitura oficial dos autos via MNI — Design

Data: 2026-07-21. Status: aprovado para implementação (decisões de escopo
confirmadas pelo usuário; detalhes técnicos com defaults registrados aqui).

## Problema

A captura autenticada dos autos hoje depende exclusivamente do agente local
(Playwright na máquina do advogado): exige agente online, um conector por
sistema e homologação live por perfil. O MNI (Modelo Nacional de
Interoperabilidade, Res. CNJ 65/2008 + Provimento 355/2018) é o webservice
SOAP oficial que os tribunais expõem para consulta de processo e teor de
documento — gratuito, server-to-server, sem navegador, sem CAPTCHA. Onde o
MNI do tribunal funcionar, os autos íntegros chegam pelo caminho oficial, e a
captura fica agendável sem a máquina do advogado.

## Decisões de escopo (confirmadas)

1. **Só leitura.** `consultarProcesso` (metadados + lista de documentos +
   teor). Protocolo (`entregarManifestacaoProcessual`) fica fora; o caminho de
   protocolo continua sendo o agente local até `ready_to_sign`.
2. **Backend direto.** O cliente SOAP roda no backend hospedado, como
   DJEN/DataJud. A credencial MNI fica no vault (localdev/supabase) — a
   política de custódia atualizada (AGENTS.md §1) permite.
3. **API + UI mínima.** Endpoints de credencial + bloco "Consulta oficial
   (MNI)" na seção Acesso aos tribunais das Configurações. Sem mudança no
   assistente JIT nesta entrega.
4. **Transporte artesanal.** `httpx` + templates de envelope + `lxml`. Sem
   `zeep`: WSDL de tribunal é frequentemente quebrado/inacessível e a lib
   WSDL-first falha na construção do cliente. Envelope fixo do MNI 2.2.2
   (intercomunicação), perfis por tribunal absorvem variações.

## Arquitetura

O MNI entra como **fonte nova por um contrato existente**: um
`MniReaderDriver` implementa `CourtReaderDriver`
(`app/connectors/contracts.py`) e alimenta o pipeline do Plano 2 (manifesto,
hash, OCR, chunks, dossiê, gate) sem alterá-lo. A diferença é o executor: em
vez de comando enfileirado para o agente, a captura roda **in-process num job
persistente** do backend.

```
capturar_autos (API)
  └─ open_capture(instancia)
       ├─ credencial MNI ativa p/ tribunal + perfil MNI p/ (tribunal, grau)?
       │    sim → CapturaAutos(fonte="mni") + job `mni_capture`
       │    não → caminho atual intacto: comando `read_process` p/ agente
       │          (CapturaAutos com fonte="agente")
  worker (cli process-autos-due)
  └─ drena `mni_capture`:
       enumerate_documents (consulta 1)
       → record_initial_manifest
       → p/ cada doc: download teor → put_bytes no ObjectStore
         → confirm_document_upload (recomputa SHA-256, valida PDF)
       → enumerate_documents (consulta 2)
       → finalize_capture (fingerprints idênticos ⇒ complete)
```

A prova de completude do Plano 2 se aplica sem exceção: duas enumerações com
fingerprint idêntico, todo item verificado, magic bytes de PDF, não-PDF fica
`unsupported_mime` e bloqueia o contexto.

## Componentes

Novo pacote `backend/app/connectors/mni/`:

- **`client.py`** — transporte SOAP: monta envelope de `consultarProcesso`
  (MNI 2.2.2), autentica com `idConsultante`/`senhaConsultante`, chama via
  `httpx`, parseia com `lxml`. Duas operações públicas:
  `consultar_processo(numero)` → metadados + lista de documentos (sem teor);
  `baixar_documentos(numero, ids)` → mesmo `consultarProcesso` com o elemento
  `documento` pedindo o conteúdo (base64) dos ids. Timeouts e teto de tamanho
  de resposta configuráveis. A senha nunca aparece em log/erro/repr.
- **`profiles.py`** — `MniEndpointProfile(tribunal, grau, url_endpoint,
  versao, verificado)` + registry em código, no padrão de
  `capture/court_routing.py` (best-effort, `verificado=False` até conferido).
  Sem perfil registrado para `(tribunal, grau)` ⇒ MNI indisponível para a
  rota (fail-closed, cai no agente).
- **`reader.py`** — `MniReaderDriver(CourtReaderDriver)`:
  `enumerate_documents` → `CourtManifestSnapshot` com `external_id` =
  `idDocumento` do tribunal, `cursor_complete=True` somente com resposta
  `sucesso` completa (MNI devolve a lista inteira; resposta parcial/fault ⇒
  erro canônico), `source_fingerprint` = SHA-256 da lista ordenada de
  (idDocumento, tipo, dataHora, mimetype). `download_document` → bytes do
  base64, com validação de tamanho.
- **`executor.py`** — dirige `record_initial_manifest` /
  `confirm_document_upload` / `finalize_capture` (funções existentes de
  `autos/service.py`) usando o driver; grava objetos na convenção de chave
  existente (`tenant/.../{sha256}.bin`). Erro canônico marca a captura
  `failed`/`incomplete` com `error_code`; nunca deixa job `running`.
- **`credentials.py`** — CRUD da credencial com segredo no vault (reusa os
  helpers `_store_secret_reference`/`_load_secret_from_reference` de
  `vault/service.py`, expostos como funções próprias para MNI), auditoria em
  toda mutação.

### Modelo de dados

- Nova tabela **`mni_credencial`**: `escritorio_id` (FK, unique junto com
  `tribunal`), `tribunal`, `id_consultante`, `referencia_vault` (senha),
  `ativo`, `last_validated_at`, `created_by_usuario_id`. Credencial é por
  tribunal (o mesmo credenciamento cobre 1º/2º grau; o endpoint por grau vem
  do perfil).
- **`captura_autos.fonte`**: `String(10)`, default `"agente"`, valores
  `"agente" | "mni"`. Exposta em `AutosStatusOut` para a UI mostrar a origem.
- Migração Alembic única para as duas mudanças.

### Erros

Mapeamento para os erros canônicos existentes (`connectors/errors.py`):
falha de autenticação → `AccessDenied`; fault/resposta inválida ou versão
inesperada → `LayoutUnknown` (com `safe_detail` do código do fault); teor
ausente/base64 inválido/tamanho excedido → `DocumentDownloadFailed`;
indisponibilidade HTTP/timeout → novo **`MniUnavailable`**
(`code="mni_unavailable"`, `retryable=True`, `requires_human=False`).
Documento sigiloso listado sem teor → item `failed` ⇒ captura `incomplete`
(stop condition existente).

### API

- `POST /mni/credenciais` `{tribunal, id_consultante, senha}` → cria (senha
  direto pro vault, nunca ecoada).
- `GET /mni/credenciais` → lista mascarada (tribunal, id parcial, status,
  `last_validated_at`).
- `DELETE /mni/credenciais/{id}` → desativa + auditoria.
- `POST /mni/credenciais/{id}/testar` `{numero_processo}` → chama
  `consultar_processo` (metadados apenas); sucesso grava
  `last_validated_at`; erro devolve o código canônico.

Todas com isolamento por `escritorio_id` como as rotas existentes.

### Frontend

Em `SettingsModal` → seção "Acesso aos tribunais", novo bloco **"Consulta
oficial (MNI)"**: lista de credenciais (tribunal, status, última validação),
form de cadastro (tribunal, idConsultante, senha), ações Testar e Revogar.
`lib/api.ts` ganha as quatro chamadas. `ProcessContextStatus`/painel Autos
mostram a fonte da captura ("via MNI" / "via agente") a partir do novo campo.

## Testes

- **Unit:** parsing de fixtures XML sanitizadas (consulta com 3 docs incl.
  anexo vinculado e um sigiloso, fault de autenticação, resposta parcial);
  fingerprint estável; senha ausente de `repr`/log; perfil fail-closed.
- **Simulador:** `connectors/simulators/mni.py` servindo SOAP sintético no
  padrão dos simuladores existentes (IDs `SIM-DOC-001..003`, PDFs sem dado
  real, teor em base64, rota de auth-fail). Teste de integração dirige o
  executor completo contra o simulador ⇒ `CapturaAutos.complete`, chunks
  extraídos, contexto `ready` (pipeline Plano 2 intocado).
- **Rota/roteamento:** com credencial+perfil ativos, `capturar_autos` cria
  captura `fonte="mni"` sem `agent_command`; sem credencial, cria comando de
  agente como hoje (regressão).
- **Live opt-in:** `RUN_MNI_LIVE=1` + env com tribunal/processo autorizado;
  nunca roda em CI. Só após credenciamento real.

## Fora de escopo (explícito)

- `entregarManifestacaoProcessual` (protocolo via MNI).
- Integração do assistente JIT com o caminho MNI.
- Credenciamento em si (processo administrativo por tribunal; runbook curto
  em `docs/operacao/` fica para quando o primeiro ofício for enviado).
- Health-check periódico de credencial MNI (o botão Testar cobre o piloto).

## Riscos aceitos

- Variação real dos MNIs por tribunal só será conhecida no primeiro
  credenciamento; o desenho absorve isso em `profiles.py` + fixtures novas,
  sem tocar contrato/pipeline.
- A operação exata de teor varia entre implementações (alguns tribunais
  limitam documentos por chamada); o executor baixa em lotes de tamanho
  configurável desde o início.
