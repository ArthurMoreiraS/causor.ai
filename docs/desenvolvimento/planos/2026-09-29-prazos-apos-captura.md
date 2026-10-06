# Cálculo automático de prazos após captura

Estado: implementação parcial suspensa para consolidação do plano solicitada
pelo fundador em 29/09. Este escopo técnico integra o
[plano do fluxo simplificado](2026-09-29-fluxo-mvp-simplificado.md).
Somente uma função isolada foi iniciada; captura e UI ainda não estão integradas.

## Resultado e escopo

Captura concluída deve disparar análise persistente das intimações e produzir
contagem automática quando os parâmetros forem sustentados pelo teor. O usuário
não deve preencher todos os parâmetros de todas as publicações para iniciar o
fluxo. Falta de informação, múltiplos prazos/partes ou regime não suportado ficam
com motivo de revisão explícito. Não reaplicar 15 dias a toda comunicação.

Pesquisar regras oficiais, implementar e revisar os resultados.
Escopo permitido: módulos backend capture, prazo_engine, agent de interpretação,
queue/worker, API/schemas, modelos apenas se necessário, testes; frontend tipos,
captura, intimações, prazos, confirmação e indicadores. Reusar fila e provider
Claude de classificação. Não modificar protocolo, autos ou algoritmo legado de
minutas fora da compatibilidade necessária. Não executar análise em massa real
como teste nem sobrescrever prazos humanos. Sem commit/push pelo executor.

## Arquitetura e aceites

- Etapa de análise em jobs persistentes separados da captura, com tenant,
  auditoria, deduplicação e progresso/status. Falha de IA não desfaz captura.
- Captura registra/enfileira intimações novas e também as ainda não analisadas
  quando reencontradas; não repetir sucessos nem sobrescrever revisão humana.
  Prover ação explícita para analisar as já capturadas sem recapturar o DJEN.
- Interpretação identifica duração, regime, termo inicial e trecho da fonte;
  validar trecho contra texto real. Sem prova suficiente ou confiança, marcar
  pendência. Não usar LLM para somar datas. Suportar primeiro DJEN cível em dias
  úteis; outros regimes/ciência pessoal/edital/audiência não recebem cálculo
  desse caminho por engano. Vários comandos/prazos não viram um único prazo.
- Separar disponibilização, publicação e primeiro dia contado. Calendário de
  publicação não é calendário de suspensão da contagem (recesso CPC). Criar
  função específica se necessário, preservando semântica dos cálculos legados.
- Corrigir baseline nacional: inspeção da dependência instalada em 29/09 mostrou
  que Brazil().holidays(2026) omite 20/11. Incluir explicitamente desde 2024,
  conforme Lei 14.759/2023 (publicada em 22/12/2023), com testes de vigência.
  Não acrescentar feriados locais presumidos ao calendário nacional.
- Salvar memória: datas, duração, unidade, evidência, fundamento, versão/regra,
  calendário usado e lacunas locais. Feriados/suspensões locais ainda não
  homologados exigem indicação explícita de revisão; data calculada não vira
  confirmação jurídica silenciosa.
- Persistir status calculado_a_revisar / pendente / sem_prazo_identificado /
  falha e apresentar na UI, inclusive durante o processamento. Prazos
  calculados automaticamente devem estar distinguíveis dos confirmados em
  lista, detalhe e badge. Reusar JSON sob namespace próprio na intimação é
  permitido para evitar migração se isso preservar a fonte e garantir
  persistência/isolamento; não confundir metadados com payload do CNJ.
- Confirmação humana aproveita a sugestão e pode corrigir parâmetros/calendário;
  atualiza o mesmo prazo com auditoria, sem criar duplicata. Prazos históricos
  não são descartados silenciosamente nem confundidos com novos vencimentos.
- O pipeline automático deve funcionar nos registros sem contexto dos autos;
  não esperar geração de minuta. Não prometer completude dos calendários.
- Worker deve atender o novo tipo sem segurar captura HTTP, recuperar falhas
  explícitas, limitar chamadas/retries e não deixar job eternamente running.

## Testes obrigatórios

TDD para cálculo DJEN: sexta->segunda publicação->terça contagem, feriado,
recesso na publicação/contagem, duração ausente, baixa confiança, múltiplos atos,
fonte sem trecho, regime não suportado. Integração simulada captura -> job ->
prazo a revisar -> confirmação -> nova captura sem duplicar; falha IA e retry;
tenant e concorrência PostgreSQL. UI automática, pendência e revisão com refresh.
Executar pytest/ruff e pnpm check; build no CI (não usar .next do dev ativo).

## Referências a conferir

- CNJ: https://www.cnj.jus.br/cnj-alerta-tribunais-sobre-novas-regras-de-contagem-de-prazos-processuais/
- CPC arts. 219, 220, 224: https://www2.camara.leg.br/legin/fed/lei/2015/lei-13105-16-marco-2015-780273-normaatualizada-pl.html
- Resolução CNJ 569: https://atos.cnj.jus.br/atos/detalhar/5691
- Lei 14.759/2023: https://www2.camara.leg.br/legin/fed/lei/2023/lei-14759-21-dezembro-2023-795091-publicacaooriginal-170522-pl.html

Testes simulados não homologam uma contagem real. Próximo aceite real deve
comparar memória calculada e calendário do tribunal com conferência do advogado.
