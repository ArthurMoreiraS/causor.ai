# Protocolo multi-tribunal: cofre de credenciais + roteamento + captura pela UI

**Data:** 2026-07-07
**Status:** Design aprovado (Abordagem A), pendente revisão da spec
**Origem:** "Melhorar o fluxo de captura de vault e protocolo PJe" — reunião de
demo (investidor) em 3 dias. Diretriz do Arthur: construir na **forma do MVP
definitivo**, mesmo que dê mais trabalho; a execução ao vivo precisa ser à prova
de falhas.

---

## 1. Problema

Hoje o fluxo de conexão de tribunal e protocolo é **PJe-only, com URL digitada à
mão e sessão escolhida manualmente**. Três defeitos concretos:

1. **URL errada / roteamento ausente.** O modal "Conectar PJe"
   ([VaultSection.tsx](../../../frontend/app/components/VaultSection.tsx)) tem
   default `https://pje.tjsp.jus.br/pje` — mas **TJSP usa e-SAJ**, não PJe. Não
   existe registro de qual sistema/URL cada tribunal usa para peticionar. O
   [court_systems.py](../../../backend/app/capture/court_systems.py) já deduz o
   *rótulo* do sistema (PJe/e-SAJ/EPROC/Projudi), mas não carrega URL nenhuma.
2. **Vault não é multi-tribunal de verdade.** `CredencialAssinatura`
   ([models.py](../../../backend/app/sor/models.py)) guarda N linhas por
   advogado, mas toda sessão é rotulada `provedor="PJeSession"`, e o payload só
   tem `{tribunal, url_base, storage_state}` — **sem `sistema`, sem `grau`**. O
   advogado com casos no TJSP (e-SAJ) + TRT (PJe) + TRF (eproc) não tem como o
   sistema distinguir e rotear as sessões.
3. **Captura é CLI-only e a escolha é manual.** A captura de sessão roda por
   `python -m app.cli pje-capture-session` (o modal só exibe o comando pra
   copiar). No protocolo, o advogado escolhe a credencial num dropdown
   ([ProtocolarModal.tsx](../../../frontend/app/components/ProtocolarModal.tsx));
   o job [run_pje_protocol_job](../../../backend/app/queue/jobs.py) dá hard-stop
   se `processo.sistema != "pje"` e crava `"sistema": "PJe"` em tudo.

**Consequência:** cada minuta pode precisar de um sistema diferente, e o software
não suporta isso. Para uma demo robusta (o advogado da reunião pode ser de
qualquer tribunal) e para o MVP real, precisamos generalizar.

## 2. Princípios de inspiração (Garfield AI, Enter, Handle.ai)

Produtos que "entram no tribunal e fazem tudo" convergem em padrões que **já são**
a arquitetura pretendida do Causor (AGENTS.md) — o desenho abaixo os reforça:

- **Expert-system determinístico + LLM só na borda.** Garfield usa LLM
  "primarily for information extraction, not legal reasoning". Navegação e
  protocolo são regras determinísticas; Claude só extrai/classifica/redige.
- **Gate humano é feature, não bug.** Garfield é explicitamente "not autonomous;
  users must approve each step" — e é por isso que é regulável e confiável. O
  gate humano antes do ato irreversível (constraint não-negociável do AGENTS.md)
  é mantido e vira parte da narrativa: *"o Causor faz tudo sozinho até o gate; o
  advogado aprova e ele protocola e traz o comprovante."*
- **Entrar no portal e mostrar o serviço.** Sem API pública de protocolo no
  Brasil, a ação é Playwright/computer-use — mas com **evidência de cada passo**
  (screenshots que o conector já captura), que é o que torna a autonomia crível.
- **Cofre de credencial fecha o loop (whom / doc9).** O whom (referência do
  Arthur) é, na prática, um **cofre de certificados digitais** em nuvem com
  compartilhamento controlado (por cargo/URL/horário) e **auditoria de cada
  uso**. A lição: guardar só o cookie de sessão coloca o Causor *dentro* do
  portal, mas a **assinatura** ainda exige o certificado (PJeOffice/Web Signer).
  Para "protocolar sozinho de verdade", o cofre precisa de uma **referência de
  certificado em nuvem** (push-signing) — decisão tomada: **integrar** cloud-cert
  (BirdID/VIDaaS/Certisign Cloud/SafeID), não recriar o whom. O Causor foca no
  moat (ação autônoma) e herda do whom os padrões de **controle de acesso** e
  **auditoria por assinatura**.

