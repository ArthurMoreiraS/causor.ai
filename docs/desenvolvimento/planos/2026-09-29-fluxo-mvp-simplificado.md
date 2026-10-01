# Plano: captura, prazo e preparação de minuta em um fluxo

Estado: execução autorizada pelo fundador em 29/09/2026. Etapa 1 implementada e
revisada localmente (lint, tipos, 120 testes frontend). Etapa 2 em implementação.
Sem novo deploy; conferência visual ainda indisponível.
Em 30/09 o fundador priorizou três novos prints de desalinhamento. Correção
direta pelo coordenador após indisponibilidade do executor Sol por capacidade:
painel de autos com campos padronizados e botões sem esticar, barra de análise
com hierarquia/espaçamento e avisos do dashboard com ação separada do texto.
Revisão adjacente corrigiu campos de índice e checkboxes de evidências.
Native Computer Use falhou por pipe indisponível; inventário de browsers vazio.
Testes de DOM não substituem conferência visual. Retomar as etapas abaixo após
verificação dessas correções, conforme pedido do fundador.
Este plano coordena a próxima execução e incorpora o plano técnico
`2026-09-29-prazos-apos-captura.md`. A pausa para consolidação do plano terminou
com a autorização de execução; o diagnóstico abaixo registra a situação inicial.

## Objetivo e decisões de produto

Capturar intimações e processos, iniciar automaticamente a análise dos prazos,
reunir documentos e informações do advogado, produzir minuta fundamentada nas
fontes disponíveis e permitir revisão humana. Preservar a interface informativa
atual, corrigindo organização e comportamento. Não fazer outro redesenho global.

- Trabalho é a preparação persistente de uma peça: objetivo, parte representada,
  processo/intimação/prazo, documentos, informações e fontes conferidas.
- Minuta é o documento gerado nesse trabalho, com versões, edição e revisão.
- Um caminho de criação. Trabalhos contém `Novo trabalho`; Minutas funciona
  como biblioteca/editor dos resultados e permite voltar ao trabalho de origem.
  Minutas legadas sem trabalho continuam acessíveis.
- Remover `Novo trabalho` da sidebar. Manter `Trabalhos` como módulo.
- Na intimação, uma ação principal `Preparar minuta` inicia/retoma esse mesmo
  fluxo. Não gera uma peça imediatamente nem abre um segundo criador.
- Criar tarefa fica em ações secundárias. O prazo aparece como informação e
  status clicável; não como terceiro botão espremido na célula.
- Manter Assistente em Escritório e preservar Clientes, Processos e Documentos.
  PJe, protocolo e captura automática de autos não entram neste escopo.

## Diagnóstico: observado versus ainda a reproduzir

| Achado | Evidência e limite |
| --- | --- |
| Captura não calcula prazo | `backend/app/capture/poll.py` não enfileira análise; worker atende captura, sem job de prazo. Última consulta registrada em estado.md tinha 614 intimações e zero prazos; não foi feita nova consulta nesta análise. |
| Prazo depende hoje de revisão manual ou caminho legado de geração | `ConfirmarPrazo.tsx` exige todos os parâmetros; classificação em `agent/service.py` vem depois do gate de contexto. Eliminar a diferença de regra entre as duas entradas. |
| Formulário de prazo sem layout | `ConfirmarPrazo.tsx` usa labels/inputs sem o contêiner `.officeForm` nem estrutura equivalente; estilos dos formulários em `office.css` são restritos. Compatível com o print. |
| Ações comprimidas | `IntimacoesView.tsx` põe três botões em `.dataRowEnd`; `globals.css` reserva 120px para essa coluna. |
| Novo trabalho duplicado | Existe na sidebar e no cabeçalho de Trabalhos. Limpar um formulário já vazio pode parecer que nada ocorreu. Há callback implementado; isso não prova funcionamento na sessão do usuário. |
| Preparar trabalho quebra na sessão do usuário | Há caminho em `page.tsx`, props iniciais, chave de remontagem e retomada por query string. Causa exata ainda não reproduzida. Auditar troca de origem, detalhe aberto, refresh, respostas atrasadas e volta entre módulos. |
| Entrada manual existe, mas é fragmentada | Trabalhos divide objetivo, upload, status de contexto, declaração de escopo, índice, análise, conferência e geração em componentes separados. Campos de WorkScope fora de `.officeForm` também exigem revisão de estilo. |
| Retomada merece correção | Intenção inicial vive no estado React; URL persiste ID só após selecionar/salvar trabalho. O polling de Trabalhos ignora resultado com versão diferente, podendo conservar estado desatualizado. Reproduzir antes de corrigir. |
| Testes insuficientes para os bugs relatados | 6 testes passaram em NoticeToWork, ConfirmarPrazo e SidebarNavigation nesta análise. NoticeToWork simula APIs e remove componentes de documentos/evidências; não testa CSS, navegador ou o percurso integrado. |

Nenhum teste novo, alteração de produto, análise de IA real, migração ou deploy
foi executado nesta revisão. O arquivo parcial `backend/app/prazo_engine/djen.py`
foi preservado; está sem integração/testes e não constitui funcionalidade pronta.

