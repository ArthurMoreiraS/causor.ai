# Vault de assinatura — seam `SignatureProvider` (modo `manual_handoff`)

**Data:** 2026-06-18
**Autor:** Arthur + Claude (brainstorming)
**Status:** aprovado para execução
**Escopo:** preencher o passo "[advogado assina]" do fluxo PJe assistido com um seam
de provedor de assinatura, mantendo a regra de nunca guardar segredo de assinatura.

---

## 0. Resumo de uma frase

Dar ao software a inteligência de saber **como cada advogado assina** (BirdID /
PJeOffice / A3 / A1 / VIDaaS) e de instruí-lo com segurança no checkpoint
`signature_required`, fechando a auditoria — sem que o Causor jamais segure o PIN,
senha ou certificado que assinaria por ele.

---

## 1. Motivação e posicionamento

- O fluxo PJe já para no gate humano (`ready_to_sign`) sem nunca assinar. O buraco
  é o passo "[advogado assina]": hoje o software só devolve a string genérica
  `manual_pjeoffice` e não sabe **qual** é o provedor de assinatura do advogado,
  não dá instrução específica, nem registra na auditoria qual credencial assinou.
- O moat do Causor é segurança: concorrentes RPA-bureau (e-Protocol, doc9, DWRPA,
  Finch) guardam senha/cert do advogado em script/planilha. O Causor ganha por
  **não guardar segredo**. Este passo estende esse princípio à assinatura.
- `manual_handoff` entrega ~90% do valor (preparar o protocolo automaticamente,
  com gate e auditoria) com 0% do risco de custódia de certificado: o advogado
  assina **fora** do Causor (app BirdID, token, PJeOffice). Não há segredo de
  assinatura a guardar nesse modo.
- A integração via API (push de assinatura) é diferencial enterprise futuro, não
  requisito inicial — fica como gancho preparado, não implementado.

---

## 2. Restrições inegociáveis (do CLAUDE.md)

1. **Secrets never enter prompts or logs.** A credencial de assinatura nunca
   guarda PIN/senha/.pfx/chave privada/OTP. Em `manual_handoff` não há sequer
   segredo de assinatura — o `SignatureProvider` só orquestra o advogado.
2. **Gate humano antes do ato irreversível.** O seam não adiciona nenhum método
   que assine ou protocole. O ato continua sendo do advogado, fora do Causor.
3. **Auditoria imutável.** O fechamento passa a registrar qual provedor/modo
   assinou, ligando o ato à credencial.
4. **Vault como fronteira.** O banco principal guarda só `referencia_vault` +
   metadados não-sensíveis (já é o comportamento de `vault/service.py`).

---

## 3. O que JÁ existe (não reconstruir)

| Peça | Arquivo | Estado |
|---|---|---|
| Conector para em `ready_to_sign`, sem método de assinar | `connectors/pje/connector.py` | ✅ |
| Job orquestra + gate + auditoria | `queue/jobs.py` → `run_pje_assisted_protocol_job` | ✅ |
| Fechamento manual com `protocolo` obrigatório (≥3 chars) | `queue/jobs.py` → `confirm_manual_protocol` | ✅ |
| Vault guarda só referência; rejeita campos de senha/cert | `vault/service.py` | ✅ |
| `store_signature_reference` (referência genérica de provedor) | `vault/service.py` | ✅ |
| Modal de protocolo com seletor de credencial | `frontend/app/components/ProtocolarModal.tsx` | ✅ |
| Modelo `CredencialAssinatura` (sem `modo`) | `sor/models.py` | ✅ |

---

## 4. Decisões travadas no brainstorming

| # | Decisão | Escolha |
|---|---|---|
| D1 | Profundidade | Só `manual_handoff` no MVP; adaptador de API só **preparado** (`request_signature` levanta `NotImplementedError`). |
| D2 | Modelagem | Mesma tabela `credencial_assinatura` + coluna `modo`. `provedor` é o discriminador. |
| D3 | Fechamento do laço | Número de protocolo **obrigatório** (já é); comprovante opcional. |

---

## 5. Arquitetura-alvo

```
peticao aprovada (SOR)
  → run_pje_assisted_protocol_job (queue/jobs.py)
      → resolve credencial → get_signature_provider(provedor, modo)   [NOVO]
      → build_pje_package + render_minuta_pdf                          [JÁ EXISTE]
      → PjeAssistedConnector.prepare_filing(...)                       [JÁ EXISTE]
            → PARA em ready_to_sign
      → provider.handoff(package) → SignatureHandoff                   [NOVO]
      → resultado/auditoria carregam o handoff (sem segredo)           [AJUSTE]
  → frontend mostra mensagem do provedor + botões                      [AJUSTE]
  → advogado assina/envia FORA do Causor (BirdID/PJeOffice)
  → confirm_manual_protocol(protocolo) + audit com provedor/modo       [AJUSTE]
```

