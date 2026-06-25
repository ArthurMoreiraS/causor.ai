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

- Backend FastAPI com SOR multi-tenant, captura, prazo engine, agente de
  classificacao/minuta, gate de aprovacao, templates, jobs e auditoria.
- Supabase Auth/JWT e Vault como caminhos de producao.
- Frontend Next.js com dashboard, fila do dia, processos, intimacoes, prazos,
  minutas, Gate OAB, conectores, configuracoes e onboarding.
- PJe assistido ate `ready_to_sign`, com confirmacao manual do protocolo.
- Captura agendada com retry limitado, deteccao de jobs interrompidos e falha
  observavel pelo codigo de saida.
- CI de backend e frontend.

## APIs atuais

- `GET /health`
- `GET /me`
- `GET /dashboard/operational`
- `GET /review/queue`
- `GET /processos`
- `GET /intimacoes`
- `GET /prazos`
- `GET /peticoes`
- `GET /jobs`
- `GET /audit`
- `POST /intimacoes/{id}/draft`
- `POST /peticoes/{id}/approve`
- `POST /peticoes/{id}/protocolar/async`
- `POST /peticoes/{id}/protocolar/confirmar`

## Proximas fatias

1. Piloto real: validar captura, prazo, minuta, aprovacao e confirmacao de
   protocolo com um escritorio.
2. Operacao em producao: cron, monitoramento externo e alerta para jobs failed.
3. PJe pilotavel: fechar um unico tribunal/grau/tipo de peticao ate
   `ready_to_sign`.
4. Validar sessoes PJe no Supabase Vault em ambiente publicado.
5. Alertas de prazo por e-mail ou WhatsApp.

## Criterios de validacao

- Capturar pelo menos 90% das intimacoes relevantes nos pilotos.
- Manter prazo correto em pelo menos 99% dos casos testados.
- Gerar minutas aprovadas com edicao minima.
- Provar ROI em horas devolvidas e reducao de risco de prazo.
