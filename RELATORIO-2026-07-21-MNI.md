# Relatório da sessão de 21/07/2026 — MNI: a porta oficial dos tribunais

Este documento explica, em linguagem direta, tudo o que foi feito nesta sessão
e por que cada peça importa para o Causor. Leia de cima para baixo: a ordem é
a ordem em que as coisas aconteceram e cada parte depende da anterior.

---

## 1. De onde partimos

No início da sessão, o Causor estava assim:

- **Planos 1 e 2 completos**: agente local funcionando (o programa no
  computador do advogado que abre o navegador do tribunal), e o pipeline de
  "autos íntegros" pronto — captura com prova de completude, OCR, trechos
  citáveis e o gate que bloqueia a minuta se faltar qualquer documento.
- **Plano 3 pela metade**: toda a infraestrutura de conectores construída
  contra simuladores, mas os conectores **reais** (PJe, eproc, e-SAJ,
  Projudi) travados há semanas esperando o advisor liberar acessos de
  tribunal.
- Resultado prático: **9 dias sem commit**. O projeto não estava parado por
  falta de código — estava parado por falta de acesso.

## 2. A pesquisa: como os grandes resolvem o problema dos autos

A pergunta que destravou tudo: *"como a Enter (o unicórnio jurídico
brasileiro) resolve o contexto íntegro dos autos para gerar peças?"*

O que descobrimos:

- **A Enter não constrói captura de dados.** Ela compra da **Judit**, que
  mantém um exército de robôs de navegador (um framework parametrizado por
  tribunal, com proxies e resolução de CAPTCHA em escala) cobrindo 90+
  tribunais. A Enter foca só na "inteligência aplicada" — o agente que lê,
  cruza e redige.
- **A Judit é cara** porque o modelo dela é monitoramento contínuo em escala
  enterprise. Para um piloto com poucos processos, é a ferramenta errada.
- **Ponto crucial**: a Judit entrega conveniência (formato único para todos
  os tribunais), mas **não garante completude** do conjunto de documentos —
  a documentação deles não promete "você recebeu o processo inteiro". O
  Plano 2 do Causor (enumeração dupla, hash SHA-256, gate fail-closed) é uma
  barra **mais alta** do que a do mercado, exatamente no ponto que importa
  para escritório pequeno, onde perder peça = perder prazo = malpractice.

**Conclusão estratégica**: o Causor não precisa replicar a Judit. Precisa da
fatia dela que cobre 1–2 tribunais do piloto — e já tem a camada de
integridade que a Judit nem vende.

## 3. A descoberta: MNI, a porta que ninguém cobra

Investigando alternativas gratuitas, chegamos ao **MNI (Modelo Nacional de
Interoperabilidade)** — um webservice que o CNJ **obriga** os sistemas
processuais a expor (Provimento 355/2018). É uma porta oficial,
computador-a-computador, com duas operações que interessam:

| Operação | O que faz | Equivale a |
|---|---|---|
| `consultarProcesso` | Lista e entrega **todos os documentos** de um processo | A leitura dos autos que hoje depende do agente local |
| `entregarManifestacaoProcessual` | **Protocola** petição no processo | O protocolo que nenhum vendor de dados vende |

**Custo: R$ 0.** O acesso vem por **credenciamento**: um ofício à Diretoria
de TI do tribunal. Burocracia, não dinheiro.

**A ressalva honesta**: relatos de campo mostram que a qualidade do MNI varia
por tribunal — a consulta de metadados costuma funcionar, mas a entrega do
teor dos documentos é onde alguns tribunais falham. Por isso tudo o que
construímos é **fail-closed**: se o MNI do tribunal não funcionar, o sistema
cai automaticamente no agente local, sem quebrar nada.

## 4. A mudança de política

A pedido do usuário, a antiga regra não-negociável #1 ("credenciais vivem
só no vault/máquina do advogado") foi **removida** de todos os documentos
(`AGENTS.md`, PRD, planos, IA.md). A regra nova: **entregar o que funciona
vale mais que pureza de custódia** — delegar credencial a um terceiro de
confiança (Escavador, Judit, provedor de assinatura em nuvem) é permitido
quando for o caminho mais rápido. O que permanece intocável é a regra de
vazamento: **segredo nunca entra em prompt de IA nem em log**, esteja onde
estiver.

Foi essa mudança que permitiu o desenho do MNI rodando no servidor (a senha
do credenciamento fica no vault do backend, não na máquina do advogado).

