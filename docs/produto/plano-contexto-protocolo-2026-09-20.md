# Plano de execução: contexto dos autos, minuta e protocolo

Data: 20/09/2026. Status: plano solicitado pelo fundador; implementação ainda não iniciada nesta rodada.

## 1. Resultado e restrições

Construir sobre o Causor existente um percurso funcional:

**Abrir trabalho → receber documentos → conferir contexto → gerar e revisar minuta → aprovar pacote → encaminhar protocolo → acompanhar comprovante.**

O fundador está sem acesso a sistemas de tribunal. Isso não bloqueia cadastro de casos, processamento documental, seleção de evidências, geração, revisão, pacote, registro de comprovantes e testes do executor. Leitura autenticada, assinatura e envio reais exigem homologação posterior. Não apresentar testes simulados como comprovação de integração judicial.

Primeiro marco: concluir esse percurso no navegador, com envio externo pelo advogado, sem instalar agente e sem corrigir registros diretamente no banco. A automação judicial usará o mesmo trabalho, pacote e histórico quando estiver disponível.

O objetivo comercial permanece um piloto pago. A liberação depende de demonstração do fluxo assistido e revisão jurídica de exemplos autorizados; a construção interna pode avançar agora com casos sintéticos. Datas abaixo são estimativas de esforço de um desenvolvedor, não compromissos de disponibilidade de tribunal ou clientes.

## 2. Evidência do repositório e lacunas

Base examinada: HEAD `953e18c`, documentação de implantação de 05/09 e código local. Não houve execução do app, nova bateria de testes, inspeção visual ou verificação da produção nesta análise.

| Área | Reutilizar | Lacuna observada / decisão |
|---|---|---|
| Entrada de trabalho | Clientes, processos capturados, tarefas, intimações | Nas rotas examinadas não há cadastro manual de processo; geração parte de uma intimação. Adicionar entrada explícita sem depender de DJEN e sem fabricar intimação. |
| Acervo | Upload complementar, versões por hash, inventário, armazenamento privado, OCR, trechos e resumos | Distinguir integridade dos arquivos recebidos, cobertura do escopo declarado e evidências necessárias à providência. |
| Contexto | `autos/context.py` reúne inventário, resumos e citações; confere fingerprint | O gate espera graus 1 e 2 ou declaração de não aplicabilidade. Tornar a declaração de escopo clara, preservando o bloqueio quando o escopo é desconhecido. |
| Recuperação de fontes | `autos/chunks.py` tem busca nos trechos | `agent/context_selection.py` seleciona excertos das citações dos resumos. Um fato que não entrou no resumo pode não chegar ao redator. Buscar também no texto original indexado, limitado às versões do contexto. |
| Redação | `agent/service.py`, `drafter.py`, templates, avaliação e revisão cega | Introduzir preparação de evidências por providência, cobertura de pontos essenciais e revisão das afirmações. |
| Aprovação | `filing/approval.py` persiste PDF e hash | Os inputs e snapshot usam `grau="1"` e `anexos=[]`. Evoluir para pacote real com destino, grau e anexos versionados. |
| Protocolo | Fila, contratos neutros, registro manual, conector PJe legado | `local_agent/handlers.py` termina leitura e preparo com `NotImplementedError`. Não há rota local operacional comprovada. |
| Comprovante | `confirm_manual_protocol` registra origem manual e URI não verificada | Adicionar arquivo privado do recibo, conferência dos campos, vínculo ao pacote e estado de evidência. A função atual marca a petição como protocolada pela declaração; preservar a origem na migração. |
| Agente | Pareamento, keyring, sessão por rota, claim, heartbeat e auditoria | O claim atual escolhe comando por escritório. Vincular execução à instalação/identidade autorizada e capacidades. Tratar perda de posse e envio incerto. |
| Assistente | Consulta prazos/processo/intimação e propõe ações | Faltam ferramentas documentais e de acompanhamento do trabalho. Usar os mesmos serviços da interface. |
| Interface | Biblioteca, visualizador de fontes, editor, tarefas e aprovação | Unificar o percurso por trabalho; corrigir texto que promete protocolo concluído em `ProtocolarModal.tsx`. |

