# Rota do produto com pouco caixa — 2026-07-30

Continuação de [`viabilidade-mercado-2026-07-29.md`](viabilidade-mercado-2026-07-29.md).
Aquela pesquisa respondeu *"o produto é viável?"*. Esta responde quatro
perguntas do fundador, feitas com a restrição explícita de **pouco caixa**:

1. Onde o Causor está no mapa competitivo (Judit, Enter, Garfield e adjacentes)?
2. Qual a melhor rota para **contexto completo dos autos**?
3. Qual a melhor rota para **protocolar**?
4. Sem protocolo, sobra produto vendável e escalável?

E, ao final, o diagnóstico dos fluxos de **agente local × MNI**, que o operador
relatou como confusos.

Inferência não confirmada por fonte primária está marcada **[inferência]**.
Item que precisa de teste está marcado **[falsificar]**.

---

## 1. Resposta curta

Três frases:

- **O mapa competitivo diz que ninguém ganhou fazendo as três camadas ao mesmo
  tempo.** Todo vencedor escolheu uma e comprou (ou dispensou) as outras. O
  Causor hoje tenta as três com o menor caixa da lista.
- **O CNJ está construindo, de graça e em escala nacional, exatamente as duas
  coisas que o Causor tentou resolver tribunal a tribunal**: consulta unificada
  e peticionamento intercorrente unificado, num portal só (jus.br), com login
  gov.br. Isso reprecifica os conectores por sistema de "caminho crítico" para
  "dívida técnica cara".
- **Sem protocolo ainda sobra produto — e sobra maior.** Eve (US$ 1 bi, 1.200+
  escritórios, mesmo ICP) e EvenUp (>US$ 2 bi) não protocolam. Tirar o ato
  irreversível do caminho crítico torna o Causor vendível em **qualquer**
  tribunal do país no dia seguinte, porque DJEN e DataJud são nacionais.

---

## 2. O mapa competitivo — quatro camadas, não uma lista

O erro de comparar "Causor × Judit × Enter × Garfield" é tratá-los como
concorrentes. Eles estão em camadas diferentes da mesma cadeia.

| Camada | Quem | Preço observado | O que é |
|---|---|---|---|
| **1. Dados / captura** | Judit, Escavador, Digesto, Jusbrasil; DataJud e DJEN de graça | Judit Plataforma **R$ 9,90/mês**; Judit API **R$ 1k–35k/mês + R$ 5k setup** | Commodity. Preço caindo. |
| **2. Ação / execução** | doc9 (~600 mil ops/mês), iJUD/OAB, ADVBOX, PeticionaMais | iJUD **R$ 19,90/mês**; Whom.doc9 **R$ 1,5k–10k/mês** | Ocupada nas duas pontas. |
| **3. Inteligência aplicada** | Enter (US$ 1,2 bi), Eve (US$ 1 bi), EvenUp (>US$ 2 bi), Supio, Harvey, Legora | Eve **US$ 100–300/usuário/mês** | Onde o dinheiro foi parar. |
| **4. Escritório-produto regulado** | Garfield.Law | **£2** cobrança, **£7,50** letter before action, ação a partir de **£50** | Vende resultado, não software. |

### 2.1 O padrão que atravessa os quatro

**Nenhum deles construiu a camada de baixo.**

- **Enter** virou unicórnio **comprando** dados da Judit e vendendo inteligência.
  A própria Judit generaliza o padrão para Harvey (EUA) e Legora (Suécia).
- **Eve** chegou a US$ 1 bi e 1.200+ escritórios de **autor, pequenos e médios**
  — o ICP declarado do Causor — **sem protocolar nada**.
- **EvenUp** dobrou para >US$ 2 bi com Series E de US$ 150M fazendo carta de
  demanda e análise de prontuário. Também não protocola.