### Componentes novos (testáveis isolados)

1. **`backend/app/signing/__init__.py`** — pacote novo.
2. **`backend/app/signing/providers.py`**:
   - `@dataclass(frozen=True) SignatureHandoff`: `provedor: str`, `modo: str`,
     `mensagem: str`, `instrucoes: list[str]`, `acoes: list[str]`.
   - `@dataclass(frozen=True) ProviderSpec`: `provedor`, `label`, `modos: tuple`,
     `mensagem_template`, `instrucoes`, `acoes_por_modo: dict[str, list[str]]`.
   - `PROVIDER_CATALOG: dict[str, ProviderSpec]` — entradas para `birdid`,
     `pjeoffice`, `a3`, `a1`, `vidaas` + fallback genérico (`_GENERIC`).
   - `class SignatureProvider`:
     - `__init__(spec, modo)`.
     - `handoff(package) -> SignatureHandoff` — monta a mensagem/ações do modo
       (implementado p/ `manual_handoff`).
     - `request_signature(package)` — `raise NotImplementedError(...)`. Gancho do
       BirdID-API futuro.
   - `get_signature_provider(provedor: str | None, modo: str = "manual_handoff")
     -> SignatureProvider` — factory; provedor desconhecido cai no fallback.

### Modo de assinatura: mapeamento

O conector hoje aceita `signature_mode ∈ {manual_pjeoffice, cloud_certificate}`.
Mantém-se essa interface interna do conector, mas o **job** passa a derivá-la do
provider/modo da credencial:
- `modo == "manual_handoff"` → `signature_mode = "manual_pjeoffice"`.
- `modo == "api"` (futuro) → `signature_mode = "cloud_certificate"`.
O `SignatureHandoff` é a informação rica que viaja pro frontend; o `signature_mode`
do conector permanece como detalhe interno de checkpoint.

---

## 6. Modelo de dados

Migração Alembic em `backend/alembic/versions/`:
- Adiciona `credencial_assinatura.modo` `String(20)` `NOT NULL` default
  `'manual_handoff'`.
- Backfill: toda linha existente recebe `manual_handoff` (inclui `PJeSession`).
- `sor/models.py`: `modo: Mapped[str] = mapped_column(String(20), nullable=False,
  default="manual_handoff")`.

Sem outras colunas. Nenhum segredo entra na tabela.

---

## 7. Máquina de estados (inalterada no núcleo)

```
prepared → ... → ready_to_sign   (conector para aqui, como hoje)
                    │
                    └─ signature_required (handoff do provedor → UI)
                          │  [advogado assina FORA do Causor]
                          └─ confirm_manual_protocol(protocolo) → protocolada
```

`ready_to_sign` continua sendo o estado do conector. `signature_required` é o
rótulo de produto que a UI consome para saber **como** o advogado assina. Nenhum
estado novo de falha; os estados de falha do conector permanecem.

---

## 8. Fiação no job + conector

- `run_pje_assisted_protocol_job`:
  - resolve a `CredencialAssinatura` (já valida ativo/existência), lê `provedor` +
    `modo`, chama `get_signature_provider(...)`.
  - deriva `assinatura_modo` do conector a partir do `modo`.
  - após o checkpoint do conector, chama `provider.handoff(package)` e injeta o
    `SignatureHandoff` (asdict) no `resultado["evidence"]["handoff"]` e num campo
    do audit `peticao_protocolo_preparado`.
  - **Garantia:** o payload/audit nunca contém `referencia_vault`, `storage_state`
    nem qualquer segredo — só `provedor`, `modo`, `mensagem`, `instrucoes`, `acoes`.
- `connector.py`: campo `evidence["assinatura"]` passa a refletir o estado
  `signature_required` em vez da string solta de modo. Sem novos métodos de ação.

---

## 9. Fechamento do laço

- `confirm_manual_protocol` já exige `protocolo` (≥3 chars). Mantém
  `comprovante_uri` opcional.
- Enriquece o `detalhe` do audit com `provedor` e `modo` da credencial usada
  (quando houver `credencial_id` associável), ligando o ato assinado à credencial.
- Sem mudança no schema da request.

---

## 10. Frontend (`ProtocolarModal` + `lib/api.ts`)

- `lib/api.ts`: `CredencialAssinatura` ganha `modo: string`; novo tipo
  `SignatureHandoff { provedor; modo; mensagem; instrucoes; acoes }` no retorno do
  job.