Arquivos relevantes são relativos à raiz: `backend/app/...` e `frontend/app/...`. A documentação histórica contém afirmações superadas; os achados acima e o estado datado prevalecem para este plano.

## 3. Experiência do usuário

O ponto de entrada será **Preparar trabalho**, na ficha do processo ou numa intimação. Abre uma área do caso com cinco etapas e uma próxima ação principal:

1. **Objetivo:** cliente, parte representada, processo, instância, providência, instruções e prazo confirmado ou pendente. Intimação é vínculo opcional para trabalhos manuais.
2. **Documentos:** receber autos e subsídios do cliente; mostrar escopo declarado, progresso, versões, problemas e documentos solicitados.
3. **Análise:** cronologia, decisão relevante, fatos, fontes, provas contrárias e pendências para aquela providência.
4. **Minuta e revisão:** texto e fontes lado a lado, alertas acionáveis, correções e versão do contexto utilizada.
5. **Protocolo:** revisar pacote, aprovar versão, escolher o canal disponível, exportar ou executar e acompanhar o recibo.

Cada etapa mostra resultado persistido, problema e ação possível. Reabrir a página retoma o trabalho. A tarefa do escritório aponta para essa mesma área. Os módulos globais continuam como listas e filtros; não criam fluxos concorrentes.

Exemplo de mensagem: “12 documentos recebidos; 11 processados; página 8 do laudo precisa de conferência. Corrigir documento.” Quando tudo estiver processado: “Acervo enviado processado. Integralidade declarada por Ana em 20/09. Falta conferir a decisão indicada para esta manifestação.”

Não chamar simplesmente de “contexto íntegro” todo acervo processado. Exibir três dimensões:

| Dimensão | O que se consegue afirmar |
|---|---|
| Integridade dos arquivos | Bytes, versões, páginas, extração e referências conferidos no material recebido. |
| Cobertura do processo | Origem, instâncias, data de referência e relação de documentos declarada ou confrontada com uma fonte externa identificada. |
| Preparação para o trabalho | Pontos essenciais e lacunas revisados para uma providência específica. Isso não certifica correção jurídica. |

Sem fonte externa, o Causor não sabe se uma peça foi omitida antes do upload. Documentos novos também podem existir no tribunal após a data de referência. Essa limitação deve aparecer junto da decisão de revisão, sem bloquear indevidamente toda a experiência assistida.

## 4. Responsabilidade do agente

### 4.1 Assistente Causor, executado no servidor

Organiza o trabalho, consulta o acervo autorizado, busca fontes, prepara análise e minuta e propõe pendências. Usa APIs internas autenticadas; não precisa controlar o navegador para clicar na própria interface do Causor.

Ferramentas propostas, com nomes indicativos: `consultar_trabalho`, `listar_documentos`, `buscar_trechos`, `abrir_fonte`, `consultar_lacunas`, `preparar_evidencias`, `gerar_minuta`, `propor_pendencia`, `consultar_pacote` e `consultar_protocolo`.

Leituras ficam limitadas a escritório, processo e fotografia documental. Ações usam serviços de domínio, validação de versão e auditoria. O assistente não aceita endpoint arbitrário do modelo nem decide sozinho que a aprovação foi concedida. A autorização para produzir a minuta pode cobrir suas etapas reversíveis; aprovação do pacote e envio continuam explícitos.

O chat acompanha o trabalho aberto e responde com fontes e ações compatíveis com seu estado. O fluxo também funciona inteiramente por botões, sem exigir que o advogado saiba escrever prompts.

### 4.2 Executor Causor, instalado no computador do advogado

