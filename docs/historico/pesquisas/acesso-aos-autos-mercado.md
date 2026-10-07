# Como o mercado resolve o acesso aos autos (Enter, Judit, Escavador)

Pesquisa de 2026-07-22. Este arquivo responde a uma pergunta específica:
**como a Enter — o primeiro unicórnio de IA do Brasil, jurídico — resolve o
problema de ter os autos completos do processo para gerar peças?** A resposta
define o que o Causor deve e não deve construir.

Fontes ao final. Onde a informação é inferência e não afirmação pública, está
marcado como **[inferência]**.

---

## 1. Resposta curta

**A Enter não resolve o problema de captura. Ela compra a solução pronta.**

A camada de dados processuais é terceirizada para a **Judit**, que mantém a
infraestrutura de coleta em 100+ tribunais. A Enter concentra 100% da
engenharia na camada de inteligência aplicada — o EnterOS, que lê, cruza,
calcula acordo e redige.

Isso não é um detalhe de implementação: é a tese. O texto da própria Judit
generaliza o padrão para Enter (BR), Harvey (EUA) e Legora (Suécia) — nenhuma
delas construiu vantagem competitiva na camada de dados; todas
"terceirizaram a complexidade dos dados para quem já a resolveu".

## 2. Quem é a Enter e por que o problema dela é diferente do nosso

- Fundada em 2023 por ex-executivos da Wildlife Studios (Mateus
  Costa-Ribeiro, Michael Mac-Vicar, Henrique Vaz).
- Unicórnio em maio de 2026, rodada de ~R$ 500 mi.
- **Nicho: contencioso de massa, lado do réu.** Clientes: Bradesco, Nubank,
  Mercado Livre, Itaú, Santander, Magazine Luiza, LATAM, Azul, Airbnb.
- Volume: **300 mil+ processos/ano** pelo EnterOS.
- Modelo de receita: fixo pelo uso + ~30% variável atrelado ao êxito.