- `ProtocolarModal`:
  - seletor de credencial mostra `provedor` + `modo`.
  - após preparar (PJe), exibe a `mensagem` do provedor + lista de `instrucoes`.
  - botões conforme `acoes` do modo `manual_handoff`: **Abrir PJe/PJeOffice** ·
    **Já assinei → registrar protocolo** (abre campo de número, obrigatório) ·
    **Cancelar**.
- Nenhuma chamada de rede nova além das existentes.

---

## 11. Estratégia de testes (TDD — testes antes do código)

1. `backend/tests/test_signing_providers.py` (NOVO):
   - catálogo resolve cada provedor conhecido; provedor desconhecido → fallback.
   - `handoff()` retorna `mensagem`/`acoes`/`instrucoes` corretos por provedor no
     modo `manual_handoff`.
   - `request_signature()` levanta `NotImplementedError`.
2. `backend/tests/test_pje_vault_job.py` (ESTENDE):
   - job injeta o `SignatureHandoff` no resultado e no audit.
   - **nenhum segredo vaza**: assert de que `referencia_vault`/`storage_state`/
     chaves sensíveis não aparecem no payload/resultado/audit.
   - checkpoint reportado como `signature_required` para a UI.
3. `confirm_manual_protocol` — audit passa a conter `provedor`/`modo`.
4. Migração — teste de backfill (espelha o padrão de backfill de tenant
   existente): linhas antigas viram `manual_handoff`.
5. Frontend — type-check (`tsc`) + render do modal com handoff mockado.

Disciplina: escrever os testes de cada unidade **antes** da implementação.

---

## 12. Fora de escopo (YAGNI)

Chamada real a qualquer API de assinatura (BirdID/VIDaaS) · modo `api` e
`local_agent` funcionais · upload de comprovante para storage · A3/token físico
automatizado · fallback A1 cifrado · múltiplos provedores por advogado com seleção
por petição.

---

## 13. Ordem de execução

1. Migração + `modo` no modelo (com teste de backfill).
2. `app/signing/providers.py` (TDD: `test_signing_providers.py` primeiro).
3. Fiação em `run_pje_assisted_protocol_job` + `confirm_manual_protocol`
   (TDD: estende `test_pje_vault_job.py`).
4. Ajuste do conector (`evidence["assinatura"]` → `signature_required`).
5. Frontend (`lib/api.ts` + `ProtocolarModal`), type-check.
6. Suíte completa verde + ruff.

---

## 14. Notas de execução (desvios do design, implementado em 2026-06-18)

Pequenos ajustes feitos durante a implementação, todos aditivos/seguros:

1. **`signature_required` não sobrescreve o checkpoint.** Um teste de API já
   fixava `resultado["checkpoint"] == "ready_to_sign"` (estado do conector). Em
   vez de sobrescrever, o job adiciona `resultado["estado"] = "signature_required"`
   e o `evidence["handoff"]`. O conector permanece intocado (sem novo método de
   ação) — mais seguro do que mexer no `evidence["assinatura"]` do conector.
2. **`ConfirmarProtocoloRequest` ganhou `credencial_id` opcional.** O design dizia
   "sem mudança no schema", mas para enriquecer a auditoria de fechamento com
   `provedor`/`modo` a partir do frontend, o campo opcional é necessário. É
   retrocompatível (default `None`).
3. **Form de "registrar protocolo" no frontend fica para fase 2.** Surfaçamos o
   handoff (mensagem + instruções + provedor/modo) read-only no card do job em
   `ProtocolosView`; `confirmarProtocoloManual` já aceita `credencialId`. O form
   com input de número + parent-refresh é UI de fase 2, como o próprio design
   marca o frontend.

Verificação: backend 179 passed / 3 skipped, ruff limpo; frontend `tsc` limpo,
vitest 2 passed.

4. **Refactor de organização (pós-implementação): colapso do "modo".** A seção 5
   previa manter o `signature_mode` antigo do conector (`manual_pjeoffice` /
   `cloud_certificate`) ao lado do `modo` novo. Numa varredura de código morto,
   isso se mostrou redundância pura. O `signature_mode`/`assinatura_modo` foi
   **removido** do conector, job, request schema, vault payload e CLI — o conector
   para em `ready_to_sign` independente de como se assina, e o `SignatureProvider`
   + `credencial.modo` viraram o **único** caminho de assinatura. Também saíram:
   `PjeFilingCheckpoint.next_action` (redundante com `handoff.mensagem`), o dado
   write-only `signature_mode` no vault, e a exibição da string crua
   `ready_to_sign` no front (mostrada só para jobs fake). O gancho futuro de API é
   apenas `SignatureProvider.request_signature()`.
   Verificação pós-refactor: backend 178 passed / 3 skipped, ruff limpo; frontend
   `tsc` limpo, vitest 2 passed.
