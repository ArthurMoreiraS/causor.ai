# Viabilidade do Causor — pesquisa de mercado de 2026-07-29

Pesquisa feita para responder a uma pergunta direta do fundador: *"estamos no
caminho correto? o produto é viável?"*. Este arquivo é a **fonte** dos quatro
achados que corrigem premissas do `produto/PRD.md`, do `estado.md` e do
`mni-credenciamento.md`.

Onde algo é inferência e não afirmação de fonte primária, está marcado
**[inferência]**. Fontes ao final.

---

## 1. Resposta curta

O problema é real, o mercado é real e os ativos construídos servem. **Mas o
fosso declarado — "nós protocolamos, os outros só monitoram" — é a parte mais
fraca da tese**, e não por dificuldade técnica:

1. O canal **oficial** de protocolo (MNI) é juridicamente desenhado para
   **órgão público**, não para CNPJ privado.
2. O canal **não oficial** (RPA em portal) está sob repressão ativa e
   documentada dos tribunais, com bloqueio de credencial e comunicação à OAB.
3. Quem já protocola em escala no Brasil tem posição institucional que uma
   startup não compra: a **doc9** por cima e o **marketplace da própria OAB**
   por baixo.

O que sobra depois de tirar o protocolo do centro **ainda é um produto** — e é
um produto que a pesquisa não encontrou à venda em ninguém. Ver §6.

---

## 2. Achado 1 — o MNI para protocolo é gated a instituições

Quatro fontes independentes apontam para o mesmo lugar. Nenhuma delas diz
"empresa privada não pode"; todas descrevem um desenho em que ela não caberia.

| Fonte | O que diz |
|---|---|
| **Termo de Adesão MNI — STF (VF 2024)** | Só aderem órgãos **com credenciamento prévio do art. 246 §2 do CPC**: administração direta e indireta, MP, Defensoria e Advocacia Pública |
| **TRF6 — página oficial do MNI (v. 2.2.3)** | Pedido via SEI exigindo CNPJ, **IP público**, "Gestor de Negócio" com **matrícula funcional**, e-mail institucional e **documento formal de delegação de competência** |
| **eproc / TRF4** | O webservice MNI é descrito como autorizado apenas a **órgãos que compõem a estrutura do Poder Judiciário** |
| **Docs do PJe — Serviço MNI Client** | `entregarManifestacaoProcessual` é exposto a **sistemas** portadores da role `invoke-service-endpoint`, concedida pelo tribunal — não a usuário final |

E o fecho institucional: o CNJ **já resolveu isso para o advogado** por outro
caminho — o **Escritório Digital** (CNJ + Conselho Federal da OAB, sobre MNI:
consulta processo, **envia petição**, ajuíza nova demanda, recebe intimação,
controla prazo; gratuito; em expansão na Justiça Federal em 2026, com STJ, TRF2
e TRF5 aderindo). Existe um intermediário oficial entre advogado e MNI, ele é
institucional, e ele não é uma API para terceiros.

**Consequência para o roadmap.** A premissa registrada até aqui — *"falta só o
credenciamento (ofício gratuito à DTI)"* — trata como fila burocrática algo que
pode ser um "não" estrutural. Isso muda a leitura do bloqueio atual: talvez não
seja o advisor demorando; seja a premissa.

**Como falsificar (barato, faça antes de mais código):** pedir resposta
**escrita** a duas DTIs de tribunal e a `integracaopdpj@cnj.jus.br`, na forma
*"pessoa jurídica de direito privado, fornecedora de software de gestão para
advogados, pode obter credencial MNI para `consultarProcesso` e
`entregarManifestacaoProcessual` em nome de advogado habilitado nos autos?"*.
Sim ou não, a resposta vale mais que qualquer linha de código. Checklist em
[`mni-credenciamento.md`](mni-credenciamento.md) §0.

### 2.1 Sinal lateral: quem consegue assinar acordo com tribunal

