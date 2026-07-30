# O modelo Garfield.Law, dissecado — e como ele se transpõe para o Causor

Pesquisa de 2026-07-29. Complementa
[`viabilidade-mercado-2026-07-29.md`](viabilidade-mercado-2026-07-29.md), que
identificou a Garfield como o único precedente regulatório de "IA que
protocola" aprovado por um regulador.

Este arquivo faz duas coisas: **(1)** dissecar o que a Garfield realmente é, com
números; **(2)** testar, peça por peça, o que é transponível para o Brasil — e o
que é ilegal aqui.

Inferências marcadas **[inferência]**. Fontes ao final.

---

## 1. O que a Garfield é, em uma frase

**Não é um software vendido a escritórios. É um escritório de advocacia
regulado, cujo funcionário é um sistema.** Toda a diferença está aí, e é a
primeira coisa que não atravessa a fronteira.

## 2. A anatomia, em sete peças

| # | Peça | O que a Garfield fez |
|---|---|---|
| 1 | **Forma jurídica** | Garfield.Law Ltd, **autorizada e regulada pela SRA** (mai/2025) — o 1º escritório do Reino Unido operando integralmente por plataforma de IA |
| 2 | **Uma única raia** | Recuperação de dívida, **small claims até £10.000**, Inglaterra e Gales. Nada além disso |
| 3 | **Cliente** | O **credor** (PME) — não um escritório de advocacia. "No solicitor needed" |
| 4 | **Preço por passo** | £2,00 a cobrança amigável; £7,50 a *letter before action*; **~£400 para recuperar £7.000** (≈5,7% do valor). Custa £2 para começar |
| 5 | **Divisão IA/humano** | LLM + **sistema determinístico** para o procedimento. IA faz o trabalho documental; **advocacia oral fica com humano** (barrister) |
| 6 | **Gate** | "Garfield is not autonomous and will only take a step where the client has approved it" — aprovação do cliente em **cada passo**; solicitors nomeados respondem por **toda** saída do sistema |
| 7 | **Tração ano 1** | **600+ causas**, **£500 mil+** recuperados. 1ª vitória em julgamento: 14/05/2026, Wandsworth County Court, £7.000 + improcedência da reconvenção — cliente gastou ~£400; o réu contratou solicitor **e** barrister |

### 2.1 A crítica que importa

O *Artificial Lawyer* aponta o gargalo real, e não é tecnológico: **Philip Young
(co-fundador e único solicitor listado) responde pessoalmente pela conferência
de cada documento antes do envio.** Se escalar, o humano é o teto. E,
juridicamente, "os advogados nomeados são responsáveis por todos os resultados
do sistema" — o risco foi transferido para o profissional, não para a
tecnologia.

Segunda observação do mesmo texto: **não é um marco tecnológico.** Fluxo
estruturado + IA leve + supervisão jurídica. O marco é **regulatório**.

### 2.2 As três decisões de projeto que explicam o sucesso

1. **Raia fechada.** Small claims de dívida é um procedimento em que a árvore de
   decisão é finita e o documento de entrada é estruturado (contrato, fatura,
   nota). Não existe "depende".
2. **Preço colado no valor recuperado**, não em assento/mês. 5,7% do que se
   recupera é uma conta que o cliente faz em dez segundos.
3. **O gate como produto.** A aprovação passo a passo não é fricção de
   compliance; é o que torna o serviço **autorizável**. Foi a condição de
   existir.

---

## 3. O teste de transposição: o que passa e o que não passa no Brasil

### 3.1 ❌ Não passa — a forma jurídica (peça 1)

O Reino Unido tem **Alternative Business Structures** desde o Legal Services Act
2007: sócio não advogado e investidor externo em escritório, sujeitos a teste de
idoneidade. **O Brasil não tem equivalente**, e a direção é a oposta:

- **Lei 8.906/94, arts. 15–17:** sociedade de advogados admite **somente
  advogados** como sócios; não é atividade empresarial e não pode ter
  característica de sociedade comercial.
- A **Comissão Nacional de Sociedades de Advogados do Conselho Federal da OAB
  rejeitou** a participação de empresas em sociedades de advocacia — o
  argumento é risco de conflito de interesse, enfraquecimento da fiscalização
  disciplinar e abertura para mercantilização.
- A **OABRJ obteve procedência** em ação na Justiça Federal contra
  mercantilização da advocacia.

**Conclusão:** "Causor S.A. vira escritório de advocacia com capital de risco"
não existe no Brasil. Não é uma questão de estruturar bem — é vedação de
estatuto, reafirmada em 2026.

