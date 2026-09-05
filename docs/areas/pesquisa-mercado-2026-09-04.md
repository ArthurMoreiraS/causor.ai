# Mercado e alternativas de integração para o Causor

Pesquisa consultada em 04/09/2026. Foco: decisões viáveis para uma pessoa desenvolvendo um produto para escritórios brasileiros. Fontes comerciais descrevem o que o fornecedor anuncia; não constituem homologação independente de desempenho ou cobertura.

**Recomendação:** construir a preparação e a revisão do trabalho jurídico; aproveitar APIs oficiais para as informações que realmente entregam; comparar fornecedores para os autos e a execução; manter no máximo um conector próprio em validação por vez. Nenhum fornecedor foi contratado ou contatado nesta pesquisa.

## 1. O que aprender com a Enter

A Enter descreve integração com tribunais, ERPs e sistemas internos, leitura dos autos e subsídios e preparação de textos apoiados em evidências. Seu foco público são departamentos jurídicos de grandes empresas e contencioso de massa. A lição útil para o Causor é que **os autos não contêm necessariamente todas as informações necessárias à defesa**. Contratos, comprovantes e fatos do cliente também precisam entrar no trabalho. [Produto da Enter](https://www.getenter.ai/).

Na frente trabalhista, a empresa apresenta integração com RH, documentos como holerites e registros de ponto e engenheiros dedicados ao cliente. Isso sugere uma combinação de software, integração e implantação especializada, cujo custo de atendimento não deve ser copiado automaticamente por um fundador solo. [Enter Trabalhista](https://www.getenter.ai/trabalhista).

A Judit afirma fornecer a infraestrutura processual usada por empresas como a Enter. É uma declaração do próprio fornecedor: sustenta investigar compra de dados, mas não revela toda a arquitetura da Enter, contratos, exclusividade ou forma de protocolo. [Relato da Judit](https://judit.io/blog/jurisprudencia-casos-judiciais/enter-unicornio-ia-judit/).

**Não foi estabelecido nesta pesquisa se a Enter oferece protocolo final automatizado, em quais tribunais ou por qual canal.** Tampouco é possível concluir que nenhuma dessas empresas construiu tecnologia própria de captura. Evitar transformar ausência de documentação pública em prova de inexistência.

## 2. Mapa competitivo por trabalho executado

| Produto | Oferta pública relevante | Implicação para o Causor |
|---|---|---|
| Enter | Autos, subsídios empresariais e apoio ao contencioso | Aprender a montar evidências e especializar o fluxo; não copiar o atendimento enterprise. [Fonte](https://www.getenter.ai/) |
| Judit | API de consulta, monitoramento, anexos e credenciais | Candidata à camada de dados, também possui produto voltado ao usuário final. [Documentação](https://docs.judit.io/introduction/introduction) |
| Escavador | Consulta por OAB, atualizações, autos públicos/restritos e certificados | Segunda candidata para comparação no mesmo conjunto de processos. [Documentação](https://api.escavador.com/v2/docs/) |
| Task.doc9 | Captura, cópias integrais, protocolo, comprovante e revisão humana | Protocolo e auditoria já são ofertas comerciais. Investigar integração e preço por ato. [Produto](https://doc9.com.br/task/) |
| iJUD Peticiona | Peticionamento anunciado a partir de R$ 19,90/mês | Referência de oferta ao advogado; não assumir que a assinatura inclui API, revenda ou todos os tribunais. [Oferta](https://ijud.com.br/produto/ijud-peticiona/) |
| Jus IA | Pesquisa, elaboração, análise documental, memória e validação de citações conforme plano | “Gerar petição com IA” enfrenta concorrência direta de produtos já distribuídos. [Planos](https://ia.jusbrasil.com.br/planos) |
| Jurídico AI | Redação no estilo do escritório, documentos por caso, teses e jurisprudência com fonte | Estilo, histórico e referências já fazem parte da competição; precisam ser úteis, não somente existir como botões. [Produto](https://juridico.ai/) |
| Astrea | Detecção de prazo em publicações e inclusão revisada pelo usuário | Calendário e triagem não são território vazio; clareza sobre confirmação é parte do produto. [Central de ajuda](https://astrea.aurum.com.br/pt-BR/articles/13869214-como-funciona-a-deteccao-inteligente-de-prazos-no-astrea) |
| Projuris ADV | IA integrada, resumos de intimações e sugestões de prazos/atividades | Avaliar integração com a rotina existente do escritório em vez de exigir substituir toda sua gestão. [Oferta](https://store.projuris.com.br/products/projuris-ia-1) |
| Eve | Pesquisa dentro do caso com referências abertas para conferência | Referência de experiência de trabalho baseada em fontes, em outro mercado. [Produto](https://www.eve.legal/use-cases/eve-research) |
| EvenUp | Fluxos especializados de personal injury, documentos, demandas e organização de evidências | Especialização e detecção de lacunas são referências; não evidência de adaptação ao Brasil. [Produto](https://www.evenuplaw.com/) |

As capacidades acima são anunciadas pelos fornecedores. Não medi precisão, satisfação, disponibilidade, segurança ou retorno financeiro deles. Estatísticas promocionais e valuations não foram usados para estimar receita do Causor.

## 3. Como obter os autos

### A. DJEN e DataJud: manter, com escopo correto

A API pública do DataJud entrega metadados de processos públicos. Ela é adequada para identificação, movimentos e enriquecimento; não substitui o conteúdo de contratos, laudos e decisões que formam os autos. [CNJ: acesso à API pública](https://datajud-wiki.cnj.jus.br/api-publica/acesso/).

A captura por OAB no DJEN deve continuar como fonte de publicações. Como decisão de produto, o onboarding também precisa de uma lista inicial da carteira: importação de números CNJ, planilha do escritório ou busca contratada. Processos sem publicação no período não podem simplesmente desaparecer da promessa de monitoramento.

DJEN, comunicações pessoais e autos são três objetos diferentes. Não chamar a captura do primeiro de cobertura integral dos outros dois.

### B. Judit: testar o documento baixado, não só o JSON

A documentação descreve consulta assíncrona, distinção entre retorno de cache e atualização, anexos com status e `with_attachments`. Há limite de captura de 1.000 anexos por requisição, com repetição cobrada para lotes seguintes. Os arquivos podem manter formatos como PDF, HTML, DOCX, imagem e mídia. Isso exige um adapter que baixe bytes, verifique status, persista a origem e trate formatos não suportados. [Consulta e anexos](https://docs.judit.io/requests/requests).

O cofre admite credenciais do advogado, sujeitas às permissões existentes no tribunal e às exigências de autenticação de cada fonte. Isso não cria acesso a documentos que o advogado não pode consultar. [Cofre da Judit](https://docs.judit.io/essentials/cofre-de-credenciais).

### C. Escavador: atualização e paginação fazem parte da coleta

O endpoint de autos devolve uma lista paginada de documentos presentes na base. A documentação exige atualização anterior com `autos=1` e status `SUCESSO` para acesso aos autos restritos. Não basta consultar a lista uma vez e assumir que ela representa a última versão do tribunal. [Autos do processo](https://api.escavador.com/v2/docs/consulta-de-processos).

A API de certificados recebe arquivo `.pfx`/`.p12`, senha e configuração de autenticação. A escolha envolve onboarding, permissões, custódia e revogação concretos. [Certificados](https://api.escavador.com/v2/docs/certificados-digitais).

### D. Upload: ponte prática e permanente

Reaproveitar o upload existente como primeira forma de entrada. Ele permite avaliar a minuta antes de resolver a automação dos portais. Deve continuar disponível depois de contratar fornecedor, para documento faltante, prova externa ou fonte indisponível.

A integralidade é declarada pelo advogado; só chamar de conferida contra o tribunal quando existir uma enumeração externa pertinente. Processos anexados em um PDF único precisam de índice por peça/evento, preservando as páginas do original.

### E. MNI: depende do acesso, não apenas do WSDL

O TRF6 descreve credenciamento via ofício e requisitos institucionais, incluindo gestor e identidade funcional. Isso sustenta tratar o acesso como dependência a confirmar; não prova uma proibição universal para qualquer empresa privada em qualquer tribunal. [TRF6: integração MNI](https://portal.trf6.jus.br/institucional/tecnologia-da-informacao/solucoes-de-tecnologia-da-informacao/modelo-nacional-de-interoperabilidade-integracao/).

Preservar o código já feito, com ativação somente após credenciamento e entrega de documentos reais. Não investir em `MniFilingDriver` com base apenas em operação listada no schema.

## 4. Como protocolar

Há três opções para testar quando o primeiro recorte estiver definido:

| Opção | Vantagem | O que precisa demonstrar |
|---|---|---|
| Fornecedor de execução, como doc9 | Reduz manutenção própria de portais | API ou integração contratável, tribunal/grau/ato, revisão, recibo, preço, prazo de atendimento e tratamento de falhas |
| Jus.br assistido | Pode concentrar parte da operação do advogado | Ato disponível para o tribunal, login/assinatura, anexos, campos específicos e confirmação final |
| Conector próprio Playwright | Controle de um fluxo específico | Funcionamento com conta autorizada, retomada, limites, comprovante e custo de manutenção |

A doc9 anuncia protocolo com comprovante integrado e logs, mas não foi verificada uma API pública de protocolo pronta para contratação self-service. Não confundir isso com sua API de logística. Uma demonstração deve percorrer exatamente o ato do piloto. [Task.doc9](https://doc9.com.br/task/).

O Jus.br é uma oportunidade, não prova de conector universal. A notícia de **39 tribunais é de 02/04/2025**, não uma medição de setembro de 2026. A documentação de integração é orientada aos tribunais e contempla particularidades, protocolo do portal e confirmação posterior do sistema judicial. Uma interface unificada não garante API pública para SaaS nem elimina a necessidade de reconciliação. [Notícia datada do CNJ](https://www.cnj.jus.br/mais-de-1-3-dos-tribunais-brasileiros-disponibilizam-peticionamento-intercorrente-via-jus-br/), [documentação do peticionamento](https://docs.pdpj.jus.br/servicos-negociais/portal-servicos/pet-intercorrente/).

**Playwright continua sendo uma ferramenta adequada para passos conhecidos.** A decisão de arquitetura proposta é usá-lo dentro de uma máquina de estados com pós-condições: processo certo, documentos certos, preparo concluído, aprovação vinculada, envio e recibo. Um modelo com computer use pode auxiliar em exceções ou interpretação de tela, mas não deve ser a única confirmação de que o ato foi praticado.

Não presumir que sessão local autoriza toda automação; acesso, limites e termos são validados para a rota escolhida. CAPTCHA, MFA e assinatura permanecem passos explícitos de intervenção quando exigidos. Não repetir envio após timeout sem antes verificar se houve protocolo.

## 5. Domicílio Judicial e custódia: corrigir generalizações antigas

A documentação do Domicílio descreve API para instituições consumirem expedientes destinados a elas. Também apresenta acesso web do advogado a representados. Essas duas informações não bastam para concluir que uma chave do CNPJ do Causor acessa toda a carteira de todos os advogados. A abertura de comunicação com efeito de ciência deve ser tratada como ação distinta de listar metadados. [Documentação oficial](https://docs.pdpj.jus.br/servicos-negociais/domicilio-judicial-eletronico/).

A pesquisa anterior atribuiu à MP 2.200-2 uma proibição com palavras que não são o texto literal. O art. 6º, parágrafo único, estabelece controle, uso e conhecimento exclusivos da chave privada pelo titular. Compatibilidade de cada solução de assinatura/custódia depende de seu desenho e regras aplicáveis; não se resolve por um slogan de armazenamento local ou em nuvem. [Texto da MP](https://www.planalto.gov.br/ccivil_03/mpv/antigas_2001/2200-2.htm).

## 6. Preços: o que foi confirmado e o que falta

- **Jus IA:** a página oferece planos pagos e promoção de primeiro mês, com limites distintos. “Incluído nos planos” não significa gratuito e ilimitado. A própria central descreve a incorporação da IA aos planos de pesquisa. [Planos](https://ia.jusbrasil.com.br/planos), [mudanças nos planos](https://suporte.jusbrasil.com.br/hc/pt-br/articles/48184895977236-O-que-mudou-nos-planos-do-Jusbrasil).
- **Judit:** plataforma para usuário e API são produtos diferentes. A página atual de API apresenta contratação anual e pré-paga e uma tabela dinâmica; não consegui estabelecer preço unitário efetivo para os autos do piloto. Não reutilizar o preço antigo da plataforma como custo da API. [API](https://judit.io/planos-api/), [plataforma](https://judit.io/planos-plataforma/).
- **iJUD:** há oferta a partir de R$ 19,90/mês. Cobertura, franquia, integração e direitos de uso pelo Causor precisam ser demonstrados. Esse preço não serve sozinho para precificar backend de protocolo. [Oferta](https://ijud.com.br/produto/ijud-peticiona/).
- **Escavador, doc9 e Enter:** esta pesquisa não estabeleceu orçamento contratual para o cenário do Causor.

Sem carteira e volume definidos, uma previsão de custo total ou margem seria inventada. Comparar:

`custo por providência aprovada = dados + OCR + LLM + armazenamento + execução + revisão/retrabalho + suporte alocado`

O custo de construir inclui horas do fundador, manutenção, homologação e incidentes. O de comprar inclui franquia mínima, cobrança de tentativas, atualização e anexos. O preço comercial deve ser testado depois de medir tempo economizado, não inferido de valuation de concorrentes.

## 7. Experimento de compra versus construção

Quando houver um advogado parceiro, escolher 10–20 processos autorizados do mesmo recorte, incluindo processo com poucos documentos, processo longo, PDF escaneado, documento restrito, recurso e atualização recente, se existirem na carteira.

Enviar a cada fornecedor a mesma especificação de demonstração, sem enviar credenciais por e-mail: disponibilizar dados por canal apropriado somente após avaliar a contratação. Pedir:

1. Documentos efetivamente baixáveis, inventário e origem, não apenas capa e andamentos.
2. Prova de tratamento de paginação, anexos pendentes e instâncias relacionadas.
3. Cobertura exata por tribunal, sistema, grau, ato e tipo de documento.
4. Atualidade, cache, prazo de coleta e política de reprocessamento.
5. Custos de consulta, anexos, retries, franquia, setup e cancelamento.
6. Para protocolo: uma demonstração do preparo, aprovação, envio e recibo do mesmo ato, com ambiente e autorização adequados.
7. Revogação de acesso, tratamento de dados, exportação e possibilidade de integração/revenda no SaaS.

Comparar recuperação das peças relevantes contra a lista conferida pelo advogado, taxa de tarefas concluídas sem ajuda do fundador, latência e custo. Não contratar anuidade apenas com apresentação comercial.

## 8. Tese de produto a testar

“Você recebe a providência organizada, confere os documentos que sustentam a peça, revisa uma minuta aderente ao caso e acompanha o envio até o comprovante.”

Essa é uma hipótese de valor, não exclusividade comprovada. Auditoria, fontes e revisão já aparecem em concorrentes. A vantagem possível do Causor é executar um recorte melhor, com menos retrabalho, acesso conveniente aos documentos e integração à rotina do escritório. A evidência decisiva será uso recorrente e disposição de pagar, não a ausência de uma feature na página de um concorrente.
