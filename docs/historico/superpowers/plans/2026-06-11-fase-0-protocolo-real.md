# Fase 0 - Protocolo real com gate humano

**Objetivo:** fechar o MVP vertical do Causor em um tribunal: captura DJEN/DataJud -> prazo deterministico -> minuta Claude/template -> aprovacao humana -> protocolo real assistido -> auditoria.

**Estado de partida:** backend, prazo engine, captura, API, agente de chat, auditoria e frontend operacional ja existem. Ainda faltam conector de protocolo, cofre/assinatura, fila assincrona e templates persistentes do escritorio.

**Marco de sucesso:** ao menos 1 peticao protocolada em ambiente real ou homologacao de tribunal, com aprovacao humana explicita, evento de auditoria e comprovante registrado no SOR.

---

## 1. Decisoes que precisam vir antes do codigo pesado

1. **Tribunal/sistema inicial**
   - Preferencia tecnica: PJe, por padronizacao nacional.
   - Alternativa comercial: e-SAJ/TJSP, se o primeiro piloto estiver em SP e tiver volume.
   - Criterio: escolher pelo piloto disponivel, nao pela arquitetura ideal.

2. **Tipo de assinatura**
   - Preferencia: certificado em nuvem com API/push.
   - Fallback: A1 cifrado no vault.
   - Fora de escopo: A3/token fisico.

3. **Modo do primeiro piloto**
   - Recomendado: Wizard-of-Oz controlado.
   - O sistema prepara pacote, abre portal, preenche dados e para antes do ato irreversivel.
   - O advogado confirma o protocolo no gate.

4. **Escopo do primeiro protocolo**
   - Uma classe de peticao simples, repetitiva e de baixo risco.
   - Um fluxo feliz primeiro: processo localizado, peticao pronta, anexos conhecidos, sem captcha bloqueante.

---

## 2. Arquitetura-alvo da proxima fase

```text
backend/app/
  filing/
    service.py              # orquestra protocolo: valida gate, cria job, grava auditoria
    schemas.py              # FilingRequest, FilingResult, FilingStatus
    package.py              # monta pacote: peticao + anexos + metadados
  connectors/
    pje/
      connector.py          # interface publica do conector PJe
      session.py            # browser context isolado por usuario/escritorio
      flows.py              # login, localizar processo, anexar, assinar, protocolar
      errors.py             # erros recuperaveis vs bloqueantes
  vault/
    service.py              # interface para referencias seguras, sem segredos em prompt/log
    providers.py            # LocalDevVault, CloudCertificateProvider stub
  queue/
    worker.py               # worker RQ/Celery
    jobs.py                 # tarefas longas: captura, protocolo, alertas futuros
```

```text
frontend/app/
  ProtocolPanel.tsx         # acompanhamento do protocolo e comprovante
  CredentialModal.tsx       # onboarding de referencia de certificado
  TemplateManager.tsx       # modelos do escritorio por tipo de peca
```

### 2.1 Inspiracao Handle aplicada ao Causor

A referencia de produto da Handle nao deve ser copiada como tela bonita; o que importa e a arquitetura de mercado:

1. **System of Record operacional:** uma base central que sabe o estado real da operacao, mesmo quando os dados estao espalhados em portais, e-mail, WhatsApp, planilhas e sistemas legados.
2. **Agentes verticais por workflow:** agentes nao "respondem chat"; eles executam ciclos completos de trabalho, como cotacao, cobranca, reconciliacao e sinistros no caso de seguros.
3. **Computer use para sistemas fragmentados:** agentes operam portais como um funcionario faria, mas com trilha, checkpoints e fallback humano.
4. **Torre de controle:** lideranca enxerga gargalos, ROI, pendencias, risco e atividade dos agentes em tempo real.
5. **Integracoes com a pilha existente:** e-mail, WhatsApp, CRM/ERP, Excel/CSV e portais. O produto nao exige que o cliente troque tudo antes de receber valor.
6. **Seguranca e governanca como feature:** isolamento por tenant, criptografia, logs completos, controles humanos e rastreabilidade.

Traducao para o Causor: o objetivo nao e ser "monitor de publicacoes com chat". O objetivo e ser o sistema operacional do escritorio juridico: capturar, priorizar, redigir, revisar, protocolar, cobrar, atender cliente, medir ROI e auditar tudo.

### 2.2 Sidebar alvo para o Causor 360

As novas telas devem nascer em torno de workflows reais do escritorio, nao de entidades soltas. Sidebar proposta:

