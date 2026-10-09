# Jev: bancada contra a análise de prazo

Data: 09/10/2026. Etapa 1 de 3; as etapas 2 e 3 só começam se esta passar.

## Por quê

A Jev (TypeSafe AI, `jev-latest`) é um modelo de decisão: recebe texto e
perguntas fechadas e devolve probabilidades calibradas, sem gerar texto. Ela
não substitui o Claude. Pode ajudar em dois pontos:

1. `supported()` em `agent/deadline_interpretation.py` põe o prazo em vigor
   com base na confiança que o próprio Haiku declara (`confianca >= 0.85`),
   um número não calibrado.
2. `select_draft_context()` em `agent/context_selection.py` ordena os trechos
   dos autos por palavras em comum.

A HAQQ relatou ganho em reordenação de trechos jurídicos (63,8% → 85,0% no
primeiro resultado) e falha ao avaliar se uma citação é fundamentada só pelo
texto. Nenhum teste publicado foi em português. Fonte:
<https://www.haqq.ai/blog/jev-legal-ai-hallucination-detection.html>.

## Escopo desta etapa

`app/agent/jev.py` (cliente) e `app/agent/jev_bancada.py` (CLI). Nada muda em
produção, no banco ou no fluxo de prazo.

```powershell
# backend/
./.venv/Scripts/python.exe -m app.agent.jev_bancada exportar   # leitura, transação READ ONLY
./.venv/Scripts/python.exe -m app.agent.jev_bancada rodar      # chama a Jev; retomável
# rotular artifacts/evals/jev/rotulos.csv (Excel, separador ;)
./.venv/Scripts/python.exe -m app.agent.jev_bancada relatorio
```

Cinco perguntas por intimação, numa chamada: prazo expresso, múltiplos atos,
exige providência (sim/não), natureza do ato e rito (escolha, no mesmo
vocabulário do catálogo `prazo_engine/atos.py`). A Jev **só alerta**: um
alerta mandaria o prazo em vigor para a triagem, nunca o contrário.

A planilha de rótulos é às cegas (não mostra a Jev): metade dos casos com
alerta, metade sorteada. Rótulos: `s`/`n`/`na`, ato e rito pelos códigos do
catálogo.

## Critério de aceite

Com 50 a 100 intimações rotuladas por advogado:

- a Jev alerta na maioria dos prazos em vigor que o rótulo diz estarem
  errados; e
- alerta à toa em poucos dos certos, num nível que o fundador aceite como
  custo de triagem.

Uma amostra assim é diagnóstico, não taxa de acerto.

## Dados e segredos

- A chave fica em `CAUSOR_JEV_API_KEY` no `.env`, lida na hora da chamada;
  nunca em `settings`, log ou git.
- As intimações do DJEN são públicas, mas vão para servidor nos EUA (TypeSafe).
  Autorizado pelo fundador em 09/10 para esta bancada. Trechos de autos
  (etapa 3) exigem antes a leitura do DPA e da retenção de dados.
- Os arquivos ficam em `backend/artifacts/evals/jev/`, fora do git.

## Evidência

- Local: `tests/test_jev_bancada.py`.
- API real, 09/10: três intimações fictícias, 3/3 respondidas, cerca de 330 ms
  cada, US$ 0,0001. O alerta "sem providência" disparava em sentença; agora
  vale só para prazo judicial expresso.
- Bancada com intimações reais, 09/10: OAB nova capturada em produção, 90
  intimações (40 prazos em vigor, todos pelo tipo de ato), 90/90 respondidas,
  mediana 296 ms, US$ 0,013. A Jev alertou em 19 dos 40. Rótulos pendentes.
- **Achado na produção (sem rótulo ainda):** #2571 pede contrarrazões a
  embargos de declaração em 5 dias (CPC, art. 1.023, § 2º); o Causor pôs em
  vigor 15 dias de agravo interno pelo tipo de ato. A Jev marcou "prazo
  escrito no teor" (0,98). Reprodução local com Haiku: o trecho citado pelo
  modelo vem decodificado ("contrarrazões") e o teor do DJEN guarda entidades
  HTML ("contrarraz&otilde;es"), então a conferência literal falha; com o teor
  decodificado ela passou em 2 de 3 casos. O Haiku também variou `termo` entre
  chamadas no mesmo texto. 46 das 90 intimações têm entidades HTML. Todas as
  9 com esse alerta têm data fatal já vencida (publicações antigas da
  recaptura). Correção do pipeline de prazo é decisão separada.

## Próximas etapas (condicionais)

2. Segunda opinião em `supported()`, só para mais cautela, com registro na
   auditoria.
3. Reordenação dos trechos em `select_draft_context()`, comparada no caso real.
