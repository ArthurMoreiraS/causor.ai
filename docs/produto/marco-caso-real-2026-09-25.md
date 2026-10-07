# Próximo marco: um caso real, contexto e minuta revisada

Decisão de 25/09/2026, após a reunião de 22/09 com o advisor jurídico. O briefing
e a transcrição estão em `Causor_AI_Briefing_Reuniao_22-09-2026.docx` e
`backend/reuniaoComAdvisorRaw.md`. O briefing sintetiza encaminhamentos; a fala
dos participantes não deve ser confundida com prova de qualidade do produto.

## Situação

O percurso por upload, escopo, evidências, minuta e revisão está implantado e
foi exercido com dados fictícios. A interface informativa anterior foi
restaurada. Falta o caso real; o estado atualizado está em
[`../estado.md`](../estado.md).

## Caminho único

Validar **um trabalho jurídico concreto** antes de ampliar interface, modelos ou
conectores. A apelação descrita na reunião é a primeira hipótese; o advogado
pode escolher outra providência recorrente se tiver um caso autorizado e mais
adequado. A entrada é upload manual do inteiro teor disponível na data do ato.
O resultado buscado é uma minuta aproveitável, com fontes conferíveis e tempo
ativo menor que o fluxo habitual. Protocolar a peça fica
fora desta medição; envio automático não integra o aceite.

1. O advisor fornece um processo encerrado ou autorizado, PDFs disponíveis na
   data de referência, objetivo, parte representada e uma peça final anterior
   guardada apenas para comparação. Registrar tribunal, sistema e instâncias,
   sem supor que um login eProc cubra outra jurisdição. Não guardar autos reais
   no Git nem no banco de demonstração.
2. Enviar os autos pela aplicação em produção, onde API e worker de documentos
   compartilham o mesmo armazenamento. O backend local grava só no disco da
   máquina. Não exportar backups com dados de conta para a pasta sincronizada
   do projeto.
3. No Causor, cadastrar trabalho sem intimação fictícia, anexar os PDFs, declarar
   origem e cobertura, conferir páginas falhas, indexar as peças relevantes e
   preparar evidências. O advogado verifica inicial, defesa, decisão atacada,
   manifestações posteriores e provas contrárias conforme o caso. Documento
   ausente ou ilegível vira pendência explícita.
4. Gerar uma primeira minuta com o modelo atual e registrar versão dos arquivos,
   instruções, fontes recuperadas, alertas, duração e intervenção manual. O
   advogado revisa fontes e texto antes de ver a peça de referência. Não trocar
   modelo nem completar o acervo no meio desta medição.
5. O advogado registra tempo ativo de leitura, correção e revisão; identifica
   fatos omitidos/inventados, afirmações sem apoio, problemas jurídicos, estrutura
   e adequação ao estilo do escritório. Classificar cada falha como falta de
   documento, extração, recuperação, interpretação ou redação. Corrigir a primeira
   causa material antes de começar outra frente.

## Ficha de resultado por caso

Guardar a ficha junto aos autos no ambiente autorizado, com código anônimo:

| Campo | Registro |
| --- | --- |
| Código, providência e data de referência | Identificam o recorte sem dados pessoais no relatório. |
| Arquivos e páginas recebidos/processados/falhos | Separam integridade do upload da cobertura do processo. |
| Peças essenciais presentes/ausentes | Declaração revisada pelo advogado, não prova automática de completude judicial. |
| Tempo habitual e tempo ativo com Causor | Distinguir medida de estimativa; incluir correções e conferência. |
| Aproveitamento | Utilizável com ajustes localizados, reescrita ampla ou inutilizável. |
| Erros materiais e fontes | Página/versão da prova e consequência jurídica. |
| Intervenções e custo | Minutos do fundador, tentativas e custo real do provedor quando disponível. |
| Próxima correção | Uma causa observada, responsável e novo critério de verificação. |

Aceite desta rodada: o advogado consegue reconstruir o caso pelas fontes, aponta
se a minuta é aproveitável e explica os erros; tempo e intervenções ficam
registrados. Um caso não demonstra precisão geral. Depois, repetir em cinco
casos autorizados, com revisão cega quando houver comparação de modelos com
entradas idênticas. Redução de 30% no
tempo e 80% de aproveitamento continuam hipóteses, não resultados.

Protocolo automático, compra de API de autos, jurisprudência integrada e novas
telas entram na decisão seguinte, conforme o gargalo medido. O acesso eProc
mencionado na reunião ainda não foi entregue; não há rota judicial homologada.