| Area | Tela na sidebar | Objetivo | Agente/automacao associada |
|---|---|---|---|
| Controle | **Torre de Controle** | Visao executiva: risco, SLA, ROI, gargalos, agentes rodando | Supervisor Agent |
| Dia a dia | **Hoje** | Worklist unica priorizada por risco, prazo e impacto | Operations Agent |
| Captura | **Capturas** | OABs monitoradas, DJEN/DataJud, falhas, cobertura | Capture Agent |
| Prazos | **Prazos** | Controle forense, radar D-3/D-1/hoje, revisoes | Deadline Agent |
| Protocolo | **Protocolos** | Jobs de protocolo, checkpoints, comprovantes, falhas PJe/e-SAJ | Filing Agent |
| Minutas | **Minutas & Templates** | Rascunhos, templates do escritorio, versoes, aprovacao | Drafting Agent |
| Processos | **Processos** | SOR por processo: timeline, documentos, intimacoes, atos | Case Agent |
| Clientes | **Clientes** | CRM juridico: clientes, contatos, status, proximas acoes | Client Agent |
| Atendimento | **Caixa Omnicanal** | E-mail, WhatsApp, chamadas/tarefas, triagem de pedidos | Intake Agent |
| Documentos | **Documentos** | Repositorio, classificacao, extracao, anexos para protocolo | Document Agent |
| Financeiro | **Financeiro** | Honorarios, cobrancas, inadimplencia, repasses, custas | Billing Agent |
| Equipe | **Equipe & SLAs** | Responsaveis, distribuicao, carga, produtividade | Routing Agent |
| Auditoria | **Auditoria** | Log imutavel, relatorios por processo/cliente/agente | Audit Agent |
| Integracoes | **Conectores** | PJe, e-SAJ, Projudi, EPROC, e-mail, WhatsApp, storage | Connector Hub |
| Seguranca | **Vault & Acessos** | Certificados, credenciais, permissoes, isolamento | Security Agent |
| Inteligencia | **ROI & Insights** | Horas economizadas, near-misses, cobertura, forecast | Insights Agent |

Regra de produto: uma tela nova so entra na sidebar se tiver um workflow claro, um dono operacional no escritorio e uma automacao associada. Isso evita virar um ERP generico.

### 2.3 Agentes verticais para dominar o escritorio 360

1. **Capture Agent**
   - Monitora OABs, DJEN/Comunica, DataJud e cobertura dos processos cadastrados.
   - Detecta intimacao orfa, processo sem monitoramento e falha de captura.
   - Tela principal: Capturas.

2. **Deadline Agent**
   - Calcula prazos, sinaliza risco, pede revisao quando a confianca da classificacao e baixa.
   - Dispara radar D-3/D-1/hoje e escalona para socio quando ninguem age.
   - Tela principal: Prazos e Hoje.

3. **Drafting Agent**
   - Usa templates do escritorio, historico e contexto do processo para gerar minuta.
   - Aprende com diferencas entre minuta IA e versao final aprovada.
   - Tela principal: Minutas & Templates.

4. **Filing Agent**
   - Prepara e executa protocolo assistido em PJe/e-SAJ com gate humano.
   - Registra checkpoint, evidencia, erro recuperavel e comprovante.
   - Tela principal: Protocolos.

5. **Intake Agent**
   - Le e-mail/WhatsApp, classifica pedidos de cliente, cria tarefas e vincula ao processo.
   - Nao responde cliente em nome do escritorio sem regra aprovada.
   - Tela principal: Caixa Omnicanal.

6. **Client Agent**
   - Gera atualizacoes em linguagem simples para cliente final.
   - Sugere proxima comunicacao e reduz "e meu processo?".
   - Tela principal: Clientes.

7. **Billing Agent**
   - Controla honorarios, custas, inadimplencia, repasses e cobrancas.
   - Cruza ato processual com evento financeiro quando aplicavel.
   - Tela principal: Financeiro.

8. **Document Agent**
   - Classifica documentos, extrai dados, monta pacote de protocolo e detecta anexo faltante.
   - Tela principal: Documentos.

9. **Supervisor Agent**
   - Observa todos os agentes, identifica gargalos e calcula ROI operacional.
   - Nao executa atos irreversiveis; apenas recomenda e escala.
   - Tela principal: Torre de Controle e ROI & Insights.

### 2.4 Ordem de expansao da sidebar

Nao adicionar tudo de uma vez. A ordem recomendada:

1. **Agora, junto da Fase 0:** Hoje, Protocolos, Minutas & Templates, Conectores, Vault & Acessos.
2. **Depois do primeiro protocolo:** Torre de Controle, Capturas, Documentos, Auditoria exportavel.
3. **Piloto 360:** Clientes, Caixa Omnicanal, Equipe & SLAs, ROI & Insights.
4. **Dominio operacional:** Financeiro, portal do cliente, billing, automacoes por area juridica.

---

## 3. Ordem recomendada de implementacao

### Sprint 1 - Fundacao para acoes longas e seguras

