# Prazo automático depois da captura por OAB

Data: 07/10/2026. Decisão do fundador: quanto menos o advogado precisar dar
sinal verde, melhor. Referência de mercado: produto concorrente que pega a OAB,
traz intimação e processo, calcula o prazo e avisa sozinho.

## Problema

- A análise de prazo já roda sozinha após a captura, mas só o resultado
  "calculado" vira `Prazo`. O incerto ("Informar prazo") fica parado na tela de
  Intimações, sem data, sem alerta.
- Prazo calculado não "vale" até o advogado confirmar: não pode ser cumprido
  (409), não conta no risco do painel, aparece como "a revisar".
- `notificar-prazos` existe, mas nenhum serviço de produção o executa. Nenhum
  aviso sai.
- Reanálise com o catálogo novo e repetição de falha dependem de clique.

## Decisões (07/10, fundador)

1. Incerto ganha **data de triagem**: 5 dias úteis da publicação DJEN (menor
   prazo supletivo, CPC art. 218, § 3º); no rito criminal, 2 dias úteis (menor
   prazo comum, embargos de declaração, CPP art. 619). Rotulada como "prazo real
   não identificado"; nunca apresentada como o prazo do ato.
2. Prazo **calculado vale sem confirmação**: entra no risco, no alerta e pode
   ser cumprido. A conferência continua disponível e opcional.
3. Aviso por **e-mail agora**; WhatsApp depois, como outro `AlertSender`.

## Escopo

Backend
- `prazo_engine.pipeline`: status `triagem` (versão 3 da análise); falha conta
  tentativas e, após 3, vira triagem; `requeue_analyses` reenfileira análises
  desatualizadas, falhas e intimações nunca analisadas, em lote.
- `capture.service` (agendador): a cada ciclo, captura + reanálise + aviso
  (aviso só com SMTP configurado e entre 7h e 21h de Brasília).
- `alertas.notificacao`: nível `novo` (prazo criado nas últimas 48h e ainda não
  vencido) além de D-3/D-1/D-0/vencido; texto distingue calculado, triagem e
  confirmado.
- API: cumprir sem confirmação; contadores de risco usam prazo vigente
  (confirmado ou calculado).

Frontend
- Prazo calculado mostra data e contagem normalmente; triagem tem selo próprio.
- Intimações: abas "Precisam de você / Sem prazo / Todas", ordenadas por
  vencimento; sem botão de análise manual; "Preparar minuta" some quando não há
  prazo.

## Aceite

- Testes: incerto cível → triagem 5 dias úteis; criminal → 2 dias úteis; 3
  falhas → triagem; reanálise automática de versão antiga; aviso `novo` enviado
  uma vez; cumprir prazo calculado sem confirmar.
- `pytest`, `ruff`, `pnpm check`, `pnpm build` verdes.
- Em produção: definir `CAUSOR_SMTP_HOST`, `CAUSOR_SMTP_USER`, `CAUSOR_SMTP_FROM` e
  `CAUSOR_SMTP_PASSWORD` no `.env` da VPS (lido pelo `capture-scheduler`).
