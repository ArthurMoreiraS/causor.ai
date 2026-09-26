# Trabalho jurídico, evidências e protocolo assistido — 21/09/2026

Implementação local do [plano de contexto e protocolo](plano-contexto-protocolo-2026-09-20.md), somente no `causor-software`. Não houve push, deploy, alteração do banco de produção, contratação de fornecedor ou protocolo judicial. Alterações de interface existentes no workspace foram preservadas.

## Comportamento entregue

1. **Entrada independente de tribunal.** Em Preparar trabalho, cadastrar processo/cliente ou escolher um processo existente, informar providência, instruções, polo e grau. O número CNJ é normalizado e validado quanto ao formato; isto não verifica existência no tribunal nem dígito verificador. Intimação e prazo são opcionais. O trabalho pode ser retomado pelo link `/?trabalho=ID#trabalhos`.
2. **Contexto conferível.** Upload complementar, declaração de origem/data/limitações e índice manual de peças por página. Extração registra diagnóstico de cada página. Falhas preservam as páginas extraídas e a retomada executa OCR apenas nas pendentes. Arquivo ilegível continua bloqueado; nenhuma página é descartada como irrelevante. A ausência de instância exige declaração explícita; desconhecimento não equivale à ausência.
3. **Preparação e revisão.** Evidências são recuperadas no texto original, usando FTS PostgreSQL, páginas vizinhas e fontes fixadas. A consulta fica restrita às versões do inventário. O sistema persiste perguntas, trechos enviados, hashes, análise proposta, lacunas, duração e conferência humana. Fontes podem ser abertas no PDF original. Lacunas viram tarefas vinculadas, com deduplicação. Documento ou objetivo alterado exige nova conferência; a minuta anterior permanece preservada. O contexto excedente gera seleção registrada ou bloqueio explícito, sem truncamento invisível.
4. **Pacote e resultado do envio.** Pacote versionado com PDF, anexos ordenados, hashes e destino. Anexos são copiados para o arquivo de protocolo, independentemente da biblioteca mutável. Edição invalida a aprovação, inclusive se o texto for revertido. ZIP usa os bytes conferidos e inclui índice identificado como interno. Download não cria protocolo. Tentativa externa, declaração de envio, recebimento de PDF e conferência humana são estados diferentes. Comprovante divergente não confirma; declaração sem comprovante não marca a minuta como protocolada. Prazo e tarefa não são encerrados automaticamente. Protocolos exibe os envios assistidos e preserva o histórico anterior com seu método original.
5. **Assistente e executor.** O assistente consulta as fontes e o estado do trabalho com escopo de escritório/processo, sem executar mutações. O fluxo inteiro funciona por botões. O executor 0.2.0 declara capacidades; comandos respeitam usuário, instalação de destino e posse vigente. Operações de envio exigem handler com checagem entre etapas. Há checkpoint persistido antes do envio e resultado incerto em falha posterior; o worker não repete o ato. Simuladores verificam destino/bytes, perda de posse e timeout após envio. Handlers judiciais reais de leitura/protocolo continuam indisponíveis.

## Operação do piloto assistido

- Fazer backup e aplicar as migrações aditivas até `b0d6e2f8a4c7` antes de disponibilizar o código. Frontend, API e worker de autos devem usar a mesma revisão. A execução local não aplicou essas migrações em produção.
- Configurar storage privado e os provedores já utilizados pelo projeto. Manter o worker de autos em execução. O executor local não é pré-requisito para o piloto assistido.
- Começar com processos e documentos autorizados pelo escritório. Cadastrar cliente/polo e escopo, conferir instâncias, preparar evidências e abrir cada fonte relevante. A análise da IA é proposta, não certificação jurídica.
- Revisar a minuta; montar e conferir destino, grau e arquivos; aprovar a versão; exportar; abrir uma tentativa de envio externo. O advogado envia pelo canal ao qual já tem acesso.
- Informar número e hora do ato, anexar comprovante e conferir visualmente correspondência com processo, destino e arquivos aprovados. Divergência exige o documento correto. Não cancelar uma tentativa após informar envio: cancelar acompanhamento não desfaz ato judicial.
- Se a análise/redação falhar, as fontes e a minuta anterior permanecem. A mensagem permite retentar; alterações concorrentes rejeitam o resultado antigo. Se um documento falhar, consultar páginas no escopo e usar Retomar processamento com falha. Não contornar ausência de fonte essencial com uma declaração genérica.
- Se houver resultado incerto em futura integração, consultar o resultado no destino e reconciliar antes de uma nova tentativa. O fluxo externo atual não tenta executar no tribunal.

