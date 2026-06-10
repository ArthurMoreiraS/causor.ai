# Causor Product Blueprint

## Tese

Causor e um SaaS de agentes operacionais para escritorios juridicos brasileiros. O produto nao compete como monitor de publicacoes; o diferencial e executar o fluxo operacional completo:

1. capturar intimacoes por fontes oficiais;
2. enriquecer processos no System of Record;
3. calcular prazos de forma deterministica;
4. gerar minuta com IA;
5. exigir aprovacao humana;
6. protocolar em sistemas judiciais com conectores controlados.

## Cliente inicial

Escritorios pequenos e medios no Brasil, de advogados autonomos ate equipes com cerca de 50 advogados. A dor principal e perda de tempo operacional e risco de perda de prazo.

## Principios do produto

- APIs oficiais antes de scraping: DJEN/Comunica e DataJud sao a base da captura.
- Prazo nao e LLM: contagem e calendario forense ficam em codigo deterministico e testado.
- IA interpreta e redige: Claude classifica o ato, sugere peca e gera minuta.
- Gate humano obrigatorio: protocolo e ato irreversivel e exige aprovacao do advogado.
- Segredos fora de prompts: certificado, senha e assinatura ficam no vault.
- Auditoria imutavel: cada passo do agente precisa virar evento rastreavel.

## Superficies implementadas

- Backend FastAPI com SOR, captura, prazo engine, agente de classificacao/minuta, gate de aprovacao e API operacional.
- Frontend Next.js com dashboard de operacao, modo demo para pilotos, workflow visual, conectores, fila de aprovacao e sinais de auditoria/seguranca.
- Infra local com Postgres e Redis.

## APIs atuais

- `GET /health`
- `GET /dashboard/operational`
- `GET /processos`
- `GET /intimacoes`
- `GET /prazos`
- `GET /peticoes`
- `POST /intimacoes/{id}/draft`
- `POST /peticoes/{id}/approve`
- `POST /peticoes/{id}/protocolar`

## Proximas fatias

1. PJe pilotavel: conector Playwright para login, localizar processo e preparar protocolo, ainda com aprovacao humana.
2. Vault: armazenamento seguro de referencia de certificado em nuvem e bloqueio total de segredo em prompt/log.
3. Auditoria real: tabela `audit_log` preenchida por toda acao de captura, minuta, aprovacao e protocolo.
4. Templates do escritorio: minutas por tipo de ato e area juridica.
5. Multi-tenant minimo: isolamento por escritorio, usuario e OAB.
6. Onboarding de piloto: cadastro de escritorio, OAB, tribunal inicial e status de conectores.

## Criterios de validacao

- Capturar pelo menos 90% das intimacoes relevantes nos pilotos.
- Manter prazo correto em pelo menos 99% dos casos testados.
- Gerar minutas aprovadas com edicao minima.
- Provar ROI em horas devolvidas e reducao de risco de prazo.
