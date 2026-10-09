# Prazo por tipo de ato não substitui prazo escrito

Data: 09/10/2026. Achado pela bancada da Jev
([plano](2026-10-09-jev-bancada.md)) numa captura real em produção.

## Problema

Intimação real: "apresentar contrarrazões aos Embargos de Declaração… no prazo
de 5 (cinco) dias, conforme… art. 1.023, § 2º". O Causor pôs em vigor 15 dias
de agravo interno pelo tipo de ato. Duas causas:

1. **Teor HTML.** 46 de 90 intimações da captura chegam com marcação e
   entidades (`contrarraz&otilde;es`). O modelo cita o trecho decodificado e a
   conferência literal de `supported()` nunca o encontrava no teor cru.
2. **Recaída no tipo de ato.** Quando o prazo escrito não é confirmado (trecho
   não encontrado, regra legal recusada porque o teor fala em dias, ou campos
   que o Haiku varia entre chamadas), o pipeline aplicava a duração padrão do
   ato, que pode ser maior que a real. O motivo da recusa era sobrescrito.

## Mudança

- `capture/text.html_to_text`: o pipeline interpreta e confere sobre o teor
  em texto. O teor gravado e o `source_hash` não mudam.
- `deadline_interpretation.written_durations`: durações escritas ("5 (cinco)
  dias", "quinze dias").
- `pipeline.run_analysis`: se o teor tem um número de dias diferente do prazo
  do tipo de ato, vai para a triagem com o motivo explícito. Prazo judicial
  confirmado continua tendo prioridade. `motivo_verificacao` guarda a recusa.
- `ANALYSIS_VERSION` 3 → 4: o agendador reanalisa sozinho "pendente" e "sem
  prazo identificado" automáticos sem prazo criado (cerca de US$ 0,005 cada).
  **Prazos já criados não são refeitos** (regra existente).

## Evidência

- Local: `tests/test_prazo_por_ato.py` (3 testes novos, os 2 do erro falhavam
  antes); suíte completa 788 passed, ruff limpo.
- Reprodução com Haiku real dos 40 prazos em vigor da captura de 09/10, em
  SQLite em memória: 33 iguais; #2571 passou a 5 dias; #2512 (Causor dava 5,
  teor diz 15) foi à triagem; 2 alarmes falsos esperados (90 dias de stay
  period; 5 dias do relator, art. 932); 2 casos mudaram por variação do Haiku.
- Não implantado. Não validado juridicamente.

## Pendências

- Prazos por tipo de ato já em vigor com número de dias diferente no teor
  continuam no banco; na conta de teste os 5 afetados já venceram. Revisar à
  mão ou decidir uma reanálise dirigida.
- A regra é conservadora: qualquer número de dias diferente no teor manda à
  triagem, inclusive prazos de outra pessoa (relator, stay period).