### 3.2 ❌ Não passa — vender direto ao credor (peça 3)

Aqui o risco é ainda mais concreto que o societário. Em **setembro de 2025, uma
juíza proibiu uma plataforma de oferecer serviços privativos da advocacia** — e
a conduta descrita é exatamente o funil da Garfield: **análise prévia de
documentos, estimativa percentual de êxito e direcionamento do cliente**. Some-se
o **Provimento 205/2021**, que veda captação de clientela definida como
mecanismo que "de forma ativa... se destina a angariar clientes pela indução
direta à contratação ou pelo **estímulo ao litígio**".

O caminho que parece a brecha — **Juizado Especial Cível, onde até 20 salários
mínimos (R$ 32.420 em 2026) a parte litiga sem advogado**, com peticionamento
eletrônico pelo próprio cidadão (o TJSP tem portal para isso) — é uma
armadilha, não uma oportunidade: um produto que redige a inicial e estima êxito
para a parte cai precisamente na conduta que a decisão de 2025 proibiu.
**[inferência, mas com precedente direto]**

### 3.3 ✅ Passa, e é o mais valioso — a disciplina de raia (peça 2)

Esta é a lição que o Causor mais precisa e menos aplicou. A Garfield escolheu
**um** procedimento; o Causor escolheu "operação processual brasileira". Compare:

| | Garfield | Causor hoje |
|---|---|---|
| Procedimento | 1 (small claims de dívida) | qualquer intimação, qualquer área |
| Sistemas de tribunal | 1 canal nacional | PJe, eproc, e-SAJ, Projudi × 90+ tribunais × 2 graus |
| Documento de entrada | contrato/fatura | autos inteiros de qualquer natureza |
| Árvore de decisão | finita | aberta |

A Garfield venceu porque **fechou a árvore de decisão antes de escrever
código**. O Causor construiu a máquina genérica primeiro. É por isso que
"protocolar" ficou grande demais: são 8 conectores × N tribunais em vez de um
ato num procedimento.

### 3.4 ✅ Passa — preço por passo colado ao valor (peça 4)

5,7% do valor recuperado é um modelo que escapa da âncora de R$ 197/mês do
software jurídico (ver `viabilidade-mercado-2026-07-29.md` §7). Para o Causor,
a tradução legítima é **preço por ato entregue** (intimação tratada, prazo
cumprido, minuta aceita), não por assento.

**Ressalva jurídica:** cobrar percentual de êxito é honorário — privativo de
advogado. Um fornecedor de software cobrando "% do que o cliente ganhou"
tangencia participação em atividade privativa e *quota litis*. O desenho seguro
é **preço por ato executado**, previsível e desvinculado do resultado, ainda que
*calibrado* pelo valor que o ato protege. **[inferência — vale validação com
advogado especialista antes de precificar]**

### 3.5 ✅ Passa — e o Causor já tem: gate e divisão IA/humano (peças 5 e 6)

Aqui a notícia é boa e está subaproveitada. O que a SRA aceitou é, item por
item, o que já está no código do Causor:

| Garfield (aprovado pela SRA) | Causor (já implementado) |
|---|---|
| LLM + sistema determinístico | classificador Claude + `prazo_engine` determinístico |
| Nunca autônomo; aprovação em cada passo | gate de aprovação; `protocolar` exige `aprovada` |
| Solicitor nomeado responde por toda saída | advogado responsável + gate + auditoria imutável |
| Advocacia oral permanece humana | protocolo final confirmado pelo advogado |
| Conferência documental antes do envio | contexto `ready` + citações verificadas + 409 fail-closed |

**Isto é ativo de posicionamento, não dívida técnica.** O gate deixou de ser "o
preço de não sermos autônomos" e passou a ser "o desenho que um regulador
chancelou" — e casa com o Plano Nacional de IA da OAB (10/06/2026: *"o advogado
e a supervisão humana permanecem como peças centrais"*).

### 3.6 ✅ Passa por outro caminho — o acesso ao tribunal (o insight estrutural)

A Garfield resolveu o acesso ao sistema do tribunal **sendo o advogado**. O
Causor não pode ser o advogado — mas o **agente local** é o equivalente
funcional: roda na máquina do advogado, com a credencial dele, no volume de um
humano. Do ponto de vista do tribunal, é o advogado trabalhando.

Ou seja: o ativo que o roadmap tratou como *fallback* é a transposição correta
da peça que fez a Garfield funcionar. O desvio para o MNI é o que tenta ser
"órgão" — e é o caminho que a §2 do arquivo de viabilidade mostra fechado.