## Experiência proposta

Entrada A: Capturar OAB → intimações/processos salvos + análise de prazos iniciada
automaticamente → abrir intimação → Preparar minuta.

Entrada B: Trabalhos → Novo trabalho → selecionar/cadastrar processo.

Ambas chegam a uma preparação com três etapas e progresso salvo:

1. **Objetivo:** peça/providência, parte representada, instruções; processo e
   origem já preenchidos quando vier da intimação. Prazo em resumo separado.
2. **Documentos e contexto:** enviar PDFs, selecionar os já existentes, informar
   fatos e orientações do advogado, acompanhar processamento e conferir resumo,
   fontes e lacunas. Detalhes de índice/páginas e cobertura ficam em expansão.
3. **Minuta e revisão:** gerar, editar, conferir citações, salvar versão e revisar.

Informação digitada deve ser persistida, incluída na análise e distinguida de
fato documentado. Não converter relato do cliente em prova automaticamente.
Não exigir redigitação de dados já capturados. Exibir o que falta e o próximo
passo em cada bloqueio. Salvar explicitamente as etapas e proteger alterações
não salvas; retomar após refresh sem perder vínculos ou documentos.

## Ordem de execução e aceites

### 1. Estabilizar navegação e formulários

Reproduzir os dois botões quebrados no app integrado, registrar erro de console
e requisição relevante sem tokens ou teor sigiloso, e escrever regressão que
falhe. Corrigir contrato único de entrada/retomada entre page.tsx e Trabalhos.
Remover ação da sidebar, colocar criação explícita dentro do módulo, reduzir
ações da lista e padronizar formulário de revisão de prazo.

Aceites: novo formulário é claramente aberto; preparar pela intimação mantém
processo/origem/prazo; trocar de trabalho não restaura resposta antiga; sair e
voltar não perde progresso salvo; falta de processo oferece ação de vinculação;
nenhum overflow em 390px, 768px e 1440px; teclado/foco e erros legíveis.

### 2. Cálculo disparado pela captura

Implementar o plano de prazos anexo. Disparar ao persistir a comunicação, sem
esperar documentos, criação de trabalho ou clique em calcular. Persistir fila
e progresso; falha de análise não desfaz captura e não prende modal.

Extrair parâmetros e evidência do teor, validar suporte da interpretação e
calcular datas no motor determinístico. Primeiro recorte: publicação DJEN cível
com parâmetros sustentados. Separar calendário de publicação e de contagem.
Calendários locais não conferidos devem ficar explícitos. Casos incertos ou
regimes não suportados ficam pendentes com motivo; nunca receber prazo padrão.

Estados: analisando, calculado a revisar, pendente de informação, sem prazo
identificado, falha e confirmado. Ausência de prazo identificado não significa
certeza de inexistência. Mostrar memória e permitir corrigir/confirmar a mesma
linha; não sobrescrever confirmação humana. Atualizar lista e painel sem reload.

Corrigir isolamento da deduplicação atual por fonte/fonte_id antes de enfileirar
análises: um escritório não pode reaproveitar/mutar a intimação de outro.
Unificar o caminho legado que cria prazo na geração; edição de parâmetros deve
recalcular ou invalidar resultado, nunca manter vencimento incompatível.

Aceites: captura simulada gera prazo a revisar; repetição não duplica; feriados,
recesso, início/fim e ambiguidade têm TDD; recuperação de job e concorrência
passam em PostgreSQL; tenant isolado; dados já capturados têm processamento
em lote retomável sem recapturar DJEN nem sobrescrever prazo humano. Lote real
fica para operação após validação, não como execução de testes.

### 3. Entrada manual de contexto de ponta a ponta

Achados adicionais na execução: `draft_work` exige cliente vinculado ao processo
e polo, mas a tela só oferecia cliente no cadastro de processo novo. Oferecer
vinculação/criação também para processo capturado, mantendo vínculo existente
visível e evitando troca silenciosa. `DocumentUploadDialog` inicia grau 1 sempre:
herdar o grau do trabalho e manter o processo de destino fixo nessa entrada.
Proteger também alterações de escopo/índice, não só objetivo, ao sair ou receber
atualização remota. A declaração de outro grau não aplicável deve continuar
explícita; não dispensar documentos automaticamente para contornar o gate.

Storage: API/worker de produção compartilham volume no Compose, mas o disco
local não é esse volume. A fila `process_document` atual não diferencia stores;
com banco compartilhado, o worker de um ambiente pode consumir o upload do outro
sem ter seus bytes. Evitar essa disputa com identificação do storage nos jobs e
seleção pelo worker correspondente, ou store compartilhado configurado. Não
resolver marcando documento ausente como processado. Fundador confirmou que não
há bucket privado. Manter storage atual, identificar o store nos jobs e impedir
consumo por ambiente sem os bytes; informar limitação de disponibilidade ao abrir
arquivo em outro ambiente. Configuração futura de bucket não bloqueia o upload
e processamento no mesmo ambiente; nenhum segredo deve ser solicitado no chat.
O identificador do store local deve acompanhar o volume físico compartilhado
pela API e pelo worker do mesmo ambiente (marcador persistente no diretório),
sem depender do hostname de contêiner ou do caminho textual. Jobs legados sem
identificador precisam de uma regra conservadora que confira acesso aos bytes,
inclusive na recuperação de lease. Testar dois stores distintos sobre o mesmo
banco descartável: somente o worker com acesso ao PDF pode reivindicar o job.