- **Garfield** resolveu o acesso ao tribunal **sendo o escritório**, numa raia
  única (dívida até £10k). Em maio de 2026 ganhou o primeiro julgamento,
  recuperando £7.000 por ~£400, contra uma parte que pagou solicitor **e**
  barrister. Já são 600+ causas e £500 mil+ recuperados.

O Causor hoje faz camada 1 (DJEN/DataJud/captura de autos), camada 2 (protocolo)
e camada 3 (prazo/minuta) simultaneamente. Nenhum dos quatro vencedores fez
isso — e todos tinham mais dinheiro.

### 2.2 O que o preço está dizendo

O meio está sendo esmagado por baixo: **R$ 9,90** (Judit) para monitorar,
**R$ 19,90** (iJUD, marketplace da OAB) para protocolar. Vender "acesso" ou
"clique" nessa faixa é perder. A âncora certa continua sendo o **paralegal
(R$ 2,5–4 mil/mês)** e a faixa continua **R$ 500–1.500/mês por escritório** —
mas só se o entregável for *o trabalho do dia resolvido*.

---

## 3. A descoberta que muda a arquitetura: o CNJ está convergindo tudo

Isto **não** estava na pesquisa de ontem e é o achado mais acionável desta.

### 3.1 jus.br — um portal, todos os tribunais

- A **Resolução CNJ 455/2022** instituiu o Portal de Serviços com **consulta
  processual unificada, peticionamento inicial e intercorrente e login único**,
  com **adesão obrigatória** pelos tribunais.
- A **Resolução CNJ 624/2025** (publicada em 03/06/2025) determina que o jus.br
  tenha peticionamento **inicial e intercorrente em todos os processos
  eletrônicos** dos sistemas conectados à PDPJ-Br, com prazo de **60 dias** para
  os tribunais integrarem após a publicação da documentação técnica.