O **iJUD Peticiona**, do marketplace **da própria OAB** (Central da
Advocacia), vende "protocolar em qualquer tribunal, **sem necessidade de
certificado digital**", a partir de **R$ 19,90/mês**, com liberação
*"progressiva conforme acordos de cooperação técnica com os tribunais e o
CNJ"*. A cobertura real hoje é provavelmente ínfima **[inferência]**, mas o
recado estrutural é claro: quem assina ACT com tribunal é a OAB e o CNJ.

---

## 3. Achado 2 — o caminho RPA está sob repressão ativa

- **TJMA**: mais de **800 mil acessos indevidos em 5 horas** (06/06/2025), por
  robôs RPA via perfis de usuário externo. O tribunal **bloqueou as
  credenciais** usadas (09/06/2025). Base citada: Res. CNJ 185/2013 e Termo de
  Uso do PJe.
- **TRT-6 (20/03/2026, vigente desde 21/03/2026)**: bloqueio **automático** de
  quem consultar mais de **1.500 processos de terceiros em 30 dias**, com
  e-mail ao advogado **e à seccional da OAB**. Base: Res. CNJ 185/2013 art. 29
  e Res. CSJT 185/2017 art. 10-A. Reincidência pode gerar bloqueio permanente.
- **TRT-4** na mesma linha; **TJRS** publica que "acesso robotizado a dados
  públicos é duplamente arriscado".

**A nuance que preserva o Causor:** o gatilho dessas regras é consulta a
processo **de terceiro**. O Causor lê a carteira do próprio advogado, onde ele
está habilitado — não cai nesse critério. Duas coisas seguem verdadeiras
mesmo assim:

1. O diferencial passa a ser "automação que o tribunal tolera" — uma permissão
   que não controlamos e que pode mudar por portaria.
2. Para um produto cuja promessa é *"você não perde mais prazo"*, ter a
   credencial do cliente bloqueada com cópia para a OAB é o pior modo de falha
   possível. Isso é argumento **a favor** do agente local (credencial e máquina
   do próprio advogado, volume igual ao de um humano) e **contra** qualquer
   coleta centralizada em nome de muitos advogados.

---

## 4. Achado 3 — o fosso já tem dono nas duas pontas

A frase do PRD — *"o concorrente de monitoramento resolve só a primeira
linha"* — não se sustenta em 2026:

| Player | O que já faz |
|---|---|
| **doc9 / Task.doc9** | ~**600 mil operações automatizadas/mês**; cobertura Estadual + Federal + Trabalhista, 1º ao 3º grau; inclui **peticionamentos intermediários** e habilitações |
| **doc9 / Whom.doc9** | 1º gestor de certificado digital em nuvem do Brasil, permissão por robô/tribunal/horário, ISO 27001, +3.000 empresas — **R$ 1,5 mil a R$ 10 mil/mês** |
| **iJUD / OAB** | Protocolo multi-tribunal a partir de R$ 19,90/mês |
| **ADVBOX** | "Agentes de Peticionamento" (IA para redação de peças) |
| **Inspira, ForeLegal, Aurum** | Ecossistemas de agentes jurídicos anunciados em jun/2026 |
| **Enter** | US$ 100M, valuation US$ 1,2 bi (mai/2026), automatizando litígio "do início ao fim" |

Leitura: o preço do protocolo automatizado está sendo definido por baixo
(R$ 19,90, OAB) e a governança de identidade digital jurídica por cima
(R$ 1,5–10 mil/mês, doc9, com ISO 27001). Não há faixa confortável no meio para
vender *só* protocolo.

---

## 5. Achado 4 — a custódia delegada encosta na única parede legal dura

A **MP 2.200-2/2001** é explícita: o titular do certificado **não pode ceder,
emprestar ou compartilhar**, e não há como repudiar o ato assinado. A
flexibilização de custódia decidida em 2026-07-21 (commit `1d4d5eb`) resolve
uma amarra de engenharia, mas aponta exatamente para esse ponto.