---

## 4. Os três modelos possíveis para o Causor

### Modelo A — Fornecedor de software (status quo), com a disciplina da Garfield

Causor vende para escritórios pequenos. Muda **o quê**: uma raia, preço por ato,
gate como argumento de venda.

- **Legal:** sim, sem ressalva.
- **Ganho:** aplica as peças 2, 4, 5 e 6 sem tocar na estrutura.
- **Risco:** distribuição. Astrea/ADVBOX/Projuris têm milhares de escritórios e
  estão lançando agentes (ver viabilidade §4). Software genérico perde para
  incumbente; software de **uma raia, com prova de completude e trilha
  auditável**, não é o que eles fazem.

### Modelo B — Causor + escritório-âncora (a transposição pragmática) ⭐

Uma **sociedade de advogados de verdade** (sócios advogados — o advisor), que é
parceira de projeto e primeira operadora, licenciando o Causor como software.

- **Legal:** licenciar software para escritório é trivial e comum. O que **não**
  pode: Causor ter participação societária no escritório, o escritório ser
  fachada, remuneração como percentual de êxito, ou o Causor fazer captação e
  publicidade de serviço jurídico. Mantidas essas fronteiras, é o desenho normal
  de fornecedor + cliente-âncora.
- **Ganho — e é enorme:** resolve **hoje** o bloqueio que o roadmap atribui ao
  MNI e ao acesso do advisor. Credencial real, processos reais, volume real do
  mesmo ato, e um caso de uso ("recuperamos X em N causas") — que é exatamente o
  que a Garfield publicou no ano 1.
- **Risco:** confundir os papéis. Se a receita do Causor virar participação no
  êxito, ou se o marketing vender resultado jurídico, colapsa em mercantilização
  e captação — as duas condutas com precedente de condenação citadas em §3.

### Modelo C — Causor opera como escritório (Garfield literal)

- **Legal:** ❌. Vedado por Lei 8.906 arts. 15–17, reafirmado pela Comissão
  Nacional de Sociedades de Advogados, sem equivalente de ABS no Brasil.
- **Descartar.** Não gastar mais tempo nisso.

**Recomendação: B como caminho, A como produto.** O escritório-âncora é o
mecanismo de validação e de acesso; o produto vendido a terceiros continua sendo
software.

---

## 5. Se fosse para escolher a raia hoje

A pergunta certa, no espírito da Garfield: *qual ato jurídico tem árvore de
decisão finita, documento de entrada estruturado, alta frequência no mesmo
escritório, e valor que paga a ferramenta?*

Candidatos, com o critério aplicado:

| Raia | Árvore fechada? | Entrada estruturada? | Frequência | Veredito |
|---|---|---|---|---|
| **Cobrança judicial de carteira** (ação monitória CPC 700–702 + execução de título extrajudicial CPC 784) | ✅ | ✅ contrato/boleto/cheque/nota | ✅ carteiras de condomínio, clínica, escola, PME | **melhor análogo direto da Garfield** |
| Contencioso de massa consumerista (defesa) | 🟡 | 🟡 | ✅ | ocupado pela Enter, lado do réu |
| Recurso inominado / manifestações JEC | ✅ | 🟡 autos variados | ✅ | bom 2º passo |
| "Qualquer intimação" (hoje) | ❌ | ❌ | ✅ | é o que impediu de fechar |

A cobrança de carteira é o análogo mais fiel: mesmo ato, repetido, com documento
de entrada que o **credor** entrega estruturado — e é onde a prova de completude
dos autos e o prazo determinístico do Causor rendem mais por unidade de
engenharia. **[inferência — precisa ser confrontada com a carteira real do
escritório-âncora antes de virar decisão]**

---

## 6. O que fazer com isto (concreto)

1. **Não mudar a arquitetura.** As peças 5 e 6 já estão prontas e são o que um
   regulador aprovou. Parar de tratar o gate como limitação em documento e em
   pitch.
2. **Escolher uma raia** com o escritório-âncora, olhando a carteira real —
   critério da tabela §5, não intuição.
3. **Trocar o preço** de assento/mês para **por ato entregue**, e validar a
   redação com advogado especialista (§3.4).
4. **Formalizar o Modelo B** com fronteiras escritas: licença de software, sem
   participação societária, sem remuneração por êxito, sem publicidade de
   serviço jurídico pelo Causor.