## 5. O que foi construído: leitura oficial dos autos via MNI

Do design ao merge na `main`, com spec
(`docs/superpowers/specs/2026-07-21-mni-leitura-autos-design.md`), plano de
implementação (`docs/superpowers/plans/2026-07-21-mni-leitura-autos.md`) e
9 tasks executadas com TDD:

### As peças (backend)

- **`app/connectors/mni/client.py`** — o cliente SOAP. Fala o protocolo do
  MNI "na unha" (httpx + lxml), sem depender de WSDL de tribunal (que vive
  quebrado). Tolerante a variações de formato entre tribunais. A senha nunca
  aparece em log, erro ou repr.
- **`app/connectors/mni/profiles.py`** — o mapa de endereços: qual URL de
  MNI atende cada (tribunal, grau). Fail-closed: tribunal sem perfil
  registrado = MNI indisponível = cai no agente.
- **`app/connectors/mni/reader.py`** — o driver de leitura. Implementa o
  **mesmo contrato** (`CourtReaderDriver`) que o agente local usa — por isso
  o resto do sistema nem percebe a diferença de fonte.
- **`app/connectors/mni/credentials.py`** + tabela `mni_credencial` — a
  credencial do credenciamento, uma por (escritório, tribunal). A senha vai
  para o vault (localdev/Supabase); o banco guarda só a referência.
- **`app/connectors/mni/executor.py`** — o executor que roda a captura
  **dentro do servidor**, passando pelo MESMO pipeline de integridade do
  Plano 2: enumera duas vezes, recomputa hash de cada arquivo, valida PDF
  por magic bytes, e só marca `complete` com prova. Nenhuma exigência foi
  relaxada.
- **Roteamento automático** em `autos/service.py`: ao capturar autos, se há
  credencial MNI ativa + perfil para a rota → `fonte="mni"` (job no
  servidor); senão → `fonte="agente"` (comando ao agente local, caminho
  intocado). Ninguém escolhe nada; o sistema decide.
- **API `/mni/credenciais`** — cadastrar (senha direto pro vault), listar
  (mascarada: `123***`), testar conexão e revogar. Isolada por escritório.
- **Simulador SOAP** (`connectors/simulators/mni.py`) — um tribunal MNI
  falso e sanitizado para testes; o teste de integração roda o fluxo
  completo: HTTP real → executor → captura `complete` 3/3.
- **Teste live opt-in** (`tests/live/test_mni_live.py`) — pronto para o dia
  em que o credenciamento sair: `RUN_MNI_LIVE=1` valida o tribunal real.

### As peças (frontend)

- **Configurações → Acesso aos tribunais → "Consulta oficial (MNI)"**: lista
  de credenciais com status e última validação, botões Testar/Revogar, form
  de cadastro.
- **Selo de origem no painel de contexto do processo**: cada captura mostra
  "via MNI (oficial)" ou "via agente local".

### Por que isso importa

| Dor de antes | Depois |
|---|---|
| Captura só com o PC do advogado ligado | Servidor captura sozinho, agendável por cron |
| Robô quebra quando o site do tribunal muda | Porta oficial padronizada pelo CNJ |
| Pagar Judit/Escavador | R$ 0 — só o ofício de credenciamento |
| Tudo travado no acesso do advisor | Destrava por burocracia própria, sem depender de ninguém |
| Risco de peça com processo incompleto | Continua impossível: mesmo gate fail-closed nas duas fontes |

## 6. A vistoria do sistema

Com o MNI entregue, fizemos uma inspeção do produto inteiro, com três
consertos reais no fluxo de protocolo:

1. **Porta falsa fechada**: existia um caminho no código que prometia
   "protocolo real do PJe direto no servidor", mas dependia de um cookie de
   sessão cuja fonte foi deletada semanas atrás (remoção do cofre de
   sessão). Parecia vivo, mas quebraria de forma confusa se acionado. Agora
   falha fechado com mensagem clara: **protocolo real roda só no agente
   local** (ou, no futuro, via MNI).
2. **Etiqueta errada**: protocolo que parava em "pronto para assinar"
   reportava sempre "PJe", mesmo em rota e-SAJ/eproc. Corrigido.
3. **Resquício removido**: código que fingia ler o "grau" de um campo que
   nunca existiu no modelo `Processo`.

**Verificação de sistema completa:**