Registro do fato, não reabertura da decisão: a resposta que o mercado achou
**não** foi delegar a credencial, foi **custódia gerenciada** com permissão por
robô, por tribunal e por horário, mais auditoria — e isso é vendido a
R$ 1,5–10 mil/mês com ISO 27001. A versão "delegada" desse problema é um
produto caro e certificado, não um atalho.

---

## 6. O que sobra — e ninguém vende

Três capacidades que a pesquisa **não** encontrou à venda em nenhum
concorrente brasileiro:

1. **Prova de completude dos autos.** Judit, Escavador e Digesto entregam
   conveniência (formato único), não integridade — a própria API da Judit admite
   anexo que pode não vir. Ver [`acesso-aos-autos-mercado.md`](acesso-aos-autos-mercado.md) §3.1.
2. **Prazo determinístico auditável** num mundo DJEN + Domicílio Judicial
   Eletrônico pós-Res. CNJ 455/2022 e 569/2024 (confirmação em 3 dias úteis,
   prazo começando no 5º dia útil seguinte, dois canais com naturezas
   distintas). A regra ficou *mais* difícil, não menos.
3. **Trilha imutável de supervisão humana** — o artefato que responde à OAB, ao
   cliente e ao seguro. O Conselho Federal da OAB lançou em **10/06/2026** o
   Plano Nacional de IA na Advocacia, com Código de Boas Práticas e a diretriz
   de que *"o advogado e a supervisão humana permanecem como peças centrais"*.
   Este é o único item da lista que fica **mais** valioso com o tempo.

### 6.1 Dois precedentes que definem o formato certo

- **Eve** (EUA, escritórios de autor pequenos/médios — o ICP do Causor) virou
  unicórnio com US$ 103M e valuation >US$ 1 bi fazendo intake, análise, resumo
  médico, minuta e discovery. **Ela não protocola.** É a evidência mais forte
  de que o botão "enviar" não é o fosso; a preparação confiável do trabalho é.
- **Garfield.Law** (Reino Unido, mai/2025) é o primeiro escritório de IA
  autorizado pela **SRA**: protocola de verdade, mas com aprovação do cliente
  em **cada passo procedimental**, combinando LLM com sistema determinístico e
  com solicitor nomeado responsável por toda saída. É, literalmente, a
  arquitetura do Causor — chancelada por um regulador.

---

## 7. Âncoras de preço e de ROI

- Software jurídico de gestão no Brasil: **R$ 197 a R$ 1.000+/mês** por
  escritório (NextCase, Projuris ADV, ADVBOX, Astrea).
- Protocolo por correspondente jurídico: **R$ 80 a R$ 150 por ato**.
- Paralegal: ordem de **R$ 2,5 a 4 mil/mês** all-in **[inferência]** — é a
  âncora certa, porque é o que o produto substitui.
- Mercado: **1,3 milhão+** de advogados inscritos na OAB, **>60%** autônomos ou
  em escritórios pequenos; AB2L saiu de ~20 para **+600** legaltechs; ~R$ 2 bi
  investidos no setor nos últimos 18 meses.

Conclusão de preço: a R$ 19,90 competimos com a OAB e perdemos. O Causor tem
espaço em **R$ 500–1.500/mês por escritório** — mas só se o entregável for "o
dia de trabalho resolvido", não "o clique automatizado".

---

## 8. Recomendação

**Continuar o produto. Parar o caminho crítico atual.**

1. **O piloto não precisa de MNI nem de conector novo.** DJEN/DataJud já rodam
   ao vivo; o agente local lê os autos com a credencial do próprio advogado;
   prazo, minuta, gate e auditoria estão prontos. O protocolo sai como está
   hoje: `ready_to_sign` + o advogado confirma o envio. Isso não é degradação —
   é o desenho da Garfield.Law aprovado pela SRA.
