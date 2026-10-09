# Jev no produto: três fases

Data: 09/10/2026. Sucede a [bancada](2026-10-09-jev-bancada.md). Cada fase
precisa de aprovação do fundador antes de começar.

Regras que valem para todas as fases:

- A Jev **nunca** calcula, muda ou libera prazo, e nunca aprova nada. Ela
  acrescenta avisos ou ordena; a decisão continua no código determinístico e
  na pessoa.
- Falha ou ausência da Jev (sem chave, fora do ar) não muda o resultado: o
  fluxo segue como hoje.
- A chave fica em `CAUSOR_JEV_API_KEY`, lida na hora da chamada.

## Fase 1: avisos na intimação e no prazo (dados públicos)

**Estado (09/10):** implementada. Aviso no painel da intimação e selo
"Conferir ato" na lista de intimações (a lista de prazos abre o mesmo
painel). Testes do backend e do frontend; chamada real à Jev com duas
intimações fictícias (com e sem dois atos), cerca de 0,8 s cada. Em produção
só vale depois de `CAUSOR_JEV_API_KEY` no `.env` da VPS e só para análises
novas; as já feitas não ganham aviso.

**Por quê.** A bancada achou textos com mais de um ato ou parte em 9 dos 40
prazos em vigor (6 com probabilidade ≥ 0,9). Hoje nada avisa o advogado disso.

**O quê.**
- Depois da interpretação do Haiku, fora da transação, uma chamada à Jev com
  as perguntas da bancada. Resultado em `_causor_prazo.jev` (modelo,
  probabilidades). Um aviso quando `multiplos_atos ≥ 0,9`: "O texto parece
  trazer mais de um ato ou parte; confira a qual o prazo se refere."
- Na tela de confirmação do prazo e na lista de prazos, o aviso aparece
  como selo neutro. Não muda status, data nem triagem.
- Só teor do DJEN, que é público.

**Aceite.** Testes com a Jev simulada (com aviso, sem aviso, Jev falhando,
sem chave). Em produção: numa captura nova, cada intimação analisada tem o
campo `jev`, e o aviso aparece em cerca de 10–20% dos prazos. O fundador
confere 10 avisos lendo o texto, uma pergunta simples ("há mais de uma
ordem?"), sem exigir análise jurídica.

**Custo.** Cerca de US$ 0,00015 por intimação (US$ 0,15 a cada mil).

**Implantação.** Adicionar `CAUSOR_JEV_API_KEY` ao `.env` da VPS.

## Fase 2: ordem dos trechos dos autos para a minuta

**Por quê.** `select_draft_context` ordena os trechos por palavras em comum. É
o uso com a melhor evidência publicada (HAQQ: 63,8% → 85,0% no primeiro
resultado). Afeta a qualidade da minuta, não o custo.

**Bloqueio.** Os trechos dos autos podem estar em segredo de justiça e iriam
para servidor nos EUA. **Antes de qualquer código:** confirmar por escrito com
a TypeSafe o contrato de tratamento de dados (DPA), a retenção (ZDR ou prazo)
e que não há treino com dados do cliente.

**O quê.** Nota da Jev para cada trecho candidato contra a providência do
trabalho; a regra de um trecho por documento e os trechos fixados continuam.
Falha da Jev → ordem atual.

**Aceite.** No caso fictício e no primeiro caso real: lista de trechos antes e
depois lado a lado e as duas minutas; o fundador ou o advisor escolhe a
melhor sem saber qual é qual.

## Fase 3: a Jev manda prazo para a triagem

Só com rótulos de advogado: 20 a 30 linhas de `r_prazo_causor_correto` na
planilha da bancada, preenchidas pelo advisor. Sem isso, não há como saber
quantos prazos certos ela tiraria de vigor.

## Fora do plano

- **Escolha automática do resumo aprofundado:** o padrão já é o Haiku; a Jev
  só poderia promover documentos ao Sonnet, o que **aumenta** o custo. Não
  economiza.
- **Substituir o Haiku na interpretação do prazo:** a Jev não devolve número
  de dias nem trecho citado, que o Causor exige.
