# Proximos passos - MVP

## Onde estamos

- SOR + prazo engine deterministico implementados.
- Captura real via DJEN/Comunica + DataJud funcionando.
- Supabase Postgres e Supabase Auth funcionando com `causorai@gmail.com`.
- Backend valida JWT, isola por `escritorio_id` e o frontend envia Bearer token.
- IA roda em Claude:
  - chat operacional: `claude-haiku-4-5`;
  - classificacao de intimacao: `claude-haiku-4-5`;
  - redacao de minuta: `claude-sonnet-4-6`.
- PJe assistido iniciado: protocolo prepara ate `ready_to_sign`; assinatura/envio
  final ainda fica com o advogado no PJe/PJeOffice.
- Captura agendada possui retry exponencial limitado, recuperacao de jobs
  interrompidos e codigo de saida nao-zero em falha definitiva.
- CI valida Ruff, pytest, Vitest e build do Next.js.
- Testes do frontend cobrem autenticacao HTTP e os principais contratos do
  fluxo de captura, prazo, aprovacao e protocolo assistido.

## Chaves/servicos

- `CAUSOR_DATABASE_URL` - Supabase Postgres.
- `CAUSOR_DATAJUD_API_KEY` - DataJud.
- `ANTHROPIC_API_KEY` - Claude.
- `CAUSOR_SUPABASE_JWT_SECRET` - Supabase Auth/JWT.

## Ainda falta para MVP real

1. Executar um piloto ponta a ponta com OAB e dados reais.
2. Configurar em producao o cron que chama `capture-due` e alertar quando seu
   codigo de saida for diferente de zero.
3. Validar o Vault Supabase para sessoes PJe/tokens no ambiente publicado.
4. Fechar um unico conector PJe Playwright real ate a tela de assinatura,
   escolhendo tribunal, grau e tipo de peticao do piloto.
5. Integracao futura com certificado em nuvem, se o piloto exigir envio final
   automatizado.
6. Adicionar monitoramento externo do backend, cron e jobs `failed`.
7. Alertas de prazo por e-mail ou WhatsApp.

## Ordem de execucao

1. Publicar backend e frontend com CI verde.
2. Provisionar o primeiro escritorio conforme `onboarding-piloto.md`.
3. Ativar o cron e acompanhar ao menos dois ciclos de captura.
4. Validar captura, prazo e minuta com o advogado.
5. Escolher o primeiro cenario PJe e concluir um protocolo assistido real.

Nao ampliar para novos tribunais, billing ou RAG antes dessa validacao.

## Decisoes de custo de IA

Nao usar modelos premium em teste. O custo padrao fica:

- Haiku para chat e classificacao.
- Sonnet para minuta.

Modelos mais caros ficam fora do caminho padrao e so devem ser reintroduzidos
se houver uma tarefa juridica que Sonnet nao resolva bem.