- Backend: **450 testes passando** (eram 424 no início da sessão), lint limpo.
- Frontend: **45 testes**, typecheck e build verdes.
- **Verificação visual no app real**: subimos o app com a rede 100%
  interceptada (sem tocar Supabase/API reais) e navegamos nele — dashboard,
  Processos, painel de Autos com os selos "via MNI (oficial)" / "via agente
  local", e a seção MNI nas Configurações, tudo renderizando corretamente.

## 7. O achado mais valioso: o protocolo pode passar pela mesma porta

O fluxo de protocolo hoje está bem desenhado (Gate OAB → job → agente →
"pronto para assinar" → advogado assina → confirma), mas o robô que navega
no tribunal de verdade ainda não existe (Tasks 6–9, travadas no mesmo
acesso).

O MNI muda esse jogo em dois níveis:

**Nível 1 — reuso total da fundação.** A operação de protocolo
(`entregarManifestacaoProcessual`) usa a MESMA credencial, o MESMO endpoint,
a MESMA infraestrutura (vault, perfis, executor, erros canônicos) que
acabamos de construir para leitura. Um `MniFilingDriver` é ~1 semana de
trabalho sobre o que já existe. E a resposta da operação **devolve o
comprovante com número de protocolo** — satisfazendo a regra de que sem
comprovante verificado nunca se marca "protocolada".

**Nível 2 — o gargalo da assinatura pode desaparecer.** O `AGENTS.md` sempre
tratou a assinatura (PJeOffice, certificado, token físico) como "o gargalo
de viabilidade" do produto. Mas a **Lei 11.419/2006 (art. 1º, §2º, III)**
reconhece como assinatura eletrônica válida o **cadastro de usuário no
Poder Judiciário** — exatamente o que o credenciamento MNI fornece. É assim
que grandes litigantes protocolam por sistema hoje, sem clicar em nada. Se
isso se confirmar no tribunal do piloto (varia por regulamento local —
confirmar durante o credenciamento), o protocolo automatizado deixa de
depender de PJeOffice/certificado por completo.

A escada do protocolo fica assim (da melhor opção ao fallback, sempre com o
Gate OAB na frente):

1. **MNI `entregar`** — servidor, oficial, gratuito, comprovante na resposta
   *(a construir; fundação pronta)*.
2. **Agente local até "pronto para assinar"** — construído, aguardando
   drivers reais (Tasks 6–9).
3. **Confirmação manual** — funciona hoje.

## 8. O próximo passo (e por que ele é o mais importante do projeto)

**Enviar o ofício de credenciamento MNI ao tribunal do piloto.** Um único
processo administrativo, gratuito, que destrava simultaneamente:

1. A **leitura oficial dos autos** (código pronto, esperando: basta cadastrar
   a credencial na tela nova e rodar `RUN_MNI_LIVE=1`).
2. O **protocolo via MNI** (fundação pronta; driver é ~1 semana).
3. Possivelmente a **eliminação do gargalo da assinatura** (a confirmar com
   o tribunal).

Enquanto o ofício tramita, nada fica parado: o caminho do agente local
continua funcionando como está, e o roadmap de conectores (Tasks 6–9) segue
válido como fallback para tribunais onde o MNI não entregar.

---

## Apêndice: commits desta sessão (todos na `main`, publicados)

| Commit | O quê |
|---|---|
| `1d4d5eb` | Política: remove exigência de custódia exclusiva de credenciais |
| `af768d8` | Spec do design da leitura MNI |
| `da88b5b` | Plano de implementação |
| `158e1e2` | Cliente SOAP com erros canônicos e segredo à prova de vazamento |
| `c15bc4d` | Perfis de endpoint fail-closed por tribunal/grau |
| `acaba15` | Driver de leitura sobre o contrato existente |
| `27ecdb1` | Modelo de credencial + coluna de fonte da captura |
| `5c1b782` | Credenciais no vault + API mascarada + endpoint de teste |
| `9a21e42` | Roteamento pro executor in-backend com pipeline de integridade |
| `618441b` | Simulador SOAP sanitizado + teste ponta a ponta |
| `c01c5fe` | UI de credenciais MNI nas Configurações |
| `76df384` | Teste live opt-in + docs de estado |
| (badge) | Selo "via MNI / via agente" no painel de contexto |
| (vistoria) | Fecha caminho morto de navegador no backend + consertos no protocolo |