**A diferença que mais importa para o Causor:** a Enter opera processos
*repetitivos e padronizados* em que o cliente é **parte** e tem estrutura
jurídica própria. O site dela declara ser "API-connected to courts, your legal
ERP and internal systems" — ou seja, boa parte do contexto **não vem do
tribunal**: vem dos sistemas internos do próprio cliente ("Enter surfaced
unstructured data from hundreds of thousands of internal documents").

Um banco processado 50 mil vezes já tem o contrato, o extrato e o log de
atendimento em casa. O escritório pequeno de 3 advogados **não tem nada disso**
— para ele, o autos do tribunal *é* a única fonte de verdade. O problema do
Causor é estruturalmente mais difícil no ponto exato onde a Enter é mais fácil.

## 3. Como a Judit funciona (a camada que a Enter compra)

Arquitetura em três serviços:

| Serviço | Host | Função |
|---|---|---|
| Requests | `requests.prod.judit.io` | Consultas assíncronas (dispara e busca depois) |
| Lawsuits | `lawsuits.production.judit.io` | Datalake de processos, consulta síncrona |
| Tracking | `tracking.prod.judit.io` | Monitoramento contínuo com webhook |

- **Busca por**: CPF, CNPJ, OAB, nome, número CNJ.
- **Cobertura**: Estadual, Federal, Trabalhista, Eleitoral, Militar, Superiores,
  BNMP. 100+ tribunais.
- **Rate limit** padrão: 500 req/min.
- **Como coleta**: frota de robôs de navegador parametrizados por tribunal,
  com proxies e resolução de CAPTCHA em escala. Não é MNI; é scraping
  industrializado. **[inferência parcial — o modelo é descrito publicamente
  como robôs, mas o mix exato com APIs oficiais não é divulgado]**

### 3.1 Anexos — o ponto que mais interessa ao Causor

O fluxo de documentos é explicitamente **segunda classe** em relação aos
metadados:

1. Criar a consulta com `with_attachments: true`.
2. `GET /transfer-file` lista os arquivos disponíveis com IDs.
3. `GET /transfer-file/{id}` devolve URL assinada de download.

Limitações declaradas pela própria Judit:

- **"Nem todos os tribunais disponibilizam anexos publicamente."**
- Só funciona com `search_type: "lawsuit_cnj"` (busca por número CNJ).
- **Cada anexo coletado é cobrado à parte.**
- Cada anexo tem um campo `status` (`done` quando obtido) — ou seja, **o
  próprio contrato da API admite que anexos podem não vir**.

### 3.2 Cofre de credenciais — validação do desenho do Causor

A Judit mantém um **"Cofre de Credenciais"** com criptografia end-to-end, e a
regra é clara: **processos em segredo de justiça só são acessíveis com
credencial do advogado cadastrada no cofre.**

Isso é a validação de mercado da mudança de política que o Causor fez em
`1d4d5eb` (remoção da exigência de custódia exclusiva). O líder de
infraestrutura de dados jurídicos do Brasil guarda credencial de advogado no
próprio cofre porque **não existe outro jeito** de ler processo sigiloso. O
Causor guardando a senha do credenciamento MNI no vault do backend é o mesmo
desenho, com uma credencial *menos* poderosa.

## 4. O que a Judit **não** vende — e é exatamente o nosso moat

| Capacidade | Judit | Causor |
|---|---|---|
| Metadados e movimentos | ✅ | via DataJud (grátis) |
| Lista de anexos | ✅ (cobrado por anexo) | via MNI / agente |
| **Garantia de completude do conjunto** | ❌ nenhuma promessa | ✅ enumeração dupla + SHA-256 + gate fail-closed |
| **Protocolo (peticionamento)** | ❌ não vende | ✅ é o produto |
| Cálculo de prazo determinístico | ❌ | ✅ `prazo_engine` |

Dois buracos, e os dois são o Causor:

1. **Completude.** Em nenhum lugar da documentação a Judit promete "você
   recebeu o processo inteiro". Ela entrega *conveniência* (formato único),
   não *prova de integridade*. Para contencioso de massa isso é aceitável —
   errar 2% de 300 mil processos é ruído estatístico absorvido pelo modelo de
   êxito. Para o escritório de 3 advogados, faltar uma peça = minuta errada =
   prazo perdido = malpractice. **O Plano 2 do Causor é uma barra mais alta
   do que a do mercado, no único ponto em que o cliente pequeno não pode
   errar.**
2. **Ação.** Nenhum vendor de dados protocola. Judit, Escavador, Digesto,
   Jusbrasil — todos param na leitura. O `entregarManifestacaoProcessual` do
   MNI é a única porta oficial e gratuita para o ato irreversível, e é onde o
   Causor se diferencia de "mais um monitorador".

## 5. Por que copiar a Judit é a estratégia errada para o Causor

O custo real da Judit não é a assinatura da API — é a **operação contínua** que
ela financia com escala enterprise:

- Um framework de scraping parametrizado por tribunal (100+ perfis, cada um
  com layout, login e paginação próprios).
- Frota de proxies residenciais.
- Resolução de CAPTCHA em escala.
- Uma equipe que conserta quebras **todo dia**, porque tribunal muda layout
  sem avisar.

Isso é um produto inteiro, não uma feature. Replicá-lo com um piloto de poucos
processos significa parar de construir o diferencial (integridade + protocolo)
para reconstruir a commodity que já existe — e reconstruí-la pior, sem a
escala que paga a manutenção.

Além disso, colidiria com a restrição não-negociável #4 do `AGENTS.md`
(*API oficial antes de scraping*), que existe justamente porque scraping em
massa é frágil e juridicamente cinzento.

## 6. A leitura estratégica para o Causor

**A Enter provou que a camada de dados não é onde está o valor.** Ela virou
unicórnio comprando dados e vendendo inteligência. O erro seria concluir
"então o Causor também deve comprar" — porque o Causor atende um cliente cujo
problema a compra **não resolve**:

- O escritório pequeno não tem ERP interno para enriquecer o contexto.
- Ele não tolera captura incompleta.
- Ele precisa que alguém **protocole**, não que alguém avise.

A conclusão certa é: **o Causor precisa da fatia da Judit que cobre 1–2
tribunais do piloto — e o MNI entrega essa fatia por R$ 0.** O que o Causor
constrói em cima (prova de completude + prazo determinístico + protocolo com
gate humano) é exatamente o que nenhum dos dois vende.

Escada de acesso aos autos, da melhor opção ao fallback:

1. **MNI** — oficial, gratuito, padronizado pelo CNJ, entrega documentos *e*
   protocola. Custo: um ofício de credenciamento.
2. **Agente local** — o computador pareado do advogado, com a credencial dele.
   Cobre tribunal sem MNI e faz o protocolo hoje.
3. **Vendor pago (Judit/Escavador)** — só se um tribunal do piloto falhar nos
   dois caminhos acima **e** o cliente justificar o custo. Nunca como base da
   arquitetura.

## 7. O que confirmar (lacunas honestas desta pesquisa)

- A Enter usa MNI em algum ponto? Não há informação pública. Grandes
  litigantes tipicamente têm integração MNI própria com os tribunais.
  **[inferência]**
- O mix exato de scraping vs. API oficial da Judit não é divulgado.
- Preço por consulta/anexo da Judit e do Escavador não é público — exige
  contato comercial. Não use estimativa em decisão de arquitetura.
- Taxa real de sucesso de anexos por tribunal: nenhum vendor publica.

---

## Fontes

- [Enter: A startup jurídica brasileira que virou unicórnio de IA — JUDIT](https://judit.io/blog/noticias/enter-unicornio-ia-judit/)
- [ENTER — Agentes de IA para contencioso de massa](https://www.getenter.ai/en)
- [Judit API — Documentação Oficial](https://juditdocs.mintlify.app/introduction/introduction)
- [Baixe automaticamente anexos de processos judiciais — JUDIT](https://judit.io/blog/api-judit/download-automatico-anexos-processos-judiciais/)
- [Quem é a Enter, unicórnio brasileiro de IA do setor jurídico — InfoMoney](https://www.infomoney.com.br/mercados/startups-quem-e-a-enter-unicornio-brasileiro-de-ia-do-setor-juridico/)
- [Enter e a softwareização do jurídico: promessas e riscos — Roberto Dias Duarte](https://www.robertodiasduarte.com.br/enter-e-a-softwareizacao-do-juridico-promessas-e-riscos/)
- [Enter: como uma startup brasileira de IA atraiu US$ 5,5 milhões da Sequoia — Exame](https://exame.com/negocios/enter-como-uma-startup-brasileira-de-ia-atraiu-us-55-milhoes-da-sequoia/)
- [Modelo Nacional de Interoperabilidade — Portal CNJ](https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/comite-nacional-de-gestao-de-tecnologia-da-informacao-e-comunicacao-do-poder-judiciario/modelo-nacional-de-interoperabilidade/)
- [API Escavador Business](https://www.escavador.com/business/api)
