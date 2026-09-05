# Primeiro piloto: cinco casos revisados por advogado

O fundador confirmou um advogado disponível para revisar exemplos. Ainda não
há acesso do Causor a tribunal. Isso permite iniciar a avaliação das minutas
por upload; a homologação do protocolo continua dependendo de acesso real.

**Resultado desta rodada:** descobrir por que uma minuta exige retrabalho e
medir o tempo até ela ficar utilizável. Cinco casos não bastam para afirmar
qualidade geral ou liberar envio automático.

## Como as duas dores serão resolvidas

| Dor | Caminho escolhido | Situação e próximo aceite |
|---|---|---|
| Minuta sem contexto dos autos | Inventário de documentos → extração por página → resumos citados → evidências relevantes para a providência → redação → revisão com fontes | Upload, trechos, resumos, seleção lexical e fontes já estão ligados. Falta demonstrar cobertura dos fatos materiais e qualidade com o advogado. |
| Informação importante ausente | Confrontar o que a providência exige com autos e documentos do cliente; listar lacuna, consequência e documento necessário | Próxima melhoria de produto após classificar os erros dos cinco casos. Documento não enviado não pode virar fato presumido. |
| Protocolo fragmentado | Pacote aprovado e exportado → envio assistido → recibo → um canal automatizado homologado | Há PDF aprovado por hash e registro manual identificado. Faltam pacote completo com anexos/destino, canal real e reconciliação do recibo. |
| Fluxo difícil de operar | Uma sequência com estado, responsável, pendência e próxima ação; processamento retomável | A integração inicial e os checkpoints reduzem correções manuais no banco. O advogado precisa provar que consegue completar o percurso. |
| Formatação e montagem | Padrão do escritório aplicado ao PDF e anexos, conferência visual e nomenclatura consistente | Priorizar os defeitos que atrapalharem os cinco casos; DOCX entra se o editor do advogado for um bloqueio observado. |