## 3. Arquitetura alvo (MVP definitivo)

As peças 3.1–3.5 (incluindo 3.4b) são **arquitetura real** — valem no piloto e na
demo. A 3.6 (sandbox) é o que muda entre demo e piloto real. A 3.7 é a narrativa
na UI.

### 3.1. Registro de roteamento de tribunais (`court_routing`)

Estende `court_systems.py` de "rótulo do sistema" para um registro completo,
versionado em código, best-effort e sobreponível:

```
CourtRoute(
    tribunal: str,          # "TJSP", "TRT2", "TRF3", ...
    grau: str,              # "1" | "2"  (1º/2º grau)
    sistema: str,           # "PJe" | "e-SAJ" | "EPROC" | "Projudi"
    url_login: str,         # onde o advogado autentica
    url_peticionamento: str,# onde se protocola (e-SAJ inclui ?servico=...)
    verificado: bool,       # URL conferida contra o site do tribunal
    observacao: str | None,
)
```

- **`sistema_para_tribunal()` continua existindo** (retrocompat) e passa a ser
  derivado do registro. DataJud, quando traz o campo, continua autoritativo e
  sobrepõe o palpite.
- **Cobertura ampla** (diretriz "MVP definitivo"): e-SAJ (SP, MS, CE, AL, AC),
  PJe (MG, BA, DFT, PE, RN, MA, ES, RO, SE, PB, PI, AM, PA, …), Trabalho (TRTs
  via PJe), Federal (TRFs), EPROC (TRF4, TJRS, TJSC, TJTO), Projudi (TJPR, TJGO).
  Cada entrada com `verificado` — **toda URL confirmada contra o site oficial do
  tribunal na implementação** (não confiar em memória). Fallback explícito para
  tribunal desconhecido: sistema deduzido, URL nula, UI pede confirmação manual.
- **Exemplo verificado (TJSP / e-SAJ):**
  `url_login = https://esaj.tjsp.jus.br/esaj/portal.do?servico=740000`,
  `url_peticionamento (1º grau) = https://esaj.tjsp.jus.br/esaj?servico=820100`,
  `2º grau = ...?servico=820200`.

### 3.2. Cofre de credenciais multi-tribunal (sessão + cloud-cert)

O vault deixa de ser um "chaveiro de cookies" e vira um **cofre de credenciais
com tipos plugáveis**, um por advogado, N por `(sistema, tribunal, grau)`:

- **`SessionCredential`** — o `storage_state` (cookie) autenticado do portal.
  Caminho de **navegação**: coloca o Causor *dentro* do tribunal. Funciona hoje.
- **`CloudCertCredential`** — **referência** (não o certificado bruto) a um
  provedor de certificado em nuvem (BirdID/VIDaaS/Certisign Cloud/SafeID).
  Caminho de **assinatura** via push-signing pela API do provedor. É o que
  **fecha o loop autônomo** (protocola sem handoff manual ao PJeOffice).
- **`A1Credential`** (fallback, fora do escopo agora) — A1 cifrado; só se o
  piloto exigir e sem cloud-cert.

Detalhes:

- **Migração** em `CredencialAssinatura`: adiciona `sistema` (str, null),
  `grau` (str, null) e `tipo` (`session` | `cloud_cert` | ...). `provedor` deixa
  de ser cravado "PJeSession"; sessões usam `provedor="CourtSession"`,
  `tipo="session"`. Cloud-certs usam `provedor` do fornecedor, `tipo="cloud_cert"`.
- **Serviços genéricos** `store_court_session(...)` (sessão) e
  `store_cloud_cert_reference(...)` (referência de cloud-cert). O
  `store_pje_session_reference` vira wrapper fino (retrocompat).
  `load_court_session_payload` substitui `load_pje_session_payload` (mantém alias).