- Cerca de quatro meses após o lançamento, **39 tribunais** já tinham integrado
  o peticionamento intercorrente (CNJ: *"Mais de 1/3 dos tribunais brasileiros
  disponibilizam peticionamento intercorrente via Jus.br"*).
- O login é **único, integrado ao gov.br**.

O que isso significa em uma frase: **o CNJ está eliminando, por norma, a razão
de existir das Tasks 6–9** (um conector por sistema processual). Em vez de PJe +
eproc + e-SAJ + Projudi = 4 conectores × (leitura + protocolo) = 8 entregas,
existe **uma** superfície nacional que já cobre 39 tribunais e tende a 100%.

### 3.2 Domicílio Judicial Eletrônico — API oficial para empresa privada

A documentação da PDPJ descreve API de integração para *"instituições que
optarem por consumir as comunicações processuais via serviço"*, incluindo
**empresas privadas**:

- cadastro de **CNPJ** no frontend web, credencial gerada com certificado
  digital (`Gerenciar credenciais API`);
- `client_id` + `client_secret`, `grant_type: client_credentials`;
- header **`On-behalf-Of: <CPF>`** — ou seja, um modelo oficial e documentado de
  **agir por conta de uma pessoa**;
- endpoints para listar comunicações e acessar o **inteiro teor**.

Isto é o oposto do MNI: canal oficial, documentado, com credenciamento
self-service para CNPJ privado. **[falsificar]** o escopo — se entrega só as
comunicações dirigidas ao próprio CNPJ cadastrado ou também as de terceiros que
autorizaram — porque isso decide se serve ao escritório ou só ao cliente PJ dele.

### 3.3 Codex — o cofre que resolveria tudo, e provavelmente não abre

A **Resolução CNJ 446/2022** institui o Codex como base oficial com *"metadados
processuais e inteiro teor dos documentos e atos proferidos relativos a todos os
processos eletrônicos, públicos ou sigilosos"*, com série histórica desde
01/01/2020. É literalmente "contexto completo dos autos" pronto, nacional.

Mas a norma só menciona como destinatários *"sistemas e soluções do CNJ"*, e o
CNJ está regulamentando o acesso público a esses dados. Acesso por privado **não
está previsto**. Custo de perguntar: um e-mail. Probabilidade: baixa
**[inferência]**. Payoff: encerra o problema 1 do produto.

---

## 4. Rota recomendada para o problema 1 — contexto completo dos autos

**Manter o agente local como executor. Trocar o alvo dele.**

Hoje o agente local é apontado para o sistema do tribunal (eproc/TJTO no piloto).
A proposta é uma escada nova, em ordem de custo crescente:

1. **DJEN + DataJud** (já rodando, nacional, grátis) — intimação e movimentos.
2. **jus.br pelo agente local**, com o login gov.br do próprio advogado — um só
   alvo de automação para 39+ tribunais. **[falsificar]**: o jus.br entrega o
   **inteiro teor / download das peças** dos processos do advogado, ou só a
   consulta e o peticionamento? Este é o teste mais barato e mais valioso
   disponível: o advisor loga no jus.br e tenta baixar as peças de um processo
   dele. Trinta minutos, R$ 0.
3. **Sistema do tribunal pelo agente local** (o que já existe) — fallback para
   tribunal que ainda não integrou o jus.br.
4. **Vendor pago (Judit)** — só se 2 e 3 falharem *e* o cliente pagar. A Judit
   admite no próprio contrato de API que anexo pode não vir; ela vende
   conveniência, não integridade.

A prova de completude (enumeração dupla + SHA-256 + gate fail-closed) continua
sendo o diferencial e **independe da fonte** — o pipeline do Plano 2 não sabe de
onde vieram os bytes. Isso é o ativo mais bem construído do repositório e é o
único item da lista que ninguém no mercado vende.

---

## 5. Rota recomendada para o problema 2 — protocolar

**A ordem correta é a inversa da que o roadmap tinha.**

| Rota | Veredito |
|---|---|
| **MNI (`entregarManifestacaoProcessual`)** | Descartar do caminho crítico. Desenhado para órgão público (§2 da pesquisa de ontem) **e** — fato novo, verificado no código — os perfis MNI confirmados cobrem TJAP, TJES, TJMT, TJPA, TJPE, TJPI, TJRR, TRF5 e TRF6. **O tribunal do piloto (TJTO) não está na lista.** Nem TJSP, TJRJ, TJMG, TJRS, TJPR ou qualquer TRT. Mesmo deferido, não serve ao piloto. |
| **jus.br pelo agente local** | **Melhor aposta.** Um alvo, cobertura nacional crescente por norma, login gov.br do próprio advogado, na máquina dele, em volume humano. |
| **Conector por sistema (Tasks 6–9)** | Rebaixar a fallback. São 8 entregas travadas em acesso externo, para resolver o que o CNJ está unificando. |
| **Correspondente humano** | Sério como ponte comercial: R$ 80–150 por ato. Se o piloto tiver 20 protocolos/mês, isso é R$ 1,6–3k/mês — mais barato que qualquer engenharia de conector, e entrega a promessa inteira ao cliente enquanto o software amadurece. **[inferência]** sobre volume. |

O gate humano continua sendo produto, não fricção — é a arquitetura que a SRA
aprovou na Garfield (aprovação do cliente em **cada** passo procedimental).

---

## 6. Sem protocolo, sobra produto? Sim — e sobra maior

### 6.1 A evidência

O mercado já respondeu, três vezes, com dinheiro:

- **Eve**: US$ 1 bi de valuation, 1.200+ escritórios, escritórios de autor
  pequenos e médios, US$ 100–300/usuário/mês. **Não protocola.**
- **EvenUp**: >US$ 2 bi, Series E de US$ 150M. **Não protocola.**
- **Enter**: unicórnio sem construir a camada de dados.

O botão "enviar" não é o fosso em lugar nenhum do mundo. A preparação confiável
do trabalho é.

### 6.2 Por que sem protocolo o produto fica *mais* escalável, não menos

| Com protocolo no caminho crítico | Sem protocolo |
|---|---|
| Trabalho por sistema processual e por tribunal | DJEN e DataJud são **nacionais** desde o dia 1 |
| Ato irreversível → risco de malpractice do próprio produto | Nenhum ato irreversível |
| Exposição à MP 2.200-2 (certificado não se compartilha) | Fora do escopo |
| Pior modo de falha: credencial do cliente bloqueada, com cópia à OAB | Não aplicável |
| Onboarding: parear máquina, logar tribunal, validar conector | Onboarding: informar OAB |

Vender em qualquer estado do Brasil na semana que vem é uma propriedade que só
existe **enquanto o protocolo não estiver no caminho crítico**.

### 6.3 A condição — e é dura

O produto sem protocolo só é defensável se o entregável for **o dia de trabalho
resolvido**, não "mais uma IA que escreve petição". A categoria "IA que redige"
está lotada no Brasil em 2026 (ADVBOX, Inspira, Aurum, ForeLegal, Jusbrasil,
600+ legaltechs na AB2L). O que separa o Causor não é a escrita — é o que está
**embaixo** dela:

1. **Autos comprovadamente inteiros** (enumeração dupla + SHA-256 + gate
   fail-closed) — a minuta é escrita sobre o processo real, com citação
   verificada `[DOC-N p.M]`, e trava se o contexto não estiver íntegro.
2. **Prazo determinístico auditável** — código testável, não chute de LLM, num
   mundo DJEN + Domicílio pós-Res. 455/2022 e 569/2024, onde a regra ficou
   *mais* difícil.
3. **Trilha imutável de supervisão humana** — o artefato que responde à OAB, ao
   cliente e ao seguro, alinhado ao Plano Nacional de IA da OAB (10/06/2026).

Isso é infraestrutura, não prompt. É a razão pela qual é defensável.

**Frase de venda correspondente:** *"Toda manhã, cada intimação do seu escritório
já chega com o prazo calculado, os autos conferidos e a minuta escrita em cima do
que está no processo — com a prova de que nada faltou. Você lê, ajusta e assina."*

---

## 7. Os fluxos confusos — diagnóstico e correção

O operador relatou que **agente local × MNI** não fazem sentido. Estão certos, e
o problema é maior do que apresentação.

### 7.1 O que a auditoria do código mostra

1. **A tela pede uma credencial que o cliente não tem como obter.**
   `Configurações → Tribunais` empilha três seções (`MniSection`,
   `AgentSection`, `VaultSection`). A primeira pede tribunal + `idConsultante` +
   senha do MNI — que exige credenciamento institucional que, pela pesquisa de
   ontem, provavelmente não é concedido a CNPJ privado.
2. **Mesmo deferido, não serviria ao piloto.** `connectors/mni/profiles.py`
   confirma 14 perfis em 9 tribunais; **TJTO não está entre eles**, e o piloto é
   `EPROC · TJTO`. A tela oferece com destaque um caminho que, para o usuário do
   piloto, não existe.
3. **A assimetria mais importante não está escrita em lugar nenhum:** o MNI
   cobre **só leitura**. `MniFilingDriver` não existe e `connectors/drivers.py`
   é explícito — protocolo real roda no agente local. Ou seja: **protocolar
   sempre exige o computador pareado, em todo tribunal, inclusive onde houver
   credencial oficial.** A tela dá a impressão contrária.
4. **A tela está organizada por tecnologia, não por capacidade.** O advogado não
   precisa saber a palavra "MNI". Ele precisa saber, por tribunal: *consigo
   redigir? consigo protocolar? se não, o que falta?*

### 7.2 A correção — em ordem de custo

**(a) Hoje, ~1 hora.** Remover `MniSection` da UI. O backend
(`connectors/mni/`, ~780 LOC, 6 arquivos de teste, rotas `/mni/credenciais`)
**fica onde está** — deletar custa dinheiro e o MNI pode voltar a importar. Some
o pedido de credencial impossível, some a seção que compete com o agente, e o
único modelo mental que sobra é o certo: *o Causor entra no tribunal pelo seu
computador, com o seu login*. É a maior redução de confusão por real gasto do
repositório inteiro.

**(b) Em seguida, ~1 dia.** Implementar o design **já aprovado e não
implementado** em
[`superpowers/specs/2026-07-29-acesso-tribunais-por-capacidade-design.md`](../superpowers/specs/2026-07-29-acesso-tribunais-por-capacidade-design.md):
organizar por **capacidade** (ler autos × protocolar), com a decisão única
extraída para `resolve_acesso_tribunal` e consumida tanto pela tela quanto pelo
`resolve_next_step`. O design já resolve o problema; falta executar.

**(c) Vocabulário.** Nunca exibir "MNI". "Agente local" vira **"seu
computador"**. Um só fluxo visível: *criar minuta → aprovar → protocolar*, com o
contexto buscado sozinho no meio.

---

## 8. O que fazer com pouco caixa — ordem

1. **Dois e-mails e um login (custo R$ 0, prazo desta semana).**
   - **[falsificar]** o advisor loga no jus.br e testa: dá para ver e **baixar as
     peças** de um processo dele? O TJTO aceita peticionamento intercorrente por
     lá?
   - **[falsificar]** e-mail a `integracaopdpj@cnj.jus.br` sobre acesso de CNPJ
     privado ao Codex e à API do Domicílio em nome de advogado.
   Estas três respostas decidem a arquitetura dos próximos seis meses e não
   custam nada.
2. **Limpar a UI** (§7.2 a e b). Uma hora e um dia.
3. **Rodar o piloto sem protocolo.** 2–3 escritórios, 30 dias, intimações reais,
   entregando prazo + autos íntegros + minuta. O critério de morte já está
   escrito na pesquisa de ontem: se as minutas forem reescritas do zero **e** o
   motor de prazos não pegar nada que o escritório teria perdido, nenhum conector
   conserta isso.
4. **Não escrever conector novo** até 1 e 3 responderem. As Tasks 6–9 são 8
   entregas travadas em acesso externo, para resolver um problema que o CNJ está
   unificando por resolução.

---

## 9. Lacunas honestas desta pesquisa

- **Não confirmado** se o jus.br dá acesso ao inteiro teor e download das peças
  (só há evidência de consulta unificada + peticionamento). É o item mais
  importante a testar e o mais barato.
- **Não confirmado** se o TJTO integrou o peticionamento intercorrente ao jus.br.
  A lista de TJs citada pelo CNJ (TJAC, TJDFT, TJES, TJGO, TJMG, TJMS, TJMSP,
  TJMT, TJPA, TJPB, TJPE, TJPR, TJRN, TJRO, TJRR) é de uma notícia intermediária,
  não da situação atual.
- **Não confirmado** se o peticionamento pelo jus.br dispensa certificado digital
  (o login é gov.br, mas a assinatura da peça pode ter regra própria por
  tribunal).
- **Não confirmado** o escopo da API do Domicílio Judicial Eletrônico: se serve
  só às comunicações do CNPJ cadastrado ou também às de terceiros autorizados.
- **Automação do jus.br por robô** cai na mesma zona cinzenta de tolerância dos
  portais (Res. CNJ 185/2013 art. 29). A nuance protetora continua valendo — é a
  carteira do próprio advogado, credencial dele, volume humano — mas continua
  sendo permissão que não controlamos.
- Receita, churn e CAC reais de SaaS jurídico para escritório pequeno no Brasil:
  sem dado público.

---

## Fontes

- [Resolução CNJ n. 624/2025](https://atos.cnj.jus.br/atos/detalhar/6150) · [texto compilado](https://atos.cnj.jus.br/files/compilado18070620250603683f39ca8ca16.pdf)
- [Resolução CNJ n. 455/2022](https://atos.cnj.jus.br/atos/detalhar/4509)
- [Resolução CNJ n. 446/2022 — Codex](https://atos.cnj.jus.br/atos/detalhar/4417)
- [Mais de 1/3 dos tribunais disponibilizam peticionamento intercorrente via Jus.br — CNJ](https://www.cnj.jus.br/mais-de-1-3-dos-tribunais-brasileiros-disponibilizam-peticionamento-intercorrente-via-jus-br/)
- [Tribunais já podem integrar peticionamento inicial ao Jus.br — CNJ](https://www.cnj.jus.br/tribunais-ja-podem-integrar-peticionamento-inicial-ao-jus-br/)
- [Jus.br: novo portal centraliza acesso à Justiça — CNJ](https://www.cnj.jus.br/jus-br-novo-portal-de-servicos-do-poder-judiciario-centraliza-acesso-a-justica/)
- [CNJ libera peticionamento inicial no Jus.br para todos os tribunais — Migalhas](https://www.migalhas.com.br/quentes/432404/cnj-libera-peticionamento-inicial-no-jus-br-para-todos-os-tribunais)
- [Petição Intercorrente — Documentação PDPJ-Br](https://docs.pdpj.jus.br/servicos-negociais/portal-servicos/pet-intercorrente/)
- [Domicílio Judicial Eletrônico — Documentação PDPJ-Br](https://docs.pdpj.jus.br/servicos-negociais/domicilio-judicial-eletronico/)
- [Autenticação SSO (Keycloak) — Documentação PDPJ-Br](https://docs.pdpj.jus.br/servicos-estruturantes/autenticacao-sso/)
- [Desenvolvendo para a PDPJ-Br / Acordo com o CNJ](https://docs.pdpj.jus.br/desenvolvendo-para-a-pdpj/acordo-com-o-cnj/)
- [Plataforma Codex — Portal CNJ](https://www.cnj.jus.br/sistemas/plataforma-codex/)
- [CNJ definirá regra para racionalizar acesso público a dados da Justiça — Migalhas](https://www.migalhas.com.br/quentes/413581/cnj-definira-regra-para-racionalizar-acesso-publico-a-dados-da-justica)
- [Planos e preços — Judit Plataforma](https://judit.io/planos-plataforma/) · [Planos e preços — Judit API](https://judit.io/planos-api/) · [Calculadora Judit](https://judit.io/calculadora/)
- [Enter: startup jurídica brasileira que virou unicórnio de IA — Judit](https://judit.io/blog/noticias/enter-unicornio-ia-judit/)
- [Garfield AI — site oficial](https://www.garfield.law/)
- [AI law firm wins in court — Computer Weekly](https://www.computerweekly.com/news/366644941/Artificial-intelligence-based-law-firm-wins-in-court)
- [For $500, an AI Beat 2 Lawyers in UK Court — PYMNTS](https://www.pymnts.com/news/artificial-intelligence/2026/for-500-an-ai-beat-2-lawyers-in-uk-court/)
- [Eve reaches $1B valuation — Legal.io](https://www.legal.io/articles/5738408/AI-Startup-Eve-Reaches-1B-Valuation-With-New-Funding-Round)
- [Eve Legal pricing explained — ProPlaintiff](https://www.proplaintiff.ai/post/eve-legal-pricing-explained)
- [Top legal tech & legal AI startups 2026 — Lawyerd](https://lawyerd.net/blog/top-legal-tech-startups-2026/)
- [Legaltech no Brasil em 2026 — Legal Control](https://legalcontrol.com.br/legaltech-brasil-2026/)
- [iJUD Peticiona — Central da Advocacia / OAB](https://ijud.com.br/produto/ijud-peticiona/)
