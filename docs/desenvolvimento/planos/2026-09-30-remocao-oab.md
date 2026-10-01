# Remoção da OAB e dados capturados

Prioridade solicitada em 30/09, durante a correção visual. Retomar o plano do
MVP após esta interrupção.

## Evidência

- O modal principal chama `removerOabMonitorada(id, false)`: encerra o cadastro,
  preservando intimações/processos deliberadamente. O fundador corrigiu essa
  expectativa: quer retirar os dados da OAB ao removê-la.
- Configurações chama a mesma API com `purge=true`; comportamentos divergentes.
- `useOabCapture.recover` retoma `jobs[0]`, inclusive de OAB já removida. O modal
  mostra a conclusão antiga e “Verificar agora” sem nenhuma OAB monitorada.
- A limpeza existente infere origem pelos destinatários DJEN. Precisa preservar
  comunicação compartilhada com outra OAB monitorada e dados de outros tenants.
- Remover uma OAB durante captura não pode deixar o worker repovoar seus dados.

## Execução

1. Ocultar e descartar acompanhamento de OAB não monitorada; resposta atrasada
   não restaura feedback. Reabrir modal/atualizar página não recupera conclusão
   antiga. Sincronizar alterações feitas em Configurações.
2. Unificar remoção com limpeza dos dados exclusivos da captura. Confirmar na
   interface o efeito e os limites. Preservar trabalhos, minutas e documentos
   produzidos/anexados pelo usuário, assim como dados compartilhados com outra
   OAB; informar os registros preservados. Não apagar clientes nem auditoria.
3. Oferecer limpeza por número/UF para OAB anteriormente removida, sem exigir
   nova captura. Autorização derivada exclusivamente do escritório autenticado.
4. Atualizar listas, contadores e acompanhamento após sucesso. Impedir publicação
   tardia de captura/análise cancelada pela remoção. Não executar limpeza real
   como teste; entregar ação concreta na aplicação.

## Escopo e verificação

Backend: rotas de OAB/limpeza, dependências de captura, fila e testes. Frontend:
modal, configurações, hook, cliente API e testes. Um executor Sol por vez.

Testes isolados: sem OAB + job histórico, remoção com polling atrasado, OAB
ativa mantém progresso, tenant isolado, comunicação compartilhada, processo
exclusivo removido, trabalho/documento manual preservado, limpeza sem cadastro,
captura em andamento sem recriação de dados. Ruff/pytest dirigido e `pnpm.cmd
check`; concorrência em PostgreSQL descartável no CI. Sem alterações reais no
banco compartilhado para validar. Visual no navegador permanece pendente por
indisponibilidade da ferramenta.