5. **Medir como a Garfield mediu:** número de atos concluídos e valor
   protegido/recuperado no ano 1. "600 causas e £500 mil" venceu qualquer
   discussão sobre viabilidade. Métrica de contagem de testes não vende nada.
6. **Descartar em definitivo** o Modelo C e a variante "vender ao cidadão no
   JEC" (§3.2).

---

## 7. Lacunas honestas

- O release oficial da SRA (`news.sra.org.uk/.../garfield-ai-authorised`) voltou
  **404** nesta pesquisa; as condições da autorização vêm de análises
  secundárias (Dechert, ICLR, Artificial Lawyer, VinciWorks), não do texto
  primário. Se as condições exatas importarem para uma decisão, buscar o texto
  da SRA.
- A data da rejeição pela Comissão Nacional de Sociedades de Advogados não foi
  confirmada nesta pesquisa (a numeração da notícia sugere jun–jul/2026
  **[inferência]**).
- Faturamento e estrutura de custo da Garfield não são públicos; ~£400 por causa
  de £7.000 é o único ponto de preço confirmado, e vem de um caso.
- Se a Garfield tem seguro de responsabilidade profissional diferenciado (item
  que a SRA costuma exigir) não foi verificado.
- A viabilidade do Modelo B depende de opinião legal brasileira que esta
  pesquisa **não** substitui — especialmente sobre preço por ato vs. participação
  em êxito.

---

## Fontes

- [Garfield.Law — site oficial (etapas e preços)](https://www.garfield.law/)
- [Garfield AI wins first court trial with regulated AI lawyer](https://www.garfield.law/press/garfield-ai-wins-first-court-trial-with-regulated-ai-lawyer)
- [AI-powered law firm claims first county court victory — Law Gazette](https://www.lawgazette.co.uk/news/ai-powered-law-firm-claims-first-county-court-victory/5127138.article)
- [Artificial intelligence-based law firm wins in court — Computer Weekly](https://www.computerweekly.com/news/366644941/Artificial-intelligence-based-law-firm-wins-in-court)
- [Is Garfield the '1st AI-Driven Law Firm' A Big Deal? — Artificial Lawyer](https://www.artificiallawyer.com/2025/05/12/is-garfield-the-1st-ai-driven-law-firm-a-big-deal/)
- [SRA authorizes UK's first AI-based law firm — Dechert](https://www.dechert.com/knowledge/re-torts/2025/6/solicitors-regulation-authority-authorizes-uk-s-first-ai-based-l.html)
- [Authorising the algorithm — ICLR](https://iclr.net/news/authorising-the-algorithm-what-the-first-artificial-intelligence-law-firm-signals-for-legal-practice/)
- [Garfield AI e a aprovação da SRA — VinciWorks](https://vinciworks.com/blog/garfield-ai-sra-law-firm/)
- [Comissão Nacional de Sociedades de Advogados rejeita participação de empresas em sociedades de advocacia — OAB](https://www.oab.org.br/noticia/64325/comissao-nacional-de-sociedades-de-advogados-rejeita-participacao-de-empresas-em-sociedades-de-advocacia)
- [Justiça Federal julga procedente ação da OABRJ contra mercantilização da advocacia](https://oabrj.org.br/noticias/justica-federal-julga-procedente-acao-oabrj-contra-mercantilizacao-advocacia)
- [Juíza proíbe plataforma de oferecer serviços privativos da advocacia — ConJur (04/09/2025)](https://www.conjur.com.br/2025-set-04/juiza-proibe-plataforma-de-oferecer-servicos-privativos-da-advocacia/)
- [Provimento nº 205/2021 — OAB-SP (texto)](https://www.oabsp.org.br/upload/526840268.pdf)
- [Da sociedade de advogados (EOAB, arts. 15 a 17) — vLex](https://vlex.com.br/vid/da-sociedade-advogados-eoab-591369098)
- [Teto do Juizado Especial Cível 2026: valor e advogado](https://smargiassi.com.br/blog/teto-juizado-especial-civel-2026-valor-advogado/)
- [Peticionamento eletrônico JEC — TJSP](https://www.tjsp.jus.br/peticionamentojec)
- [Ação monitória no CPC: o que é e como funciona — Projuris](https://www.projuris.com.br/blog/o-que-e-acao-monitoria/)
- [OAB anuncia Plano Nacional de IA na advocacia (10/06/2026)](https://www.oab.org.br/noticia/64268/conselho-federal-da-oab-anuncia-plano-nacional-para-integrar-inteligencia-artificial-a-advocacia)
