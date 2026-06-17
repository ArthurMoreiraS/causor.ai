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

## Chaves/servicos

- `CAUSOR_DATABASE_URL` - Supabase Postgres.
- `CAUSOR_DATAJUD_API_KEY` - DataJud.
- `ANTHROPIC_API_KEY` - Claude.
- `CAUSOR_SUPABASE_JWT_SECRET` - Supabase Auth/JWT.

## Ainda falta para MVP real

1. Captura agendada em producao: cron chamando `capture-due`.
2. Tela para registrar protocolo final depois do `ready_to_sign`.
3. Vault real no Supabase para sessoes PJe/tokens de provedor.
4. Conector PJe Playwright real para navegar ate a tela de assinatura.
5. Integracao futura com certificado em nuvem, se o piloto exigir envio final
   automatizado.
6. Onboarding real de escritorio/OAB/usuario, sem depender de seed/manual.
7. Alertas de prazo por e-mail ou WhatsApp.

## Decisoes de custo de IA

Nao usar modelos premium em teste. O custo padrao fica:

- Haiku para chat e classificacao.
- Sonnet para minuta.

Modelos mais caros ficam fora do caminho padrao e so devem ser reintroduzidos
se houver uma tarefa juridica que Sonnet nao resolva bem.
