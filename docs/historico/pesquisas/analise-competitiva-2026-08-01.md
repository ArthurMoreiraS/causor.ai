# Análise competitiva — 2026-08-01

Terceira rodada de pesquisa de mercado, feita a pedido do fundador ("estamos no
caminho certo?"). Continua [`viabilidade-mercado-2026-07-29.md`](viabilidade-mercado-2026-07-29.md)
(o produto é viável?) e [`rota-produto-2026-07-30.md`](rota-produto-2026-07-30.md)
(qual rota com pouco caixa?). Esta responde: **a rota escolhida sobrevive ao que
o mercado fez até agosto de 2026?**

Inferência não confirmada por fonte primária está marcada **[inferência]**.

---

## 1. Veredito

**A rota está certa e foi corrigida na semana passada; o que não está certo é o
ritmo de execução dela.** Os cinco commits de 30–31/07 são todos código de Fase 1,
e a Fase 0 — o gate que o próprio [plano de 90 dias](plano-90-dias-2026-07-30.md)
declarou bloqueante — não foi executada. A métrica que o plano define como a única
que importa (minutas geradas pelo Causor que um advogado assinou com edição menor)
continua em **zero**, e nenhum commit da semana move esse número.

Nada na pesquisa desta data contradiz as decisões de 29 e 30/07. Duas delas
ficaram **mais** fortes (não reconstruir a camada de dados; tirar o protocolo do
caminho crítico) e uma premissa comercial ficou **mais fraca** (o preço que se
pode cobrar por redação assistida).

---

## 2. Enter — o que é, e por que importa para o Causor

Fatos confirmados por fonte primária/imprensa de negócios:

| Item | Dado |
|---|---|
| Fundação | 2023, São Paulo |
| Série A | set/2025, US$ 5,5M liderada pela Sequoia, valuation US$ 350M |
| Série B | **mai/2026, >US$ 100M liderada pelo Founders Fund** (Peter Thiel), com Sequoia, Ribbit, Kaszek, Atlantico e ONEVC |
| Valuation | **US$ 1,2 bi** — primeiro unicórnio de IA da América Latina; triplicou em 8 meses |
| Volume | **300 mil+ processos/ano** pelo EnterOS |
| Clientes | Itaú, Bradesco, Santander, Nubank, Mercado Livre, Magalu, Latam, Azul, Airbnb |
| Penetração | ~30% dos processos de consumidor dos clientes; projeção de 60% em 12 meses |
| Crescimento | receita 10x e base de clientes 3x desde a Série A |

O produto é **contencioso de massa do lado da defesa**: um agente lê o processo do
consumidor, cruza dados internos da empresa e entrega a defesa pronta para
protocolo, revisada por humano. O EnterOS é vendido como "sistema operacional do
contencioso" para o **réu**.

### 2.1 As quatro leituras

1. **A Enter não é concorrente — é contraparte.** Ela arma o réu; o ICP do Causor
   (escritório pequeno/médio, tipicamente do lado do autor) é o outro polo. Uma
   empresa que sai de 30% para 60% das defesas automatizadas cria assimetria
   estrutural contra o advogado do autor. Foi exatamente essa assimetria que criou
   a **Eve** (US$ 1 bi, escritórios de autor) e a **EvenUp** (>US$ 2 bi) nos EUA.
   **Este argumento comercial não estava escrito em nenhum documento do repositório
   e é o melhor que o Causor tem.**
2. **Virou unicórnio sem construir a camada de dados** (compra da Judit) e **sem que
   protocolar fosse o fosso** — entrega a peça pronta. Confirma as duas decisões
   mais caras da rota de 30/07.
3. **O comprador dela é a empresa, não o escritório.** A imprensa descreve o produto
   como "IA que concorre com escritórios". Se essa lógica atravessar para o lado do
   autor, o cliente do Causor pode ser desintermediado — argumento a favor de fincar
   o Modelo B (software para o escritório) e de escolher uma raia onde o escritório
   pequeno é insubstituível.
4. **O que ela prova é o formato, não a tese específica:** IA faz o trabalho, humano
   revisa, em volume, no Brasil, com capital Tier 1 atrás. Ninguém mais precisa ser
   convencido de que isso funciona aqui — o que muda o roteiro de venda: a objeção
   deixou de ser "IA dá conta?" e passou a ser "por que a sua, e não a que já vem
   junto?".

---

## 3. O fato novo que reprecifica a venda: o Jus IA virou item de plano básico

Em **13/04/2026**, no Jus Brasil Experience (MASP), o Jusbrasil fez a maior
atualização do Jus IA desde o lançamento e **passou a incluí-lo em todos os planos,
sem custo adicional**. São **300 mil advogados/mês** usando. A empresa declara
posicionar IA como infraestrutura do trabalho jurídico, não como ferramenta
acessória.

Contexto de adoção: **76% dos profissionais do Direito usam IA generativa ao menos
uma vez por semana em 2026** (era 55% em 2025).

Consequência direta para o Causor: **qualquer entregável que se pareça com "IA que
redige" é comparado com grátis.** Isso não invalida a tese de 30/07 — reforça a
parte dela que diz que o diferencial está *embaixo* da redação. Mas encurta o prazo
e endurece o discurso: a âncora tem que ser o paralegal (R$ 2,5–4 mil/mês), nunca o
software de gestão, e a demonstração tem que mostrar o que o Jus IA não faz.

**O que o Jus IA e os adjacentes não fazem** (verificado): puxei a página dos
**Agentes de Peticionamento da ADVBOX** (20+ agentes por área do Direito) — é
redação assistida dentro da plataforma; a página **não menciona** cálculo de prazo a
partir da intimação, leitura dos autos completos nem protocolo. Continuo sem
encontrar quem venda **prova de completude dos autos + prazo determinístico
auditável + trilha imutável de supervisão**. O diferencial declarado em
[`viabilidade-mercado-2026-07-29.md`](viabilidade-mercado-2026-07-29.md) segue sem dono.

---

## 4. O mapa global, atualizado (mar–abr/2026)

| Empresa | Valuation | Foco |
|---|---|---|
| **Harvey** | **US$ 11 bi** (mar/2026, US$ 200M) | Pesquisa e redação para grandes bancas |
| **Legora** | **US$ 5,6 bi** (Série D de US$ 600M, abr/2026) | Idem, concorrente direta da Harvey |
| **EvenUp** | **>US$ 2 bi** (Série E de US$ 150M) | Danos pessoais, carta de demanda |
| **Eve** | **US$ 1 bi** | **Escritórios de autor pequenos e médios — o ICP do Causor** |
| **Enter** | **US$ 1,2 bi** | Contencioso de massa, lado da defesa, Brasil |

Legal AI captou ~US$ 4,3 bi em 2025 em 180+ deals. O nicho "lado do autor"
(Eve + EvenUp) soma ~US$ 3,25 bi e virou categoria própria.

O padrão de 30/07 se mantém intacto: **todo vencedor escolheu uma camada e uma
raia.** Nenhum deles é generalista, e nenhum ganhou pelo botão "enviar".

---

## 5. Cinco divergências em relação ao plano vigente

Ordenadas por impacto na métrica que está em zero.

1. **Falta escolher a raia.** Garfield escolheu dívida até £10k; Enter, consumidor
   de massa; Eve e EvenUp, danos pessoais. O Causor continua sendo "qualquer
   intimação, qualquer área" — e é isso que impede a minuta de ser boa o bastante
   para ser assinada sem reescrita, que é o critério de morte escrito no plano de
   90 dias. Escolher a raia é a decisão que mais melhora a métrica.
2. **O upload contradiz o diferencial, e isso está subestimado.** O único caminho de
   captura sem gate externo (`autos/upload.py`, 31/07) produz completude *declarada
   pelo advogado* — exatamente o que não se pode vender como prova. Mitigação barata
   e disponível hoje: cruzar o que foi enviado com os **movimentos do DataJud**
   (nacional, gratuito, cliente já implementado em `capture/datajud.py`) e mostrar a
   divergência. Vira sinal conferido contra fonte independente, em vez de declaração
   pura.
3. **A resposta para "falta de usuário" pode ser melhor que a do plano.** O plano
   aposta num advogado próximo — ponto único de falha de novo, logo depois de perder
   o advisor. Mas o **DJEN é público e nacional**: com o número da OAB já dá para
   montar, sem pedir credencial nenhuma, o quadro real de intimações e prazos de um
   prospect. Tier 1 da demo (intimações + prazo calculado + o que vence esta semana)
   não precisa de nada do advogado; Tier 2 (minuta com citação verificada) precisa de
   **um PDF**. Nenhum concorrente prospecta assim.
   *Guardrail:* pedir o "pode?" do advogado antes de capturar a OAB dele e nunca
   publicar o conteúdo — é dado público, mas a conversa é B2B, não captação.
4. **A Fase 1.3 aberta invalida a promessa comercial.** Sem migration
   `a3e7b1c9d2f8`, SMTP e cron em produção, "você não perde prazo" não é entregável.
   São horas, não dias, e é pré-requisito de qualquer piloto.
5. **O discurso precisa ser reancorado agora que o Jus IA é grátis** (§3).

---

## 6. O que esta pesquisa **não** resolveu

- Não há dado público de receita, churn e CAC de SaaS jurídico para escritório
  pequeno no Brasil — a faixa R$ 500–1.500/mês continua sendo âncora por analogia
  com o paralegal, não observação **[inferência]**.
- Não foi testado se algum concorrente brasileiro já faz cálculo de prazo
  auditável: o material público é marketing, e marketing não distingue "LLM chutou a
  data" de "código determinístico com teste". A ausência de prova aqui é limite do
  método, não prova de ausência.
- A hipótese do §2.1.1 (a automação da defesa cria demanda do lado do autor) é
  raciocínio por analogia com o mercado americano **[inferência]** — plausível, sem
  evidência brasileira direta.

---

## Fontes

- [CNN Brasil — Enter alcança US$ 1,2 bi](https://www.cnnbrasil.com.br/economia/negocios/startup-brasileira-de-ia-juridica-enter-alcanca-us-12-bi-em-valuation/)
- [Forbes Brasil — Série B liderada pelo Founders Fund](https://forbes.com.br/forbes-money/2026/05/startup-juridica-enter-vira-unicornio-de-ia-com-rodada-de-us-100-milhoes-liderada-pelo-founders-fund/)
- [Brazil Journal — Thiel avalia a Enter em R$ 2 bilhões](https://braziljournal.com/the-founders-fund-de-peter-thiel-avalia-a-enter-em-r-2-bilhoes/)
- [Exame — Enter atrai US$ 5,5M da Sequoia (Série A)](https://exame.com/negocios/enter-como-uma-startup-brasileira-de-ia-atraiu-us-55-milhoes-da-sequoia/)
- [InfoMoney — quem é a Enter](https://www.infomoney.com.br/mercados/startups-quem-e-a-enter-unicornio-brasileiro-de-ia-do-setor-juridico/)
- [lightjur — startup de IA que concorre em escritórios](https://lightjur.substack.com/p/startup-de-ia-que-concorre-em-escritorios)
- [Globe Newswire — Enter valorada em US$ 350M (set/2025)](https://www.globenewswire.com/news-release/2025/09/24/3155414/0/es/enter-est%C3%A1-valorada-en-us-350-millones-founders-fund-y-sequoia-apuestan-por-la-legaltech-que-utiliza-ia-para-defender-a-las-grandes-empresas.html)
- [JuriNews — Jusbrasil integra o Jus IA a todos os planos](https://jurinews.com.br/ia/jusbrasil-integra-ia-em-todos-os-planos-para-facilitar-o-acesso-dos-advogados-brasileiros-a-inteligencia-artificial)
- [Jus IA — página oficial](https://ia.jusbrasil.com.br/)
- [ADVBOX — Agentes de Peticionamento](https://advbox.com.br/blog/agentes-de-peticionamento/)
- [PlatinumIDS — Harvey US$ 11 bi, Legora US$ 5,5 bi, corrida de capital 2026](https://blog.platinumids.com/blog/legal-ai-billion-dollar-arms-race-2026)
- [AI Vortex — mapa do mercado de legal AI 2026](https://www.aivortex.io/legal/guides/legal-ai-market-2026-landscape/)
- [Legal Control — legaltech no Brasil em 2026](https://legalcontrol.com.br/legaltech-brasil-2026/)
- [CNJ — peticionamento intercorrente via Jus.br em mais de 1/3 dos tribunais](https://www.cnj.jus.br/mais-de-1-3-dos-tribunais-brasileiros-disponibilizam-peticionamento-intercorrente-via-jus-br/)
