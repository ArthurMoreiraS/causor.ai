# Automação dos prazos e preparação da minuta

Direção reforçada pelo fundador em 01/10: menos trabalho operacional para o
advogado. Captura de OAB → intimações/processos → cálculo automático → preparação
de minuta com a intimação pontual e o acervo do processo. Autos enviados pelo
advogado são a entrada imediata; coleta automática continua como meta a validar.

## Diagnóstico atual

A captura já enfileira análise de prazos. O classificador só aceita duração
literal em dias no texto; regra legal sem duração repetida fica pendente. O
calendário considera feriados nacionais e recesso cível, sem homologação local.
Não marcar esse resultado como conferido só para remover a revisão da tela.
O backfill frontend já avança até vinte páginas automaticamente, mas transporte
e retomada ainda dependem da tela e de cursor local. Conferir antes de atribuir
todo o problema a um clique por lote.

## Bloco A: interpretação por regra identificável

Após liberar a etapa de UI/contexto, implementar catálogo
pequeno de regras CPC com fonte primária e versão, preservando prazo judicial
expresso e sem prazo padrão. O modelo identifica o ato e cita trecho literal;
o código valida regra/artigo, comando, duração e condições, e calcula a data.
Não aceitar simples sugestão do modelo como norma jurídica.

Primeiro recorte: comandos de contrarrazões de apelação (CPC 1.010 §1º),
manifestação do embargado (1.023 §2º), manifestação sobre documento novo
(437 §1º). Exigir ato e referência normativa verificáveis no teor. Sem esse
vínculo, conservar exceção explicada; não inferir 15 dias de qualquer despacho,
nem 5 dias genericamente a partir do art. 218. Bloquear regime especial,
termo pessoal, múltiplas contagens, duração conflitante e prazo em dobro não
resolvido. Prazo do juiz ou prorrogação identificada têm precedência.

Fonte conferida em 01/10:
[CPC no Planalto](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm).
O §2º do art. 437 admite dilação; não ignorar uma ordem específica no teor.
Calendário local exige tribunal/comarca/grau e suspensões aplicáveis; o
[portal do TJSP](https://www.tjsp.jus.br/CanaisComunicacao/Feriados/ExpedienteForense)
diferencia expediente, segundo grau e processos físicos. Consulta isolada não
certifica todas as exceções. Guardar a limitação no resultado até validá-las.

Arquivos permitidos: agent/deadline_interpretation.py, prazo_engine/pipeline.py
e novo catálogo de regras, testes unitários/integrados/PG correspondentes.
Frontend de prazo e backfill somente no bloco seguinte. Sem testes no banco
real, sem LLM real, sem alterar prazos humanos ou reprocessar lote de produção.

Aceites: duração judicial continua funcionando; regra com ato/artigo correto
calcula sem input humano; artigo solto/ato errado/conflito/regime especial/
prazo em dobro ficam pendentes com motivo; memória guarda origem da duração,
regra, versão, trecho, fonte normativa e calendários usados. Repetição não
duplica; confirmação humana nunca é substituída. TDD antes de regra nova,
Ruff e suíte hermética; PostgreSQL descartável no CI.

Bloco A implementado/revisado localmente em 01/10. Catálogo estreito reconhece
somente formas verificáveis do comando e citação; qualquer duração textual
impede o caminho legal e exige a interpretação judicial expressa. Metadados
oficiais de órgão/classe especial impedem cálculo mesmo se o modelo declarar
CPC com alta confiança. Executor: 753 testes completos/82 ignorados antes das
guardas finais, 21 direcionados finais e Ruff aprovados. Coordenador leu o
diff, inclusive catálogo novo, e repetiu 27 testes aprovados. Sem teste real de
modelo ou caso jurídico; confirmação humana e idempotência preservadas no
teste integrado. Não houve reprocessamento de registros de produção.

## Bloco B: percurso automático e informação clara

Fila persistente para recuperar histórico autorizado sem depender de a tela
ficar aberta. Mostrar separados cálculo em andamento, prazo calculado e
exceção com dado faltante. Evitar chamar toda comunicação sem prazo de erro.
Revisão não pode exigir redigitar parâmetros já extraídos. Documentar como o
calendário local será incorporado antes de reduzir esse último gate.

Preparar minuta abre preparação única, reaproveita processo/intimação/prazo,
e reúne o comando atual, histórico e fontes dos autos. Trabalho é o estado
persistido dessa preparação; minuta é seu documento resultante. A etapa de
geração recuperável permanece no plano contexto-manual-e-minuta. Não gerar
uma peça incompleta silenciosamente para aparentar automação.

## Validação e limite

Pesquisa técnica preliminar de 01/10 para automatizar autos: o Escavador
documenta solicitação assíncrona, status/callback, inventário de autos e download.
O acesso restrito por A1 exige advogado cadastrado no tribunal e certificado
configurado no fornecedor; documentos públicos são uma modalidade distinta.
Ver [contrato de atualização](https://api.escavador.com/v2/docs/atualizacao-de-processos)
e [acesso com certificado](https://suporte-api.escavador.com/hc/pt-br/articles/30114576118555-Acessando-os-Autos-de-Processos-via-API-v2-com-Certificado-Digital).
A Judit também [descreve anexos por CNJ e transferência de arquivos](https://judit.io/blog/apis-dados-juridicos-integracoes/download-automatico-anexos-processos-judiciais/),
com credenciais para segredo de justiça; sua documentação técnica detalhada
não abriu nesta consulta. Nenhum fornecedor foi contratado ou integrado.

Próximo teste de canal: um processo autorizado do tribunal alvo, inventário
manual de referência por grau, conta/chave configurada fora de prompts,
solicitação sem recorte de documentos iniciais, download de cada arquivo e
comparação de faltas/duplicatas/versões/páginas. Reaproveitar ingestão,
extração e contexto existentes; manter uma decisão de roteamento em
`resolve_capture_fonte` e o contrato `CourtReaderDriver`. Não declarar
integralidade pelo status de sucesso do fornecedor, nem exibir captura
automática como disponível antes desse teste. Bucket privado compartilhado
continua necessário para os bytes entre local e produção.

Testes sintéticos verificam os contratos e a matemática das regras suportadas.
O advogado ainda precisa avaliar um conjunto autorizado de casos reais para
medir cobertura e qualidade jurídica. Importação automática de autos exige
credenciais/canal disponível e comparação com o inventário real; não anunciar
que DataJud/DJEN fornecem os PDFs integrais.