2. **O MNI vira aposta paralela com teste de viabilidade primeiro** (§2), não
   caminho crítico. Custo do teste: dois e-mails.
3. **Reposicionar o fosso.** De *"nós protocolamos"* para: *"entregamos o
   trabalho do dia pronto, com os autos comprovadamente inteiros, o prazo
   calculado de forma auditável e a trilha que prova que o advogado
   supervisionou"* — com o protocolo como último metro, feito pelo agente local
   com a credencial do próprio advogado, sob gate.
4. **Critério de morte, escrito antes de começar.** 2–3 escritórios, 30 dias,
   intimações reais. Se as minutas forem reescritas do zero **e** o motor de
   prazos não pegar nada que o escritório teria perdido, o produto não está lá
   — e nenhum conector conserta isso.

### 8.1 O risco que não é técnico nem competitivo

Nenhum escritório real usou o Causor ainda. São 450 testes, cliente SOAP de
MNI, prova de completude por SHA-256, e **zero** intimações reais de um
escritório real transformadas em minuta que um advogado aceitou. O protocolo
virou a justificativa técnica para adiar a pergunta comercial.

---

## 9. Lacunas honestas desta pesquisa

- **Não** foi encontrado nenhum caso documentado de empresa privada **obtendo**
  credencial MNI — mas também **nenhuma negativa explícita**. São quatro fontes
  apontando na mesma direção, não uma vedação escrita. Por isso a ação
  recomendada é um e-mail, não uma conclusão.
- Cobertura real do iJUD Peticiona hoje: não divulgada.
- Se a doc9 atende escritório pequeno: o preço do Whom.doc9 sugere médio/grande,
  mas o Task.doc9 no marketplace (R$ 89,90/mês + pay-per-use) sugere que sim.
  Não confirmado.
- Churn e CAC reais de SaaS jurídico para escritório pequeno no Brasil: sem
  dado público.

---

## Fontes