**Meta:** tirar protocolo/captura de dentro do request sincrono e criar trilho auditavel para jobs.
**Status:** iniciado. Fundacao local entregue: `job_execucao`, endpoints de jobs, protocolo async fake com gate e auditoria. Worker Redis/RQ real fica como proximo incremento desta sprint.

- Adicionar dependencias de fila: Redis ja existe no `infra/docker-compose.yml`; escolher RQ para simplicidade inicial.
- Criar modulo `backend/app/queue`.
- Criar modelo/tabela `job_execucao` ou equivalente:
  - `id`, `tipo`, `status`, `entidade`, `entidade_id`, `payload`, `resultado`, `erro`, `created_at`, `updated_at`.
- Expor endpoints:
  - `POST /jobs/capture/oab`
  - `POST /peticoes/{id}/protocolar/async`
  - `GET /jobs/{id}`
- Manter endpoints atuais sincronos por compatibilidade enquanto o front migra.
- Toda transicao de job gera `audit_log`.

**Criterio de aceite:**
- Um job fake de protocolo roda no worker e atualiza status.
- Front consegue mostrar `queued -> running -> completed/failed`.
- Testes cobrem sucesso, falha e auditoria.

### Sprint 2 - Vault e credencial de assinatura

**Meta:** ter contrato seguro para credenciais antes de automatizar portal.
**Status:** iniciado. Base local entregue: `backend/app/vault`, cadastro/listagem/desativacao de `CredencialAssinatura`, referencia `localdev://...` sem segredo bruto e testes contra vazamento em resposta/auditoria.

- Criar `backend/app/vault/service.py` com interface:
  - `store_reference(usuario_id, provider, external_ref)`.
  - `get_reference(credencial_id)`.
  - nunca retornar segredo bruto para agente/chat/log.
- Reusar `CredencialAssinatura` existente como referencia.
- Criar endpoints administrativos minimos:
  - `POST /usuarios/{id}/credenciais-assinatura`
  - `GET /usuarios/{id}/credenciais-assinatura`
  - `PATCH /credenciais-assinatura/{id}/desativar`
- Implementar `LocalDevVault` para desenvolvimento com referencia fake, sem segredo real.
- Preparar adapter futuro para BirdID/VIDaaS/Certisign/SafeID, mas sem travar a fase em integracao real.

**Criterio de aceite:**
- Nenhum campo de senha/certificado entra em `AuditLog`, resposta de API ou contexto do chat.
- Usuario consegue cadastrar uma referencia de credencial ativa.
- Testes provam que o vault nao vaza segredo.

### Sprint 3 - Templates do escritorio

**Meta:** melhorar qualidade da minuta antes de protocolo.
**Status:** iniciado. Base backend entregue: `TemplatePeticao`, CRUD minimo por escritorio, uso automatico do template ativo na geracao de minuta e testes de fallback/uso.

- Criar entidade `TemplatePeticao`:
  - `escritorio_id`, `tipo`, `area`, `nome`, `conteudo`, `ativo`.
- Atualizar `draft_from_intimacao` para escolher template por tipo/area quando existir.
- Front:
  - tela simples de templates;
  - preview;
  - aplicar template na minuta.

**Criterio de aceite:**
- Uma intimacao gera minuta usando template do escritorio.
- A classificacao da IA continua decidindo tipo/prazo; o template so estrutura a redacao.
- Testes cobrem fallback sem template.

### Sprint 4 - Conector PJe em modo assistido

**Meta:** conector Playwright executando fluxo feliz ate o ponto de confirmacao.
**Status:** adiado deliberadamente (decisao do usuario em `docs/superpowers/specs/2026-06-11-alinhamento-demo-design.md`): alinhar o software a landing antes de integrar APIs reais de tribunal. O protocolo segue simulado e rotulado como tal.

- Criar `backend/app/connectors/pje`.
- Definir interface comum:
  - `prepare_filing(peticao_id, credencial_id) -> FilingCheckpoint`.
  - `confirm_filing(checkpoint_id) -> FilingResult`.
- Implementar fluxo deterministico:
  - abrir sessao isolada;
  - login;
  - localizar processo;
  - iniciar peticionamento;
  - anexar peticao/documentos;
  - preparar assinatura;
  - parar antes do envio final quando houver risco/captcha/layout inesperado.
- Capturar evidencias:
  - screenshots ou referencias de artefato;
  - numero do protocolo quando concluido;
  - mensagem de erro recuperavel quando bloqueado.

**Criterio de aceite:**
- Em ambiente de teste/homologacao, o conector localiza um processo e prepara peticao.
- Se encontrar captcha/layout inesperado, falha de forma explicita e auditada.
- `protocolar` continua exigindo peticao aprovada.

### Sprint 5 - Protocolo no produto

