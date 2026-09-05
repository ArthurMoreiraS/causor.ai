# Correção da remoção de OAB

O usuário relatou a mensagem genérica de falha do servidor ao remover uma OAB
da conta de teste. Não foram consultados dados privados ou logs dessa conta.
O erro HTTP 500 foi reproduzido em banco descartável com chaves estrangeiras
ativadas: a limpeza tentava excluir `documento` enquanto arquivos, manifestos
e resumos ainda o referenciavam. Instâncias, contexto e notificações de prazo
também não eram tratados pela rotina anterior.

## Alteração

A limpeza agora remove os dependentes antes dos registros principais, dentro
da mesma transação que remove a OAB. Inclui manifestos, trechos, resumos,
versões de arquivo, documentos, capturas, instâncias, contexto, liberações de
contexto e notificações de prazo. Os contadores de documentos evitam contar
duas vezes um documento ligado simultaneamente ao processo e à petição.

Clientes, tarefas e eventos de auditoria permanecem. As tarefas perdem apenas
as referências aos registros removidos, pelas FKs `SET NULL`, mantendo seu
texto de origem. Processos que ainda têm intimações de outra OAB são mantidos,
assim como seus documentos e contexto. `purge=false` continua removendo
somente o monitoramento.

Os jobs removidos agora exigem o escritório correto no payload, inclusive
quando duas contas acompanham a mesma OAB. Jobs sem identificação do
escritório são preservados. Jobs da OAB também são limpos quando ainda não
existe intimação capturada. A identificação abrange os arquivos removidos,
evitando deixar processamento documental enfileirado para esses registros.

Não há alteração de esquema nem remoção de objetos físicos do storage.
A limpeza mantém o comportamento anterior de retenção dos objetos; coleta
de arquivos sem referência exige uma política própria. O caso de captura
externa já em execução durante a remoção não foi homologado nesta correção.

## Validação

Antes da correção: três falhas reproduzidas (500 por FK, job de outro escritório
removido e job próprio retido sem intimações). Depois: 20 testes direcionados
de limpeza/auditoria/tarefas passaram; outros 22 cenários de OAB/auditoria da
API também passaram, com Ruff aprovado. Seis cenários novos entram na matriz
PostgreSQL 16/17 do CI. Nenhuma OAB real foi removida pelo agente.

O [CI da versão ad9bfb6](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33945481355)
aprovou **676 testes gerais backend, 42 em cada PostgreSQL (16/17), 75 frontend**,
lint, tipos e build Linux. Os 48 testes pulados na suíte geral correspondem
aos 42 PostgreSQL executados separadamente e aos seis cenários opt-in.

O [deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33945546116)
concluiu em 05/09 às 01h53 (Brasília), verificando a versão exata `ad9bfb6`
no backend, worker, autos-worker e frontend, todos saudáveis. O usuário pode
repetir a remoção na aplicação; não foi executada uma exclusão em sua conta.