- [Termo de Adesão MNI para Tribunais — STF (VF 2024)](https://www.stf.jus.br/arquivo/cms/processoIntegracaoInformacaoGeral/anexo/TermodeAdesoMNIparaTribunaisVF2024.pdf)
- [MNI — Portal STF](https://portal.stf.jus.br/textos/verTexto.asp?servico=processoIntegracaoInformacaoGeral&pagina=mni)
- [MNI / integração — TRF6](https://portal.trf6.jus.br/institucional/tecnologia-da-informacao/solucoes-de-tecnologia-da-informacao/modelo-nacional-de-interoperabilidade-integracao/)
- [Serviço MNI Client — Documentação PJe](https://docs.pje.jus.br/servicos-auxiliares/servico-mni-client/)
- [Escritório Digital — como funciona (CNJ)](https://www.cnj.jus.br/sistemas/escritorio-digital/como-funciona/)
- [Tribunais federais aderem ao Escritório Digital (CNJ)](https://www.cnj.jus.br/tribunais-federais-aderem-ao-escritorio-digital-para-integrar-comunicacao/)
- [TJMA alerta sobre acessos massivos indevidos ao PJe/MA](https://www.tjma.jus.br/midia/portal/noticia/517946/tjma-alerta-sobre-acessos-massivos-indevidos-ao-pjema)
- [TRT-6 bloqueará usuários do PJe-JT com consultas excessivas (20/03/2026)](https://www.trt6.jus.br/portal/noticias/2026/03/20/trt-6-bloqueara-usuariosas-do-pje-jt-que-realizem-consultas-excessivas-processos)
- [TRT-RS bloqueará usuários do PJe com consultas excessivas](https://www.trt4.jus.br/portais/trt4/modulos/noticias/320926)
- [Acesso robotizado a dados públicos é duplamente arriscado — TJRS](https://www.tjrs.jus.br/novo/processos-e-servicos/processo-eletronico/acesso-robotizado-a-dados-publicos-e-duplamente-arriscado/)
- [RPA nos tribunais: seria o fim da era dos RPAs? — doc9](https://doc9.com.br/blog/rpa-automacao-nos-tribunais/)
- [Task.doc9 — automação jurídica integrada ao Whom.doc9](https://doc9.com.br/blog/doc9-expande-ecossistema-juridico-com-task-doc9/)
- [DOC9 — preços e funcionalidades (B2B Stack)](https://www.b2bstack.com.br/product/doc9)
- [Certificado digital: emprestar é perigoso — Jusbrasil](https://www.jusbrasil.com.br/noticias/certificado-digital-emprestar-e-perigoso/100156653)
- [iJUD Peticiona — Central da Advocacia / marketplace OAB](https://ijud.com.br/produto/ijud-peticiona/)
- [Agentes de Peticionamento — ADVBOX](https://advbox.com.br/blog/agentes-de-peticionamento/)
- [Inspira leva IA jurídica a escritórios e advogados autônomos — TI Inside](https://tiinside.com.br/05/06/2026/inspira-leva-ia-juridica-a-escritorios-e-advogados-autonomos/)
- [Enter vira unicórnio com US$ 100 mi — Forbes Brasil](https://forbes.com.br/forbes-money/2026/05/startup-juridica-enter-vira-unicornio-de-ia-com-rodada-de-us-100-milhoes-liderada-pelo-founders-fund/)
- [Eve levanta US$ 103M a valuation de US$ 1 bi — LawSites](https://www.lawnext.com/2025/09/eve-ai-driven-platform-for-plaintiff-side-law-firms-raises-103-million-in-series-b-round/)
- [SRA aprova o primeiro escritório de IA (Garfield.Law)](https://news.sra.org.uk/news/news/press/2025-press-releases/garfield-ai-authorised/)
- [SRA authorizes UK's first AI-based law firm — Dechert](https://www.dechert.com/knowledge/re-torts/2025/6/solicitors-regulation-authority-authorizes-uk-s-first-ai-based-l.html)
- [OAB anuncia Plano Nacional de IA na advocacia (10/06/2026)](https://www.oab.org.br/noticia/64268/conselho-federal-da-oab-anuncia-plano-nacional-para-integrar-inteligencia-artificial-a-advocacia)
- [Resolução CNJ nº 335/2020 (PDPJ-Br)](https://atos.cnj.jus.br/atos/detalhar/3496)
- [Documentação PDPJ-Br](https://docs.pdpj.jus.br/)
- [Domicílio Judicial Eletrônico obrigatório a PJ — Migalhas](https://www.migalhas.com.br/depeso/431782/domicilio-judicial-eletronico-obrigatorio-a-pj-em-todos-os-tribunais)
- [Intimação eletrônica, DJEN e segurança jurídica — ConJur (20/05/2026)](https://www.conjur.com.br/2026-mai-20/intimacao-eletronica-djen-e-seguranca-juridica/)
- [Perda de prazo: responsabilidade civil do advogado — Projuris](https://www.projuris.com.br/blog/perda-de-prazo-responsabilidade-civil/)
- [STJ aplica teoria da perda de uma chance](https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/07042022-STJ-aplica-teoria-da-perda-de-uma-chance-e-condena-escritorio-de-advocacia-por-desidia-em-acao-.aspx)
- [Comparativo AdvBox × Astrea × Projuris 2026 — Seasy](https://seasy.host/2026/04/02/advbox-vs-astrea-vs-projuris-adv-software-juridico-2026/)
- [Preços e planos ADVBOX](https://advbox.com.br/planos)
- [Quanto custa um correspondente jurídico em 2026 — Juris](https://blog.juriscorrespondente.com.br/quanto-custa-contratar-um-correspondente-juridico-em-2026-guia-completo-de-valores-por-tipo-de-diligencia/)
- [Mercado da tecnologia jurídica prospera no Brasil — AB2L](https://ab2l.org.br/noticias/mercado-da-tecnologia-juridica-prospera-no-brasil/)