Consolidar upload, documentos existentes, informações digitadas, escopo e
conferência na segunda etapa. Reusar backend de documentos/extração/contexto.
Eliminar campos repetidos e pré-preencher referências conhecidas. Manter índice
detalhado opcional quando não necessário à identificação das fontes.

Revisão de 30/09: o índice atual descreve origem e peças; não filtra o conjunto
usado pelo gerador. Preservar a análise do acervo processado completo do processo
e explicitar isso na interface, evitando que o índice pareça uma seleção de
fontes. Exibir o inventário/versões efetivamente usados e identificar referências
do índice a versões anteriores. Não excluir prova contrária por omissão no índice.
Sincronizar filhos com o snapshot atual sem perder campos não salvos e invalidar
a conferência local quando a análise mudar. Respostas de busca antigas não podem
atualizar outro trabalho ou outra consulta.

Aceites: PDF nativo e escaneado têm progresso/erro recuperável; texto e fontes
podem ser conferidos; informações digitadas sobrevivem a refresh e aparecem no
contexto da geração; grau/processo de destino corretos; fonte de outro processo
ou escritório nunca entra; arquivo novo invalida análise antiga; duplicidade de
upload e versões são explícitas. Falta de documento não pode parecer conclusão
de processamento. Conferir storage local versus produção para arquivo não sumir
ao acessar o mesmo registro por outro ambiente.

### 4. Gerar e revisar a minuta dentro desse trabalho

Achado adicional: as rotas atuais executam a chamada de IA dentro do request
HTTP, embora liberem a transação antes dela. O transporte frontend comum não
tem timeout. A próxima implementação deve incluir acompanhamento recuperável
da análise e geração (fila persistente existente), com identidade/versionamento
do trabalho, timeout do provedor, resultado tardio descartado e deduplicação.
Fechar a tela não deve apagar o acompanhamento nem criar outra minuta ao voltar.
Na publicação do resultado, conferir também os parâmetros e o status do prazo
usado na redação: o ID do prazo sozinho não detecta uma correção de vencimento
feita enquanto o modelo responde. Guardar o snapshot utilizado no dossiê.

Unificar entrada de geração, manter vínculo trabalho/minuta e histórico. Exibir
objetivo, fontes incluídas e lacunas. Preparação de evidências e geração precisam
de timeout, erro recuperável e prevenção de duplicação; usar job persistente
se a chamada longa não suportar retomada após perda da resposta.

Aceites: contexto conferido chega ao gerador; minuta cita documentos/páginas
existentes; relatos ficam identificados; lacunas/contradições não desaparecem;
editar e reabrir preserva versão; alteração de contexto pede nova conferência;
aprovação é invalidada quando conteúdo muda. Qualidade final exige leitura do
advogado de um caso autorizado, com critérios explícitos de fatos, pedidos,
fundamentação, fontes e omissões.

### 5. Validação integrada e entrega

- Caminho capturado: OAB → intimação/processo → prazo → preparar → upload →
  contexto conferido → minuta → edição/revisão → reabrir.
- Caminho manual: Novo trabalho no módulo → processo → informações e PDFs →
  mesmo percurso de contexto/minuta.
- Falhas: sessão expirada, rede lenta, resposta perdida, refresh, clique repetido,
  documento ilegível, prazo ambíguo, IA indisponível e versão concorrente.
- Local isolado: pytest/ruff backend, pnpm.cmd check frontend. Não rodar build
  no `.next` de desenvolvimento ativo; build Linux e PostgreSQL 16/17 no CI.
- Conferência visual real nas três larguras; registrar capturas antes/depois.
  Se navegador indisponível, declarar essa lacuna, sem chamar DOM de teste visual.
- Testes usam banco descartável e providers simulados. Caso real autorizado
  separado, com revisão do advogado; não rodar lote de produção como teste.
- Deploy usa autorização já existente após gates; verificar SHA e saúde e
  repetir percurso funcional. CI/deploy verde não substitui aceite do fluxo.

## Coordenação e limites de escopo

Astra coordena e revisa; um worker Sol implementa um bloco delimitado por vez,
com arquivos, critérios e comandos definidos na delegação. Revisar diff real e
evidências antes do próximo bloco. Backend: capture/normalize, queue, engine,
API/schemas/modelos necessários e work_service. Frontend: navegação, página,
intimações/prazos/trabalhos/minutas, formulários, documentos/contexto e estilos.

Preservar alterações anteriores do usuário e documentos não rastreados. Não
apagar módulos/dados para simplificar a navegação. Separar nos relatos:
implementado, testado com simulação, verificado visualmente, implantado e
validado com caso real. Conclusão é o percurso funcional e revisável, não a
quantidade de componentes ou testes aprovados.