Responsável somente pelas operações externas que realmente precisam da sessão local. Reutilizar o runtime existente. Não exigir sua instalação para upload, análise, minuta, revisão ou exportação.

Na interface, o executor aparece no momento de usar uma integração homologada, com estado do computador, sessão e operação. Configuração avançada permanece em Integrações. “Online” não significa “pode ler/protocolar neste tribunal”.

Antes de qualquer execução: conferir escritório, usuário/identidade autorizada, instalação destinada, versão do executor, capacidade, rota, pacote aprovado e posse vigente do comando. Um computador de outro advogado do mesmo escritório não pode reivindicar automaticamente um ato com outra sessão.

Separar **preparar**, **aguardar intervenção**, **enviar** e **reconciliar resultado**. Ao perder heartbeat/posse, o executor interrompe novas etapas; antes de enviar, renova/confere a autorização. Se a conexão cair depois do envio, não há repetição automática: registrar resultado incerto e verificar o que aconteceu.

Hoje podemos completar esse ciclo com simuladores e operações sem tribunal. Não gastar a primeira semana em instalador, atualização automática ou navegador remoto. Empacotamento para usuário final entra após demonstrar uma operação externa útil.

### 4.3 Fontes e canais externos

Upload é uma entrada permanente. MNI permanece condicionado a credencial e validação. Uma API contratada poderá alimentar o mesmo inventário. Preservar `resolve_capture_fonte` como dono do roteamento; `access_channel` expõe capacidades e o assistente traduz a próxima ação, sem criar um terceiro seletor de rota.