**Meta:** colocar o fluxo no frontend sem esconder risco.
**Status:** entregue em modo simulado. Fluxo no produto: aprovar -> Protocolar abre modal com aviso de ato irreversivel, escolha de credencial do vault, job assincrono e comprovante; eventos na auditoria. `POST /peticoes/{id}/protocolar/async` aceita `credencial_id` validado (404/409).

- Substituir o botao "Protocolar" atual por fluxo:
  - validar peticao aprovada;
  - escolher credencial;
  - iniciar job;
  - acompanhar status;
  - mostrar checkpoint;
  - confirmar envio;
  - registrar comprovante.
- Exibir no detalhe da peticao:
  - status do protocolo;
  - eventos de auditoria;
  - comprovante/numero de protocolo.

**Criterio de aceite:**
- Advogado entende exatamente onde esta o ato irreversivel.
- Nenhum protocolo acontece por clique acidental.
- Auditoria mostra: preparado, aprovado, enviado, confirmado.

### Sprint 6 - Sidebar operacional da Fase 0

**Meta:** reorganizar o frontend para refletir a ambicao de escritorio 360 sem implementar todo o 360 ainda.
**Status:** entregue. Sidebar agrupada (Operacao diaria / Automacoes / Registro / Governanca) com Fila do dia ("Hoje"), Minutas, Templates, Gate OAB, Protocolos (jobs/checkpoints/comprovantes via `GET /jobs`), Conectores (status DJEN/DataJud/PJe/e-SAJ + seguranca/vault) e Auditoria. Vault em Configuracoes.

- Adicionar as telas de sidebar que dependem diretamente da Fase 0:
  - **Hoje:** worklist priorizada por risco.
  - **Protocolos:** jobs, checkpoints, comprovantes e falhas.
  - **Minutas & Templates:** rascunhos, editor e biblioteca de modelos.
  - **Conectores:** status PJe/DJEN/DataJud/e-SAJ futuro.
  - **Vault & Acessos:** credenciais de assinatura e controles de seguranca.
- Renomear/organizar a navegacao atual para separar:
  - Operacao diaria;
  - Automacoes;
  - Governanca;
  - Configuracao.
- Cada tela nova deve ter:
  - estado vazio util;
  - dados reais ou claramente rotulados como "em breve";
  - acao primaria;
  - vinculo com auditabilidade.

**Criterio de aceite:**
- Nenhum item de sidebar fica morto.
- `pnpm build` passa.
- O usuario entende que o produto esta evoluindo de MVP de prazo/protocolo para sistema operacional do escritorio.

---

## 4. O que nao fazer agora

- Nao construir varios tribunais ao mesmo tempo.
- Nao fazer billing.
- Nao implementar auth completa antes do primeiro protocolo, salvo o minimo necessario para piloto.
- Nao deixar o agente protocolar via tool-use.
- Nao colocar certificado, senha, `.pfx` ou token em prompt, log, response JSON ou screenshot publico.
- Nao transformar o conector em "computer use generico" para tudo; o caminho feliz deve ser deterministico.

---

## 5. Backlog imediatamente apos o primeiro protocolo

1. Torre de Controle com ROI, gargalos, SLA e agentes rodando.
2. Radar de prazos D-3/D-1/no dia, usando fila.
3. Worklist "Hoje" priorizada por risco.
4. Relatorio de auditoria exportavel por processo/cliente/agente.
5. Captura agendada multi-OAB.
6. Document Agent para classificar anexos e montar pacote de protocolo.
7. Caixa Omnicanal para triagem de e-mail/WhatsApp.
8. Clientes/CRM juridico com atualizacoes automaticas.
9. Financeiro para honorarios, custas, cobrancas e inadimplencia.
10. Segundo conector: e-SAJ ou outro conforme piloto.

---

## 6. Checklist de validacao da fase

- [x] `pytest` backend verde (112 passed em 2026-06-12).
- [x] `next build` frontend verde (tsc + build).
- [ ] Worker sobe localmente com Redis — adiado: jobs rodam in-process com o mesmo contrato de estado; RQ entra junto com o conector real (RQ nao suporta Windows dev sem SimpleWorker).
- [x] Nenhum segredo aparece em logs (testes cobrem job/auditoria sem referencia externa).
- [x] Peticao aprovada e obrigatoria antes do protocolo (409 testado).
- [x] Job de protocolo cria eventos no `audit_log` (job_criado/iniciado/concluido + peticao_protocolada).
- [x] Protocolo simulado retorna comprovante e checkpoint claros (rotulado "simulado — conector PJe em desenvolvimento"); real/homologacao adiado junto com o Sprint 4.
- [ ] Fluxo bloqueado por captcha/layout — depende do conector real (Sprint 4, adiado).