- **Controle de acesso e auditoria (herdados do whom):** cada credencial carrega
  metadados de acesso (advogado dono, escritório) e **toda** navegação/assinatura
  gera `audit_log` imutável (quem, o quê, sistema, quando). Janela/cargo de acesso
  granular fica preparado no modelo, ativado incrementalmente.
- **Push-signing** via provider (ver 3.4b): o Causor **nunca** detém PIN,
  certificado bruto, senha ou OTP — só dispara a assinatura pela API do provedor
  em nuvem, que confirma no dispositivo do advogado.
- **Persistência na demo:** o provider `localdev` hoje guarda segredo em dict de
  memória (perde ao reiniciar o backend — risco de perder a sessão no meio da
  demo). Passa a ser **file-backed** (arquivo cifrado local, fora do git).
  Provider `supabase` (vault.create_secret) permanece para produção.
- **Segurança (AGENTS.md #1):** o cofre guarda apenas `storage_state` (cookie) e
  **referências** não-secretas a cloud-certs. Nunca senha, certificado bruto, PIN
  ou OTP; nada entra em prompt ou log.

### 3.3. Captura de sessão pela UI (adeus CLI)

- **Endpoint local** `POST /usuarios/{id}/sessoes-tribunal/capturar` que, quando
  o backend roda no notebook do advogado, dispara `capture_pje_storage_state`
  (headed) apontando para a **`url_login` do registro** para o `(tribunal, grau)`
  escolhido. O advogado loga uma vez; a sessão é capturada e salva via
  `store_court_session`.
- **Modal "Conectar tribunal"** substitui o texto de comando de terminal por:
  seletor de tribunal + grau (com o sistema e a URL resolvidos e exibidos:
  *"TJSP · e-SAJ · 1º grau"*), botão "Conectar" real, e estados
  (abrindo janela → aguardando login → conectado). O comando CLI vira fallback
  documentado, não o caminho principal.
- **Guard de produção mantido:** `validate_training_base_url` continua exigindo
  `CAUSOR_PJE_ALLOW_PROD=1` para URLs de produção. Na demo, o registro pode
  apontar para o **sandbox** (ver 3.6); um toggle permite apontar para
  homologação real num ensaio.

### 3.4. Interface de driver + dispatch por sistema

O protocolo deixa de ser PJe-hardcoded. Uma interface única, um driver por
sistema:

```
class FilingDriver(Protocol):
    sistema: str
    def prepare_filing(self, package, *, submit: bool) -> FilingCheckpoint: ...
```

- **`PjeDriver`** = o `PjeAssistedConnector` atual (real, já existe), adaptado à
  interface.
- **`SandboxDriver`** = driver system-aware para a demo (ver 3.6).
- **`EsajDriver`, `EprocDriver`, `ProjudiDriver`** = stubs atrás da interface,
  que hoje levantam `UnsupportedFilingSystemError` claro (ou caem no
  `SandboxDriver` na demo) e são preenchidos incrementalmente com conectores
  reais depois. Trocar o driver **não** mexe em job, vault, UI ou roteamento.
- `run_pje_protocol_job` é generalizado para `run_protocol_job`: remove o
  hard-stop de linha 402, resolve o sistema da minuta, e faz **dispatch** para o
  driver correspondente. Os campos `"sistema": "PJe"` cravados passam a refletir
  o sistema real.

### 3.4b. Assinatura em nuvem (push-signing) — fecha o loop autônomo

Interface única para assinar, separada do driver de navegação:

```
class CloudSignProvider(Protocol):
    provedor: str
    def sign(self, pdf_bytes: bytes, *, cloud_cert_ref: str) -> SignedDoc: ...
```

- **`ManualHandoffProvider`** (atual) — não assina; devolve `ready_to_sign` para
  o advogado assinar no PJeOffice/Web Signer. É o comportamento de hoje e
  continua sendo o **fallback** quando não há `CloudCertCredential`.
- **`CloudCertProvider`** (definitivo, stub agora) — dispara push-signing pela
  API do provedor (BirdID/VIDaaS/...); o advogado confirma no celular; o Causor
  recebe o PDF assinado e o driver conclui o protocolo **sem handoff manual**.
- **`SandboxSignProvider`** (demo) — cumpre o passo de assinatura
  deterministicamente, para a demo mostrar o protocolo autônomo ponta a ponta.

Fluxo do driver ao protocolar: navega até anexar a minuta → **se** há
`CloudCertCredential` na sessão resolvida, chama `CloudSignProvider.sign` (push) e
segue para protocolar → **senão**, para em `ready_to_sign` (handoff). O gate
humano de aprovação ocorre **antes** de qualquer assinatura (irreversível).

### 3.5. Roteamento automático da minuta → sessão → driver

O que responde "cada minuta em um sistema diferente":

1. Ao protocolar a minuta, resolve `processo → (tribunal, grau) → sistema` via
   registro (3.1).
2. Procura no vault a sessão **ativa** que casa `(sistema, tribunal, grau)`.
3. Se existe, roteia para o driver do sistema com aquela sessão. Se não existe, a
   UI pede: *"Conecte o TJXX (e-SAJ · 1º grau) primeiro"* — sem dropdown manual.
4. O `ProtocolarModal` deixa de exigir escolha de credencial; mostra a sessão
   resolvida (ou o pedido de conexão) e o sistema/URL de destino.

### 3.6. Sandbox system-aware (execução à prova de falhas na demo)

- Um **sandbox local** (evolução do `simulator.py`) que renderiza a tela de
  peticionamento **rotulada com o sistema resolvido** (cabeçalho e URL refletem
  e-SAJ · esaj.tjsp.jus.br / PJe · pje.trtXX.jus.br / eproc, conforme o
  tribunal). Deixado **explicitamente identificado como ambiente Causor de
  homologação** (não se passa por protocolo real).
- O `SandboxDriver` dirige esse sandbox de forma **determinística**: localizar
  processo → anexar PDF → assinar → **retorna número de protocolo + comprovante**,
  capturando screenshots de cada passo. Sempre sucede.
- Na demo, o registro/roteamento manda todos os sistemas para o `SandboxDriver`
  (via flag `CAUSOR_FILING_MODE=sandbox`). No piloto real, a flag sai e cada
  sistema usa seu driver real (PJe primeiro).

### 3.7. Evidência + gate na UI (a narrativa "faz tudo sozinho")

- A [ProtocolosView](../../../frontend/app/views/ProtocolosView.tsx) passa a
  mostrar, por protocolo: os **passos do agente** (localizou → anexou → assinou →
  protocolou), os **screenshots** de evidência, o **número do protocolo** e o
  **comprovante**. É o "mostrar o serviço" do Garfield/Enter.
- O **gate humano** antes do ato irreversível é mantido e visível: o Causor
  prepara tudo até `ready_to_sign`, o advogado aprova, e só então o driver
  protocola. Auditoria imutável de cada passo permanece.

## 4. Modelo de dados (migração Alembic)

- `credencial_assinatura`: `+ sistema VARCHAR(20) NULL`, `+ grau VARCHAR(4) NULL`,
  `+ tipo VARCHAR(20) NOT NULL DEFAULT 'session'` (`session` | `cloud_cert`).
- Backfill: linhas existentes `provedor="PJeSession"` → `provedor="CourtSession"`,
  `tipo="session"`, `sistema="PJe"`, `grau` do payload se disponível (senão null).
- Sem tabela nova: registro de rotas é dado em código versionado; auditoria usa o
  `audit_log` existente.

## 5. Contratos de API

- **Novo** `POST /usuarios/{id}/sessoes-tribunal/capturar` — dispara captura
  headed local; body `{tribunal, grau}`; resolve URL do registro; retorna a
  credencial criada.
- **Novo** `GET /court-routing?tribunal=&grau=` — resolve sistema + URLs (para o
  modal exibir o destino).
- **Alterado** `POST /usuarios/{id}/pje-sessoes` → `.../sessoes-tribunal`
  (mantém alias antigo) aceitando `sistema` e `grau`.
- **Novo** `POST /usuarios/{id}/cloud-cert` — registra referência de certificado
  em nuvem (provedor + external_ref); nunca recebe o certificado bruto/PIN.
- **Alterado** protocolo: resolve sessão automaticamente; `credencial_id` no body
  vira opcional (só override manual). Usa `CloudCertCredential` para push-signing
  quando disponível; senão, `ready_to_sign`.

## 6. Fluxo ponta a ponta (roteiro da demo)

1. **Captura intimação** — real, DJEN/Comunica (já funciona).
2. **Prazo** — engine determinístico real (já funciona).
3. **Minuta** — Claude real (já funciona).
4. **Conectar tribunal** — modal na UI; janela abre no notebook; login único;
   sessão salva no vault-chaveiro com sistema/tribunal/grau.
5. **Aprovar (gate)** — advogado revisa e aprova a minuta.
6. **Protocolar** — Causor resolve o sistema da minuta, acha a sessão certa,
   dirige o portal (sandbox na demo), mostra os passos + screenshots + **número
   de protocolo + comprovante**.

## 7. Constraints e segurança (AGENTS.md)

- Segredos nunca em prompt/log; o cofre guarda só cookie de sessão, referências
  não-secretas a cloud-certs e metadados.
- Gate humano antes de todo ato irreversível — mantido e visível.
- Auditoria imutável de cada passo — mantida.
- Sandbox **honestamente rotulado** como ambiente Causor de homologação; não se
  apresenta como protocolo real. Guard de produção (`CAUSOR_PJE_ALLOW_PROD`)
  mantido.

## 8. Faseamento (definitivo vs. incremental)

- **Agora (arquitetura definitiva):** registro de rotas; cofre de credenciais
  (session + cloud-cert) + migração; captura pela UI; interfaces `FilingDriver` e
  `CloudSignProvider` + dispatch; roteamento automático; evidência + auditoria na
  UI; gate. Implementações vivas: `PjeDriver` real, `SandboxDriver`,
  `ManualHandoffProvider` real, `SandboxSignProvider`.
- **Incremental (pós-demo):** conectores reais e-SAJ/EPROC/Projudi preenchendo os
  stubs; `CloudCertProvider` real (BirdID/VIDaaS) para assinatura autônoma; mais
  tribunais verificados no registro; controle de acesso granular por cargo/janela.

## 9. Testes (TDD)

- **Registro:** resolução `(tribunal, grau) → sistema/URL`; TJSP→e-SAJ (não PJe);
  fallback de desconhecido; DataJud sobrepõe.
- **Vault-chaveiro:** N sessões por advogado; `load_court_session_payload` acha a
  sessão certa por `(sistema, tribunal, grau)`; persistência sobrevive a restart
  (localdev file-backed); segredo nunca logado.
- **Roteador:** minuta em tribunal X escolhe a sessão certa; sem sessão → erro
  claro de "conecte primeiro".
- **Dispatch:** sistema PJe → PjeDriver; sandbox mode → SandboxDriver; sistema
  sem driver real fora de sandbox → `UnsupportedFilingSystemError`.
- **SandboxDriver:** retorna protocolo + comprovante + screenshots
  deterministicamente.
- **Assinatura:** sessão com `CloudCertCredential` → `CloudSignProvider.sign`
  chamado e protocolo concluído; sem cloud-cert → para em `ready_to_sign`;
  provider nunca recebe PIN/cert bruto; assinatura gera `audit_log`.

## 10. Riscos

- **URLs do registro desatualizam** (sistemas migram; TJSP→eproc em curso). Mitiga
  com `verificado`, fallback manual, e DataJud autoritativo.
- **Captura headed depende de rodar no notebook** (backend não abre janela em
  deploy). Aceito: a demo roda em localhost (decisão do Arthur). Deploy usa
  fallback (sessão pré-conectada / captura documentada).
- **Sandbox confundido com real.** Mitiga com rótulo explícito e flag separada.

## 11. Fora de escopo (YAGNI agora)

- Conectores reais e-SAJ/EPROC/Projudi (stubs atrás da interface; sandbox na demo).
- Integração real com provedor de cloud-cert (interface + stub agora; handoff
  manual/PJeOffice permanece como fallback vivo).
- Guarda de certificado bruto/A1 dentro do Causor (decisão: **integrar**
  cloud-cert, não recriar o whom).
- Controle de acesso granular por cargo/janela (modelo preparado, não ativado).
- Billing, multi-tenant além do que já existe, novos tribunais além do registro.