A pesquisa orienta construir no Causor a preparação de evidências e a revisão,
e comparar soluções prontas para obter autos e executar atos. A ENTER descreve
uma combinação de autos, subsídios e dados internos para apoiar a elaboração
de textos; isso reforça que os documentos do cliente também importam.
[Fonte primária, conferida em 05/09](https://www.getenter.ai/).

Para integrações, avaliar uma API de dados como a
[Judit](https://docs.judit.io/introduction/introduction) e a oferta de operações
da [Task.doc9](https://doc9.com.br/task/) contra o custo de manter um conector
próprio. Não houve contratação, validação comercial ou confirmação de API de
revenda da Task.doc9. Escolher pelo primeiro tribunal e ato reais; não presumir
cobertura universal nem acesso privado a MNI.

## Material a separar com o advogado

Escolher uma família recorrente de providências a partir dos últimos cinco
trabalhos. Preferir casos encerrados ou históricos autorizados, com a fotografia
dos documentos disponíveis na data da intimação. Se ainda não houver cinco
casos dessa família, registrar a diversidade e tratar a rodada como descoberta.

Por caso, usar um código como C001 e guardar em ambiente autorizado:

- Intimação, data de referência, parte representada e objetivo do cliente.
- PDFs disponíveis naquele momento, com indicação do que pode estar faltando;
  documentos do cliente relevantes ao ato, separados das peças judiciais.
- Minuta que foi efetivamente utilizada, se houver, somente para o revisor.
- Providência correta, inclusive quando não havia petição a produzir.
- Fatos indispensáveis, provas contrárias, decisão aplicável e fontes/páginas.
- Afirmações proibidas por ausência de prova e pendências que exigiam contato.
- Prazo/regra conferidos pelo advogado e tempo habitual de trabalho, medido ou
  identificado como estimativa.

Excluir documentos posteriores à data de referência e separar processos
relacionados do conjunto reservado. Não colocar dados de casos no Git.

## Executar a rodada

1. O fundador acompanha o advogado percorrendo um caso pelo fluxo de upload,
   processamento, revisão das fontes e minuta. Registra qualquer intervenção
   manual e o ponto de dúvida. Sem acesso judicial, encerrar em exportação.
2. Fixar o mesmo pacote de entrada para o modelo atual e o Astra. O comando
   existente `app.agent.evaluate` faz as chamadas quando executado no ambiente
   autorizado e grava uma linha por tentativa. Esta entrega não executou
   chamadas pagas nem recebeu casos reais.
3. Preparar a revisão sem metadados de modelo usando o comando abaixo. Ele é
   local e não faz chamadas de IA. O fundador opera o comando; o advogado
   recebe somente a pasta `revisor` e os documentos de cada código de caso.
4. O advogado revisa na ordem aleatória preparada, confere as fontes e registra
   tempo, aproveitamento, erros e omissões no CSV. Não revelar a chave antes
   de concluir a rodada. A familiaridade com o segundo texto pode reduzir o
   tempo; registrar esse efeito e ampliar/contrabalançar a amostra depois.
5. O fundador cruza o CSV com `coordenacao/chave.json`, investiga cada falha e
   escolhe uma correção. O comando não atribui nota jurídica e não calcula
   automaticamente métricas. Ausência de resposta não é aprovação.

```powershell
# A partir de backend; lê resultados já existentes, sem chamar provedores.
.\.venv\Scripts\python.exe -m app.agent.prepare_review --runs artifacts/evals/comparacao.jsonl --output artifacts/evals/rodada-01
```

O pacote gera arquivos de texto por minuta, instruções e `avaliacoes.csv`.
A chave separada preserva caso, hash da entrada, modelo, status, latência e
hash do arquivo entregue. Falhas de geração permanecem na rodada. Uma pasta
existente nunca é sobrescrita. A retirada de metadados não elimina pistas
eventualmente presentes no próprio texto do modelo.

## Decidir o que corrigir

| Achado do advogado | Próxima mudança |
|---|---|
| Documento relevante não foi enviado | Melhorar inventário e pendências; solicitar o documento do cliente ou obter os autos pelo canal adequado. |
| Documento está presente, mas foi mal extraído | Corrigir OCR e qualidade por página antes de mudar o modelo de redação. |
| Fato está no acervo, mas não chegou ao redator | Melhorar seleção por providência, cronologia e provas contrárias; medir a recuperação antes de adicionar busca semântica. |
| Fonte correta chegou, mas foi interpretada incorretamente | Rever preparação/estrutura da análise e comparar os modelos com a mesma entrada. |
| Texto está correto, mas pede muita reescrita | Aplicar modelo de peça e estilo aprovado do escritório, sem reutilizar fatos de outros casos. |
| A maior perda de tempo é montar e enviar | Priorizar pacote de anexos/destino e o primeiro canal de protocolo. |

Uma citação literal válida demonstra que o trecho existe, **não** que ele
sustenta toda a afirmação jurídica. O revisor deve conferir essa relação e
apontar contradições. A camada atual não promete verificar automaticamente
cada conclusão, nem provar que o upload contém todos os autos do tribunal.

Comparar modelo atual/Astra apenas quando o hash de entrada for igual. Para
medir uma melhoria de contexto, manter o modelo fixo e identificar o novo
hash; depois repetir o par. Não atribuir à troca de modelo um ganho causado
por documentos adicionais.

## Critério para avançar

Nesta rodada exploratória, produzir cinco fichas revisadas e uma lista de
erros com causa investigada. Corrigir primeiro qualquer erro material. Em
seguida, ampliar a amostra reservada conforme o plano de evolução e medir
tempo ativo total, inclusive conferência e montagem. Redução de 30% do tempo
e 80% de aproveitamento com edição localizada continuam hipóteses de aceite,
não resultados já alcançados.

**Próxima entrega de produto:** um pacote de evidências orientado à providência
escolhida, com fatos essenciais, cronologia, prova contrária e lacunas, validado
nos casos do parceiro. A infraestrutura documental deixa de ser a frente
principal após a validação desta etapa; novas mudanças nela exigem um defeito
ou gargalo observado.

**Primeiro protocolo automatizado:** só depois de escolher tribunal/sistema,
tipo de ato e acesso. Homologar preparo, assinatura quando aplicável, destino,
PDF/anexos exatos aprovados e recibo reconciliado. Uma queda depois do envio
gera estado incerto e consulta do resultado, nunca repetição cega do ato.