A documentação atual da Judit descreve cache, atualização assíncrona e status por anexo; a do Escavador descreve consulta dos autos e atualização. Isso justifica contratos que representem documento pendente, paginação, origem e atualidade, não uma promessa de que o número CNJ sempre devolverá todos os PDFs. Nenhuma dessas integrações foi contratada ou homologada neste plano. [Judit](https://docs.judit.io/requests/requests), [Escavador](https://api.escavador.com/v2/docs/consulta-de-processos).

Não iniciar adapters de vários fornecedores. Escolher um canal quando houver processos, acesso, custo e critério de aceite concretos. A decisão de compra versus conector próprio não bloqueia as entregas abaixo.

## 5. Preparação de contexto para a minuta

### 5.1 Entrada e escopo

- Cadastrar processo manualmente, com número validado e deduplicação por escritório, sem exigir consulta online. Preservar processo/instância existentes quando houver correspondência.
- Criar trabalho com ou sem intimação; o prazo fica pendente quando não houver dados confirmados. Não fabricar publicação ou vencimento para habilitar uma minuta.
- Separar a origem de cada documento: autos enviados, subsídio do cliente ou fonte externa. Origem e tipo documental são atributos distintos.
- Registrar instâncias incluídas, não aplicáveis ou desconhecidas, motivo, autor e data. Escopo desconhecido continua pendência; não declarar automaticamente que o segundo grau inexiste.
- Manter envio complementar como padrão. Substituição de inventário exige ação própria, prévia visível e confirmação explícita.
- Permitir PDF único de autos com índice de peças por intervalo de páginas. Sugerir a divisão por marcadores/conteúdo, permitir revisão e preservar sempre o original e a numeração original. IDs de eventos judiciais desconhecidos permanecem desconhecidos.

### 5.2 Extração e cobertura

Reutilizar OCR, chunks, resumos e checkpoints. Registrar qualidade por página e permitir reprocessar apenas a unidade com defeito. Uma página sem texto pode ser branca ou conter imagem relevante: marcar para conferência; não presumir que é irrelevante. Exceção deve preservar imagem, motivo e revisor, sem transformar um documento ilegível em extração bem-sucedida silenciosa.

O inventário precisa mostrar arquivos/páginas recebidos, processados, falhos e não suportados. Formato não suportado gera orientação, não omissão. Não ampliar formatos além do necessário para o primeiro fluxo antes de fechar PDF e comprovante.

### 5.3 Pacote de evidências por trabalho

Introduzir uma etapa persistida entre contexto documental e redação:

1. Fixar a versão do acervo e as instruções do trabalho.
2. Montar o mapa de peças e a cronologia, com datas extraídas e fontes; divergências e decisões possivelmente superadas exigem conferência.
3. Definir perguntas necessárias à providência a partir de um checklist inicial editável.
4. Buscar no texto original indexado, inclusive trechos que não aparecem nas citações dos resumos. Usar FTS existente, consultas por ponto e páginas vizinhas; permitir fixar fontes manualmente.
5. Recuperar decisão que motivou o trabalho, manifestações relevantes e evidências favoráveis/contrárias. A prioridade proposta pode ser corrigida pelo advogado.
6. Registrar fatos, fonte exata, contradições, informação fornecida pelo cliente e pontos não encontrados.
7. Produzir contexto de redação com mapa do acervo, evidências e limitações; registrar quais trechos efetivamente foram enviados ao modelo.

A consulta de trechos deve ser limitada às versões do manifesto fixado. `atual=true` sozinho não garante que o documento pertence a esse manifesto. Uma consulta ao acervo inteiro do escritório é proibida neste caminho. Página, intervalo, versão e hash devem permitir abrir a fonte original após novas versões ou reprocessamento; não depender apenas de IDs de chunks que possam ser recriados.

Para autos grandes, preservar inventário completo no banco e consultar blocos de texto; manter sínteses hierárquicas com cobertura rastreável. Montar o contexto dentro do orçamento do modelo, incluindo instruções, template, histórico, ferramentas e saída reservada. A redução do prompt deve ficar registrada. Se evidências essenciais não couberem, dividir a análise ou bloquear com ação concreta; nunca cortar silenciosamente a prova.

Busca semântica e reranking entram somente se os casos de avaliação demonstrarem falha de recuperação que FTS, contexto de página e seleção orientada não resolvem. Não abrir um banco vetorial separado nesta primeira entrega.

### 5.4 Revisão e mudança de contexto

Mostrar a minuta ao lado das fontes. Separar checagem determinística de referência existente da avaliação de se a fonte sustenta a afirmação. Uma segunda leitura por IA pode sugerir inconsistências, sem converter a sugestão em certificação jurídica.

Pendências bloqueantes: identidade/parte indefinida, fonte essencial ausente, documento essencial ilegível, destino indefinido para o envio e pacote alterado após aprovação. Alertas informativos não devem impedir consulta e rascunho exploratório; a política de exceção atual deve ser explícita, auditada e nunca liberar envio por conta própria.

Documento novo ou instrução alterada produz nova fotografia de evidências. Preservar a minuta anterior e mostrar “Revisão necessária desde a versão X”. Antes da aprovação/envio, exigir revisão do contexto vigente ou justificativa autorizada dentro da política existente. Nunca atualizar texto ou arquivos de um pacote já aprovado silenciosamente.

## 6. Pacote e protocolo

### 6.1 Entrega útil sem tribunal

Criar pacote versionado com:

- Processo e instância reais, tribunal, sistema quando conhecido, órgão/destino e tipo de ato.
- PDF final da petição, revisão de origem e hash.
- Anexos escolhidos pelo advogado, versão, hash, tipo, ordem e nome de saída.
- Relação com a fotografia de evidências e as instruções revisadas.
- Identidade/data de aprovação e resumo legível do conteúdo aprovado.

Permitir visualização e download de arquivos individuais e ZIP com índice para conferência. O índice interno não vira anexo judicial automaticamente. Cada exportação reutiliza os bytes aprovados. PDF/anexos assinados não devem ser recomprimidos ou modificados silenciosamente. Limites e formatos do destino só são apresentados como conferidos quando houver configuração conhecida para aquela rota.

Edição de texto, timbrado, anexo, ordem, grau, tipo ou destino invalida a aprovação aplicável e produz nova versão. Evoluir `FilingPackage` para representar o conjunto e usar o mesmo contrato na exportação, no futuro fornecedor e no executor. Não reconstruir o pacote a partir de registros mutáveis na hora de enviar.

DOCX é uma melhoria posterior se o editor externo bloquear o piloto. Se houver edição externa, reimportar a versão final e aprovar novamente; o PDF anteriormente aprovado não representa esse novo texto.

### 6.2 Estados operacionais e evidência do envio

Separar estado da tentativa e estado do comprovante, evitando um único booleano “protocolado”.

| Situação operacional | Comportamento |
|---|---|
| Preparando / aguardando aprovação | Montagem e revisão do pacote. |
| Pronto para envio | Pacote aprovado e destino definido; canal explícito. |
| Aguardando envio externo | Advogado exportou e fará o envio. Download não conclui a providência. |
| Em execução / aguardando intervenção | Executor homologado prepara ou solicita login/assinatura. |
| Resultado incerto | Pode ter havido envio; consultar resultado antes de nova tentativa. |
| Envio informado | Declaração do advogado com autor, data e número informado. |
| Envio confirmado | Evidência reconciliada conforme o método registrado, sem esconder se a conferência foi humana ou por integração. |
| Falha confirmada / cancelado | Nova tentativa somente quando seguro; cancelamento não desfaz ato já enviado. |

Estado do comprovante: ausente, recebido, divergente, conferido pelo advogado ou reconciliado por integração. Receber um PDF e extrair um número não prova sozinho sua autenticidade nem vinculação ao pacote.

Receber o arquivo do comprovante no storage privado, guardar hash e versão, extrair/sugerir número CNJ, protocolo, destino e data; pedir conferência quando faltar dado ou houver divergência. Vincular a tentativa e o pacote. Distinguir hora do registro no Causor da hora do ato informada na evidência.

Histórico legado permanece como declaração manual, com comprovante ausente ou referência não verificada conforme seu registro. Não promover registros antigos a confirmados por migração. Fechar prazo/tarefa exige regra explícita e confirmação apropriada; baixar o pacote ou informar um protocolo não deve implicitamente alterar tudo.

### 6.3 Automação futura, preparada agora

Completar contratos de preparo, autorização de envio, tentativa e consulta do resultado nos simuladores. Testar falha antes/depois do envio, troca de destino e sessão expirada. Drivers de produção continuam indisponíveis até homologação por sistema/tribunal/grau/ato.

O primeiro canal real precisa demonstrar: processo e destino corretos, bytes aprovados, intervenção de autenticação/assinatura quando exigida, envio único e comprovante reconciliado. Credencial sozinha não satisfaz o aceite. Não escolher PJe/TJTO/eproc por herança de documentos antigos.

## 7. Modelo de dados e integração incremental

Nomes abaixo são propostos; fechar a migração no início de cada entrega. Reaproveitar tabelas existentes antes de duplicá-las.

| Entidade/contrato | Responsabilidade |
|---|---|
| `TrabalhoJuridico` | Processo/cliente, instância, intimação opcional, providência, instruções, responsável, prazo vinculado e versão. Não substitui a tarefa administrativa. |
| `EscopoAutos` | Declaração de origem/cobertura, instâncias e data de referência; preferir extensão dos manifestos/capturas existentes. |
| `PacoteEvidencias` | Fotografia do acervo, perguntas, fatos, fontes, lacunas, versão da preparação e orçamento utilizado. |
| `PacoteProtocolo` / itens | Arquivos imutáveis, destino, ordem, fingerprint e aprovação. |
| `TentativaProtocolo` | Canal, pacote, chave de idempotência, instalação/identidade autorizada, estado e checkpoints. |
| `ComprovanteProtocolo` | Objeto privado, hash, campos declarados/extraídos, conferência e vínculo à tentativa. |

`ContextoProcesso`, `Peticao`, `JobExecucao`, `AgentCommand`, documentos e auditoria permanecem. Estado da tela deve ser derivado dessas fontes e das transições do trabalho; evitar uma nova cópia independente de cada estado de job.

Rotas indicativas: cadastrar processo; criar/consultar trabalho; preparar evidências; consultar/gerar minuta do trabalho; criar/consultar/aprovar/exportar pacote; informar envio; receber/conferir comprovante. A rota atual de minuta por intimação delega ao mesmo serviço e permanece compatível durante a migração.

Alterações estruturais devem ser aditivas. Registros antigos são associados a trabalhos quando necessário, sem inventar dados ausentes. Manter telas anteriores acessíveis durante a transição e ativar o percurso novo por escritório. Desativar a experiência nova não apaga dados ou aprovações. Migração deve ser validada em PostgreSQL, inclusive com dados legados.

## 8. Entregas executáveis, em ordem

Trabalhar com uma entrega em andamento. Cada item deve produzir comportamento observável, teste apropriado e registro no estado do projeto. Dividir em PRs menores quando necessário, preservando o critério de saída.

| ID / esforço indicativo | Escopo e arquivos principais | Aceite / dependência |
|---|---|---|
| E0 — 0,5–1 dia | Contrato de estados, capacidades e mensagens; `ProtocolarModal`, `access_channel`, telas de integração. Montar caso demonstrativo identificado como sintético. | Sem integração: oferecer upload/exportação, sem encaminhar instalação inútil. Modal não promete envio inexistente. Independe de acesso. |
| E1 — 2–3 dias | Cadastro manual + `TrabalhoJuridico`, migração, API e percurso mínimo em Processos/DetailDrawer. | Criar processo/trabalho sem DJEN, enviar arquivos e retomar trabalho após recarregar; isolamento e deduplicação. Depende de E0 para navegação. |
| E2 — 2–3 dias | Escopo dos autos e diagnóstico por documento/página; `autos/context`, extraction, upload e painel documental. Índice manual de peças em PDF único; sugestões automáticas podem seguir depois. | Escopo desconhecido visível; documento ausente/ilegível não desaparece; reprocessamento preserva fontes históricas. Depende de E1. |
| E3 — 3–4 dias | `PacoteEvidencias`, recuperação no texto original por versão, cobertura por ponto e preparação da minuta; context_selection, chunks, service/drafter. | Fato decisivo ausente do resumo chega ao redator pela fonte original; prova contrária aparece; orçamento não causa corte invisível. Depende de E2. |
| E4 — 2–3 dias | Revisão integrada, fontes fixadas, pendências e contexto alterado; MinutaEditor, DocumentEvidenceDialog, tarefas e serviço de aprovação. | Usuário abre a fonte correta sem perder edição; novo documento exige revisar o contexto; lacuna vira tarefa vinculada. Depende de E3. |
| E5 — 3–4 dias | Pacote com anexos, destino/grau reais, aprovação por versão, ZIP/arquivos; filing/approval, package, contracts, storage, API e UI. | Bytes exportados iguais aos aprovados; mudança de qualquer item relevante exige nova aprovação. Depende de E4. |
| E6 — 2–3 dias | Tentativa, envio externo, upload/conferência de comprovante e migração do registro manual; queue/jobs, ProtocolosView e modelos. | Percurso assistido completo, origem e método de conferência visíveis; divergência não conclui envio; histórico antigo preservado. Depende de E5. |
| E7 — 1–2 dias | Ferramentas documentais do assistente e contexto do trabalho; chat_tools, assistant e AssistantWorkspace. | Chat consulta as mesmas fontes/estados e abre a mesma ação que a tela; sem mutações arbitrárias ou falsa confirmação. Depende de E3/E6. |
| E8 — 2–3 dias | Destinação/capacidades do executor, autorização, checkpoints e resultado incerto; agent_runtime, local_agent, contratos e simuladores. | Dois computadores não trocam identidade; perda de posse impede avanço; timeout após envio não repete ato. Depende de E5/E6. |
| E9 — 1–2 dias | Fluxo completo no navegador, alertas operacionais, instrumentação, runbook e demonstração. | Fluxo reproduzível sem banco manual; evidência visual e relatório dos cenários. Depende de E1–E7; E8 pode concluir depois do piloto assistido. |

Total indicativo: **19–28 dias de desenvolvimento**, além de homologação externa e tempo do revisor. Não tentar entregar tudo antes de mostrar resultado. E0/E1 já melhoram a experiência; E3/E4 atacam a dor de contexto; E5/E6 fecham o protocolo assistido.

Meta de execução: contexto e revisão como primeiro marco; pacote e envio externo como segundo; executor como terceiro. Se uma entrega exceder a janela, reduzir conveniências (sugestão automática de índice, DOCX, instalador) preservando integridade, revisão e retomada.

## 9. Plano de trabalho para começar hoje

1. Registrar o baseline e criar branch de implementação sem alterar a produção. Preservar alterações alheias; verificar instruções do repositório.
2. Executar E0: alinhar rótulos/capacidades com a rota assistida e retirar a promessa de conclusão automática do modal. Demonstrar o próximo passo de quem não tem integração.
3. Especificar e testar primeiro o cadastro manual e trabalho com intimação opcional, sem prazo inventado. Implementar E1 sobre os serviços existentes, sem gerar registros de captura fictícios.
4. Montar dois casos sintéticos: um curto e um em PDF único com várias peças. Marcar ambos como demonstração e usar tenant próprio. Não inventar “resultado jurídico validado”.
5. Conferir o percurso no navegador: abrir caso, enviar documentos, ver estado e retomar. Registrar defeitos observados e seguir para E2.

O primeiro commit de implementação deve ser pequeno e verificável. Não começar pela substituição do modelo, instalação do executor ou tentativa de conectar tribunal sem acesso.

## 10. Validação sem acesso judicial

Usar testes de domínio/API/integração para falhas com impacto em documentos, aprovação, isolamento e envio. Não criar testes que apenas espelham textos estáticos. Validar experiência no navegador, incluindo fonte citada, edição, recarga e mensagens de erro.

| Cenário | Resultado obrigatório |
|---|---|
| Cadastro sem DJEN e sem segundo grau conhecido | Trabalho criado, escopo pendente explícito, nenhum prazo/intimação fabricado. |
| Mesmo arquivo reenviado / mesmo nome com bytes diferentes | Reuso ou nova versão conforme conteúdo; nenhuma sobrescrita do histórico. |
| Documento removido do manifesto mas ainda marcado atual | Busca da fotografia não recupera a versão excluída desse escopo. |
| PDF único com peças, OCR ruim e página sem texto | Intervalos apontam para páginas originais; problemas exigem conferência. |
| Fato essencial não incluído no resumo | Busca nos trechos originais recupera a evidência correta. |
| Decisão posterior modifica anterior / prova contrária | Contradição ou sucessão aparece para revisão com ambas as fontes. |
| Evidência essencial no fim de autos longos | Recuperação e orçamento preservam o ponto; limite insuficiente produz bloqueio visível. |
| Novo upload durante geração | Resultado mantém fotografia original e é marcado desatualizado; não ganha aprovação automática. |
| Reprocessamento após citação | Minuta histórica ainda abre texto/versão/página usados, ou preserva artefato verificável equivalente. |
| Documento contém instruções para o agente | Tratado como dado da fonte; não altera permissões, ferramentas ou aprovação. |
| Outro escritório tenta consultar fonte/pacote | Acesso recusado em API, storage e ferramentas do assistente. |
| Alteração de anexo, grau ou destino após aprovação | Envio/exportação aprovada rejeita versão divergente; usuário revisa pacote novo. |
| Dois cliques / dois workers no mesmo envio | Uma tentativa autorizada; unicidade testada no PostgreSQL. |
| Queda antes e depois do envio simulado | Antes: retomada segura. Depois: resultado incerto e reconciliação, sem reenvio cego. |
| Comprovante de outro processo ou sem campos legíveis | Divergência/pendência explícita; nunca confirmação automática. |
| Registro antigo sem recibo | Continua declaração manual; não vira comprovante confirmado. |

Testes de integração devem usar Postgres para FTS, concorrência, migrações e claims; SQLite não substitui essa validação. Simuladores comprovam contratos internos, não comportamento de portal real.

Para avaliar o modelo, separar casos de ajuste e casos reservados e fixar documentos por data. Registrar entrada, versão de prompt/modelo, custo, latência, fontes recuperadas, erros e edição necessária. Primeiro estabilizar a seleção de contexto com modelo fixo; comparar modelos depois. Chamada real de IA e avaliação jurídica são etapas distintas de testes com provedores simulados.

## 11. Critérios de liberação e receita

### Marco A — demonstração funcional interna

E0–E4: casos sintéticos percorrem entrada, documentos, evidências e minuta; fontes e pendências são conferíveis; não há ajustes manuais no banco. Demonstração claramente rotulada e sem alegar qualidade jurídica comprovada.

### Marco B — piloto assistido vendável

E5/E6/E9: pacote aprovado exportável, envio externo acompanhado, comprovante recebido/conferido, convite/login e operação recuperável. Realizar os cinco casos autorizados com o advogado disponível quando os documentos chegarem, sem atrasar a construção interna por isso.

Hipóteses comerciais de aceite: redução de 30% do tempo ativo total e 80% de aproveitamento com ajustes localizados, dentro do recorte escolhido. Qualquer erro material bloqueia promoção da versão até investigação. Amostra pequena orienta correção; não sustenta promessa de precisão geral. Medir também custo e minutos do fundador por trabalho concluído.

Antes de clientes pagantes, verificar restauração de backup de banco/artefatos, captura/alertas efetivos e procedimento de recuperação. Reusar infraestrutura já entregue. Não basta `/health` responder se os workers ou a captura estiverem parados.

Venda inicial: piloto com escopo/volume definidos e onboarding acompanhado; cobrança simples por ferramenta existente. Oferta descreve preparação e revisão com protocolo assistido externo. Não esperar checkout próprio, todos os módulos ou automação judicial universal.

### Marco C — primeiro canal judicial automático

Requer acesso autorizado, rota exata, assinatura quando aplicável e testes reais supervisionados. Só ativar para o escopo homologado, por escritório. Não entra no prazo de 19–28 dias por depender de recurso externo ainda indisponível.

Métricas semanais: trabalhos iniciados/concluídos; tempo até primeira minuta; tempo ativo até pacote aceitável; falhas de contexto; afirmações sem apoio apontadas pelo revisor; custo por trabalho aceito; intervenções do fundador; pilotos pagos e renovações. Não usar quantidade de minutas geradas como medida única de valor.

## 12. Escopo posterior e manutenção do plano

Após Marco B, priorizar pela dor medida: compra de autos se baixar documentos dominar o tempo; primeiro canal de envio se montagem/protocolo dominar; qualidade de evidências se houver reescrita. A visão de escritório integrado permanece, com agenda, atendimento, honorários e portal em etapas posteriores.

Fora da sequência imediata: quatro conectores ao mesmo tempo, agente genérico controlando todo o computador, browser de tribunal no servidor, infraestrutura nova de orquestração, fine-tuning, migração de banco, CRM/financeiro completos e billing complexo.

Ao concluir cada entrega, atualizar `docs/estado.md` com comportamento entregue, teste realizado, limitações e próxima ação. Este plano não constitui evidência de execução; nenhum item deve ser marcado concluído só por estar descrito aqui.
