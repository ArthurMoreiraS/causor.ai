# Causor como plataforma integrada do escritório

Em 05/09 o fundador ampliou explicitamente a visão: integrar mais da rotina do
escritório com IA e tornar os módulos mais claros na navegação. Este documento
atualiza o recorte de produto sem abandonar o piloto de qualidade das minutas.

**Resultado buscado:** uma informação cadastrada no atendimento acompanha o
cliente, o caso, as providências, a peça, o protocolo e a gestão do trabalho,
com origem e revisão preservadas. A IA ajuda a preparar e executar etapas
permitidas; cada módulo usa os mesmos registros e permissões.

## Leitura do produto atual

O código da navegação tinha 12 destinos, com grupos genéricos como Registro e
Automações. Termos como Gate OAB e Onboarding expunham nomenclatura interna.
Clientes já existiam no banco, mas não tinham módulo de cadastro na interface.
Não havia entidade persistente para tarefas de atendimento, coleta documental
ou revisão. Os alertas da minuta não viravam trabalho acompanhável.

Essas são observações do código. A captura visual não pôde ser feita: o
inventário de navegadores retornou vazio e a abertura do navegador integrado
falhou. Não foi realizada auditoria visual nem verificação por screenshot.

## O que a pesquisa acrescenta

O Astrea apresenta uma estrutura de processos, publicações/prazos, atividades,
atendimentos, clientes, documentos, finanças e relatórios. Isso mostra que o
escritório espera cobertura da rotina, além da redação de peças.
[Central oficial](https://astrea.aurum.com.br/pt-BR/) e
[produto](https://www.aurum.com.br/astrea/), consultados em 05/09.

O Projuris ADV também apresenta gestão de processos, IA, atendimento e
financeiro na mesma oferta. A conclusão para o Causor é construir conexões
entre essas atividades e medir o trabalho economizado em cada passagem.
Não foram verificadas precisão, satisfação ou cobertura dos fornecedores.
[Oferta oficial](https://www.projuris.com.br/adv/?v=start).

## Mapa completo de módulos

| Módulo | O que deve resolver | Papel da IA | Conexão principal |
|---|---|---|---|
| Visão geral | Prioridades, trabalho atrasado e decisões pendentes | Explicar prioridades a partir dos registros e apontar bloqueios | Consolida tarefas, processos e prazos |
| Clientes | Cadastro único, parte representada, histórico de relacionamento | Organizar informações recebidas e apontar dados faltantes | Atendimento → caso/processo → documentos |
| Atendimentos | Entrevista inicial, demanda, proposta e passagem para execução | Resumir entrevista autorizada, estruturar fatos e sugerir providências | Reutiliza cliente e abre tarefas/caso |
| Tarefas e pendências | Responsável, data interna, dependências, checklists e conclusão | Transformar avisos e análises em propostas de tarefas revisáveis | Ligação com cliente, intimação, processo e minuta |
| Agenda e audiências | Compromissos, preparação e providências posteriores | Preparar roteiro e resumir registros autorizados | Audiência gera tarefas e atualiza o caso |
| Processos e casos | Carteira judicial e trabalho consultivo ainda sem processo | Cronologia, fatos relevantes, mudanças e pontos de atenção | Contexto compartilhado com documentos e minutas |
| Intimações e prazos | Triagem, providência e vencimento conferido | Classificar e propor ação; aritmética continua determinística | Cria tarefa, prazo ou minuta conforme a necessidade |
| Documentos e evidências | Acervo, versões, origem, páginas e pendências | Extração, classificação, comparação e recuperação de evidências | Alimenta análise e redação; integra documentos do cliente |
| Minutas e contratos | Produção judicial e consultiva com fontes e padrão do escritório | Planejar, redigir, comparar revisões e sinalizar lacunas | Usa contexto do caso, modelos e instruções aprovadas |
| Revisão e aprovação | Responsabilidade, versão revisada e pendências | Apoiar conferência, sem atribuir aprovação jurídica automática | Autoriza o pacote exato da próxima etapa |
| Protocolos e assinaturas | Preparo, destino, anexos, envio e recibo | Apoiar preenchimento e tratar exceções no canal homologado | Resultado volta ao processo e ao cliente |
| Conhecimento do escritório | Modelos, teses e orientações aprovadas, com vigência e fonte | Recuperar material pertinente sem misturar fatos entre clientes | Reutilizado em minutas, contratos e atendimento |
| Financeiro e honorários | Contrato de honorários, parcelas, despesas, cobrança e recebimento | Sugerir classificação e preparar cobranças para revisão | Cliente/caso e trabalho executado compartilham referência |
| Comunicação e portal do cliente | Atualizações, solicitações documentais e acompanhamento | Traduzir eventos para linguagem acessível e preparar mensagens | Mensagem vinculada ao caso; envio e recebimento registrados |
| Equipe e indicadores | Carga, tempo, retrabalho, cumprimento e custo por trabalho aceito | Explicar gargalos com evidências dos registros | Métricas derivadas dos eventos, não contadores fictícios |
| Automações e integrações | Gatilhos, propostas, execução, falhas e retomada | Coordenar ferramentas autorizadas e pedir intervenção quando necessário | Usa os mesmos serviços dos módulos manuais |

Esse é o mapa de evolução, não a lista de capacidades prontas. Documentos,
contratos, financeiro, portal e agenda próprios ainda exigem entregas descritas
abaixo. APIs de calendário, mensagens, assinatura, dados judiciais e cobrança
serão avaliadas pelo fluxo concreto; nenhum fornecedor foi contratado.

## Integração que precisa existir

Exemplo de percurso futuro:

1. Atendimento registra cliente, demanda e documentos recebidos.
2. Revisão humana confirma a providência; o sistema abre caso e tarefas.
3. A coleta documental alimenta o mesmo acervo usado na análise e na peça.
4. Uma informação ausente na minuta vira pendência atribuída a alguém.
5. O documento recebido resolve a pendência e provoca nova conferência do contexto.
6. A peça revisada forma o pacote de assinatura/protocolo.
7. O comprovante atualiza o caso; uma comunicação ao cliente é preparada.
8. Tempo e despesas alimentam gestão e honorários, sem recadastro.

A execução automática de cada passagem só entra quando o evento, permissões,
estado de sucesso e forma de desfazer/retomar estiverem definidos. Concluir
uma tarefa não significa que a IA recebeu prova, que o contexto está completo
ou que houve protocolo. Esses resultados têm verificações próprias.

## Primeira expansão implementada nesta rodada

### Navegação

- **Trabalho diário:** Visão geral, Tarefas e pendências, Intimações, Prazos.
- **Escritório:** Clientes, Processos.
- **Produção jurídica:** Assistente Causor, Minutas, Modelos de peças, Revisão e aprovação, Protocolos.
- **Administração:** Integrações, Histórico de ações, Configuração inicial.

A largura expandida passa de 220 para 260 px, com rótulos maiores e destinos
com URL por módulo (`#clientes`, `#tarefas` etc.), preservando voltar/avançar.
Os grupos continuam recolhíveis. Módulos futuros ficam no plano; o menu aponta
somente para telas implementadas. A expansão futura poderá oferecer favoritos
e organização por função quando o uso justificar mais destinos.

### Clientes

Cadastro inicial de nome/razão social e documento opcional; busca paginada;
contagem de processos; ficha com processos carregados e criação de tarefa.
O vínculo identifica a parte representada usada nas próximas minutas.
A interface oferece processos ainda sem cliente; a API bloqueia mudança de
parte enquanto houver minuta aprovada ou em protocolo. Minutas existentes
devem ser conferidas depois de um vínculo novo.

Não há CRM comercial completo, edição cadastral, portal, contatos múltiplos
ou validação fiscal do CPF/CNPJ nesta entrega.

### Tarefas e pendências

Registro persistente com título, descrição, tipo, prioridade, responsável,
data interna, situação e ligações com cliente/processo/intimação/minuta.
Busca e paginação no servidor, edição com controle de versão, cancelamento,
conclusão e reabertura. Cada gravação relevante gera auditoria.

É possível criar a tarefa na ficha do cliente, no detalhe do processo ou da
intimação e na lista de intimações. Um alerta da IA na minuta pode virar
pendência após o advogado revisar o formulário. O servidor confere a origem,
recusa alerta alterado e reutiliza a tarefa do mesmo alerta para evitar
duplicação. Isso não é criação automática pelo assistente: a ação humana é
explícita e não faz nova chamada paga de IA.

Data interna não gera nem altera prazo judicial. Conclusão de tarefa não
aprova peça e não libera o gate documental. Relações só podem apontar para
dados do mesmo escritório. Se uma origem for removida, as FKs do PostgreSQL
desvinculam a tarefa; seu registro e histórico permanecem.

## Ordem de construção a partir daqui

| Bloco | Entrega | Aceite |
|---|---|---|
| 1 — esta rodada | Navegação, Clientes e Tarefas conectados | Cadastrar cliente → vincular processo → criar pendência da intimação/alerta → atribuir → concluir, com persistência e isolamento |
| 2 — qualidade das minutas | Cinco casos do parceiro; evidências orientadas à providência e lacunas documentais | Revisão cronometrada identifica erros e documentos ausentes; corrigir a causa principal e repetir com entrada fixa |
| 3 — documentos e preparo | Biblioteca por caso, pedidos de documentos, modelos do escritório, exportação e pacote de anexos | Documento solicitado entra no mesmo acervo da minuta; pacote final reproduz o aprovado |
| 4 — atendimento e agenda | Histórico de atendimento, caso consultivo, compromissos/audiências e tarefas posteriores | Uma demanda recebida vira trabalho acompanhado sem recadastro |
| 5 — operação externa | Primeiro canal judicial; assinatura e mensagens nos canais escolhidos | Destino/ato reais homologados, intervenção explícita e recibo reconciliado; mensagens só enviadas com autorização |
| 6 — gestão | Honorários, despesas, tempo e indicadores; portal do cliente | Trabalho realizado alimenta cobrança e acompanhamento com permissões e valores conferidos |
| 7 — automações configuráveis | Gatilhos por evento, ferramentas do assistente e biblioteca de fluxos | A mesma operação manual e automática usa regras, evidências, permissões e auditoria compartilhadas |

Para desenvolvimento solo, manter um fluxo completo em construção por vez.
Esse limite organiza a execução da plataforma completa; não reduz a visão à
automação de minutas. Agenda ou financeiro podem subir de prioridade se o
piloto mostrar que concentram o retrabalho, com mudança explícita de backlog.

O próximo bloco do plano original continua sendo a avaliação com o advogado.
As pendências identificadas nessa revisão agora têm onde ser acompanhadas
no produto. Sem exemplos fornecidos, podemos preparar o fluxo e as ferramentas,
mas ainda não medir qualidade jurídica real ou economia de tempo.

## Roteiro do próximo teste com o advogado

Usar um caso histórico autorizado do piloto; os dados e documentos ficam no
ambiente do escritório, fora do repositório. Registrar o tempo de cada etapa
e a primeira dificuldade encontrada:

1. Abrir **Clientes**, cadastrar a parte representada e vincular o processo.
2. No processo, enviar os documentos e conferir o inventário e a extração.
3. Gerar a minuta da intimação e conferir fatos, fontes e documentos ausentes.
4. Em um alerta pertinente, usar **Criar pendência**, revisar a descrição e
   escolher responsável e data interna. A tarefa deve aparecer em **Tarefas**.
5. Abrir a minuta de origem pela tarefa e conferir que o alerta foi preservado.
6. Registrar a providência tomada e concluir a tarefa. Conferir o contexto
   documental separadamente antes de gerar/revisar a próxima versão da peça.
7. Levar a peça à **Revisão e aprovação**, conferir o PDF e anotar o tempo de
   correção. O piloto não exige nem autoriza um protocolo judicial de teste.

Classificar o retrabalho como fato ausente/incorreto, fonte inadequada,
providência errada, redação, formatação ou dificuldade de navegação. O primeiro
ciclo de melhoria deve atacar a causa recorrente observada nesses registros.

## Validação da entrega

Localmente: **670 testes de backend aprovados, 42 pulados** (36 exigem o
PostgreSQL descartável do CI; 6 são opt-in), **75 testes de frontend**, Ruff,
ESLint, TypeScript e `git diff --check` aprovados. Os 12 cenários do novo módulo
também passaram em execução dedicada, incluindo abertura da minuta de origem.
Há testes de integração HTTP e de interação dos componentes com APIs simuladas.

A migração `a6c2e8f4b0d3` cria a tabela de tarefas e depende de
`a5f1b7d3c9e2`. O [CI da versão c0e18fb](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33944040745)
aprovou **36 cenários em cada PostgreSQL (16/17)**, incluindo migração real,
deduplicação concorrente e preservação da tarefa após remover uma origem.
Backend, frontend e build de produção no Linux também passaram.
Esses testes não substituem a verificação visual e o piloto com o advogado.

**Implantação confirmada em 05/09 às 01h21 (Brasília):** o
[deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33944092928)
aplicou `a6c2e8f4b0d3` e verificou a versão exata `c0e18fb` nos quatro
serviços (backend, worker, autos-worker e frontend), todos saudáveis.
O escopo atual termina nessa primeira expansão; os demais módulos da tabela
continuam no plano, com aceites próprios.