## Verificação reproduzível sem serviços judiciais

Testes de API usam provedores simulados e storage local; não avaliam a qualidade jurídica de um modelo real. A suíte PostgreSQL usa apenas `localhost/causor_test`, em schemas descartáveis, nunca o URL do banco da aplicação. Valida migrações, FKs, busca FTS, concorrência e preservação de dados legados. A coluna `extraction_pages` é nullable para os arquivos legados; o diagnóstico aparece nos novos processamentos.

Para demonstração visual isolada:

1. No backend: `.venv/Scripts/python.exe -m tests.work_demo_server`. O script cria tenant, banco SQLite e objetos novos em `backend/artifacts/work-demo-*`, substitui os provedores por respostas sintéticas e escuta somente `127.0.0.1:8099`.
2. No frontend, definir `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8099`, `NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321` e `NEXT_PUBLIC_SUPABASE_ANON_KEY=synthetic-local-browser-test`; executar `pnpm dev --hostname 127.0.0.1 --port 3099`. Não gravar esses valores na configuração de produção.
3. No backend: `.venv/Scripts/python.exe -m tests.work_browser_smoke`. Requer navegador Playwright instalado; alternativamente, `CAUSOR_TEST_BROWSER_EXECUTABLE` pode indicar um Chromium local. A autenticação é sintética somente no script de teste; nenhum bypass foi acrescentado ao produto.
4. O teste cria processo pela UI, recebe PDF, declara escopo, identifica peça, gera pendência, confere evidências, abre minuta, aprova/exporta pacote, rejeita comprovante divergente, confere o correto e recarrega em largura móvel. PDF e recibo possuem marca de demonstração sem efeito judicial. Screenshots/ZIP ficam em `backend/artifacts/work-browser`, ignorados pelo Git.
5. Encerrar os servidores locais após o teste. Nunca usar os arquivos de demonstração em tribunal.

## Limites e próximo uso real

O aceite técnico não comprova integralidade dos autos do tribunal nem qualidade jurídica do modelo real. Sugestão automática de divisão de peças, DOCX, busca vetorial e instalador final não fazem parte desta entrega. Documentos muito grandes podem exigir preparação dividida quando inventário/resumos/fontes essenciais ultrapassam o orçamento do modelo; o sistema informa o bloqueio.

Antes de cobrar por operação judicial automatizada, é necessário implementar e homologar uma rota concreta com credencial autorizada e evidência de envio único/comprovante. O percurso entregue permite testar valor e cobrança por preparação/revisão assistida com advogados, sem prometer protocolo automático. Selecionar os primeiros casos, medir tempo até minuta revisada, correções de fontes, lacunas recuperadas e taxa de conclusão do pacote. Registrar custos reais retornados pelo provedor; duração/bytes não equivalem a custo financeiro.

Na implantação, acompanhar falhas de processamento, trabalhos com contexto desatualizado e tentativas sem comprovante. As trilhas `evidencias_preparadas`, `evidencias_conferidas`, `pacote_aprovado`, `pacote_exportado`, `envio_informado` e `comprovante_conferido` permitem reconstruir a sequência sem presumir sucesso judicial.
