# Direção do Causor após a reunião jurídica

Plano de produto e execução de 25/09/2026. Fontes: o briefing
`Causor_AI_Briefing_Reuniao_22-09-2026.docx`, a transcrição
`backend/reuniaoComAdvisorRaw.md`, o estado técnico em `docs/estado.md` e o
[marco de avaliação de um caso real](marco-caso-real-2026-09-25.md). O briefing
organiza a conversa; suas prioridades são encaminhamentos, não resultados já
medidos com advogados.

## Decisão para a empresa

O primeiro produto a provar é a **preparação de trabalho jurídico com contexto
conferível** para escritórios pequenos e médios. A entrada pode ser uma intimação
capturada pela OAB ou uma demanda cadastrada pelo escritório. O Causor deve
associar cliente e processo, apresentar o prazo com base e incertezas, reunir
autos e documentos do cliente, mostrar lacunas e produzir uma primeira peça
aproveitável, com fontes que o advogado consiga abrir. A revisão humana encerra
o marco inicial. Tempo economizado e erros materiais serão medidos em um caso
real antes de prometer desempenho geral.

Essa ordem segue a fala do advisor: há valor mesmo sem protocolo automático se
a minuta reduzir trabalho e for boa. Protocolo permanece uma possibilidade de
evolução, sem dominar a navegação, a mensagem comercial nem a implementação
imediata. PJe, eProc, e-SAJ e outros sistemas são **fontes ou destinos de um
tribunal e instância específicos**; nenhum deles representa sozinho o Judiciário.
O acesso mencionado à eProc na reunião ainda não foi entregue ou validado.

## Fluxo principal do produto

| Etapa | O que a pessoa precisa ver e decidir | Fonte e limite atual |
| --- | --- | --- |
| 1. Entrada | Capturar publicações da OAB, localizar a intimação e vinculá-la ao processo e ao cliente; também poder iniciar um trabalho manual. | DJEN/Comunica é fonte de publicações. Captura por OAB não prova cobertura de comunicações pessoais nem da carteira inteira. |
| 2. Prazo | Ver evento de origem, regra e calendário aplicados, data calculada e estado de revisão. | Motor determinístico; casos ambíguos ficam para confirmação humana, sem vencimento inventado. |
| 3. Contexto | Receber autos e documentos do cliente, declarar origem/data/cobertura, identificar peças e páginas ilegíveis ou ausentes. | Upload manual funciona como primeira rota. DataJud fornece metadados, não o inteiro teor. Captura automática dos autos é meta posterior e precisa provar cobertura por tribunal/processo. |
| 4. Trabalho | Registrar providência, parte representada, instância, instruções e perguntas; buscar fatos, argumentos e decisões nos originais. | Clientes, documentos, trabalhos, escopo e evidências já existem no checkout local; devem permanecer ligados. |
| 5. Peça | Gerar minuta e dossiê de apoio com versão dos documentos, citações de página, lacunas e afirmações a conferir. | Qualidade jurídica ainda não foi medida em autos reais; o advogado revisa texto e fontes. |
| 6. Revisão | Salvar mudanças, criar pendências e submeter a peça a revisão/liberação humana. | A aprovação não confirma envio judicial. Protocolo e recibo são registros separados e secundários neste ciclo. |

## Ordem de execução

1. **Restaurar a interface informativa anterior.** Voltar à navegação por
   Trabalho diário, Escritório, Produção jurídica e Administração; manter Visão
   geral com indicadores, ciclo, fila, agenda e saúde operacional visíveis.
   Preservar rotas e dados de Clientes, Documentos e Trabalhos; adicionar
   Trabalhos como destino explícito em Produção jurídica. Remover o painel
   resumido “Hoje”, o tema verde e a navegação condensada rejeitados pelo
   fundador. Os indicadores devem explicitar quando a fonte estiver incompleta
   ou indisponível.
2. **Reordenar o produto em torno da captura e do contexto.** Intimações,
   Processos e Prazos continuam destinos próprios. Nas telas e textos, usar
   “sistema do tribunal” quando o sistema ainda não foi identificado. PJe só
   aparece quando o caso, conector ou instância realmente é PJe. A revisão
   humana permanece no fluxo; ações de envio judicial e acesso automático aos
   autos ficam fora da navegação do MVP até homologação da rota concreta.
   A ação principal de uma intimação abre um trabalho com origem e prazo
   vinculados; o advogado define a providência antes de redigir.
3. **Fechar o caminho manual do caso benchmark.** Associar cliente, processo,
   trabalho e documentos; conferir origem, inventário, OCR, lacunas, citações,
   minuta e revisão sem fabricar uma intimação. Usar a ficha do
   [caso real](marco-caso-real-2026-09-25.md) para medir tempo e qualidade.
   Antes de subir autos reais ao banco compartilhado, resolver o armazenamento
   privado acessível à API e ao worker na mesma revisão; hoje o `localdev`
   grava somente no computador.
4. **Avaliar captura automática dos autos depois do benchmark manual.** Para o
   mesmo caso e tribunal, comparar documento por documento uma rota contratada
   ou autorizada com o inventário manual. Registrar cobertura, faltas, custo,
   atraso e intervenção. Só então decidir integrar fornecedor ou desenvolver
   conector próprio. Manter upload para complementos e provas externas.
5. **Protocolo em trilha posterior.** Não expandir automação por sistema ou
   jurisdição antes de a minuta demonstrar valor. Quando retomado, exigir
   tribunal/instância/ato confirmados, aprovação humana, tentativa idempotente
   e comprovante verificado. Não apresentar “PJe assistido” como capacidade
   universal nem “operação estável” apenas por ausência de dados.

## Verificação do próximo marco

- A tela inicial restaurada mostra os módulos e indicadores anteriores, com
  Captura por OAB, Intimações, Processos, Prazos, Clientes, Documentos e
  Trabalhos alcançáveis sem perder as URLs existentes.
- Um teste de navegador percorre entrada manual, documentos, escopo,
  evidências, minuta e retorno ao trabalho; lint, tipos, testes e build passam.
- O Assistente Causor responde sobre processos, intimações e prazos e pode abrir
  um trabalho. Ele não oferece geração direta de minuta, aprovação ou baixa de
  prazo fora da conferência do contexto e das fontes.
- A captura por OAB e o prazo são demonstrados separadamente: publicação
  capturada não equivale a autos completos, e prazo incerto exige revisão.
- No caso autorizado, o advogado consegue explicar a peça pelas fontes e
  registrar fatos omitidos ou inventados, correções e tempo ativo. Um caso
  fornece diagnóstico, não taxa geral de acerto. Repetir em cinco casos depois
  de corrigir a primeira causa material observada.

Nenhum acesso judicial, qualidade de minuta real ou cobertura automática de
autos está homologado apenas porque o fluxo sintético passa. As afirmações de
valor para clientes serão proporcionais ao que essa avaliação demonstrar.
