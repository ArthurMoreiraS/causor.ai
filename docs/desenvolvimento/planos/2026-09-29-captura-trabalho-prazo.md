# Captura: feedback, novo trabalho e revisão de prazo

Estado: implantado (`83e4914`); cálculo automático pós-captura não faz parte desta correção.

## Evidência e objetivo

O fundador confirmou que a captura funciona, mas o indicador fica parado,
Novo trabalho parece não funcionar e intimações chegam sem prazo.
O commit cab194d foi implantado em 28/09: CI 36493631376 e deploy 36493774462
aprovados; API /health 200 e OpenAPI com request_id confirmados. Publicação
não equivale a avaliação jurídica; o fundador confirmou recebimento dos dados.

poll_oab deliberadamente não cria prazo sem duração/termo inicial. Existe
POST /intimacoes/{id}/prazo e ConfirmarPrazo, mas a descoberta desse caminho
e atualização do painel precisam ser corrigidas. A regra matemática não muda.
O CSS global neutraliza animações com prefers-reduced-motion.
TrabalhosView usa selectWork(null), que pode manter campos/retomada anterior.
Há alteração não concluída de recuperação de 401 em frontend/lib/api.ts.

## Contrato do executor

Um worker Sol, sem delegação adicional, commit ou deploy. Escopo: frontend
api/auth e testes para finalizar 401; página, sidebar, TrabalhosView e testes
de Novo trabalho; indicador/CSS de captura; ConfirmarPrazo/DetailDrawer/lista
de intimações para revisão acessível e refresh. Reusar o endpoint de cálculo
existente. Não inferir data fatal de toda publicação ou presumir duração.

- Preservar AGENTS.md, .codex e arquivos de reunião/plano preexistentes.
- Concluir recuperação de 401: no máximo uma renovação compartilhada, uma
  repetição com token novo; segunda recusa encerra sessão local e permite login.
  Timeout continua limitado; não deslogar outros dispositivos, não expor tokens.
- Indicador gira normalmente; em movimento reduzido oferece feedback animado
  suave e mantém texto de progresso, sem reativar todas animações do site.
- Novo trabalho abre formulário limpo, remove seleção/URL antiga e dá foco
  claro, inclusive quando o formulário já estava aberto. Tratar retorno tardio
  de obterTrabalho para não sobrescrever a nova criação.
- Sem prazo: ação visível Revisar e calcular prazo na intimação; dados e
  fundamento confirmados pelo advogado, cálculo existente, painel atualizado
  após sucesso e erros recuperáveis. Aviso após captura explica etapa pendente.
- Testes DOM reais de novo trabalho e confirmar prazo/refresh; testes de
  transporte 401; pnpm test/lint/typecheck. Backend só se arquivo alterado.
- Não executar build na .next compartilhada com dev ativo. CI fará build.

## Revisão e publicação

Coordenador revisa diff e evidência; push já autorizado na sessão. Separar
testes simulados, deploy e confirmação real. Sem escrever dados de clientes
como parte de testes. Não modificar engine de prazos nesta correção de fluxo.

Executor: `/root/finish_mvp_feedback`, worker Sol/medium. Coordenador executou
`tests/test_execution_regressions.py`: 4 aprovados, SQLite isolado e provedores
simulados. Consulta READ ONLY confirmou 614 intimações/359 processos/zero prazos.
Browser indisponível (inventário vazio e IAB indisponível); DOM automatizado
não comprova resultado visual ou animação no navegador do fundador.
O encerramento por 401 usa escopo local, conforme
[Supabase signOut](https://supabase.com/docs/reference/javascript/auth-signout).

## Resultado local

- Captura: rotação normal mantida; pulso suave de opacidade em movimento reduzido.
- Sidebar: ação Novo trabalho com ícone de adição, reset da seleção/URL; formulário
  limpo e focado pelo botão do módulo. Retomada tardia não sobrescreve criação.
- Intimações: ação Revisar e calcular prazo; painel recarregado após confirmação.
  Visão geral mostra intimações sem prazo vinculado. Não foi implantada contagem
  automática de todas as publicações: duração, data base e calendário continuam
  sujeitos à confirmação humana, com a matemática determinística já existente.
- Auth: renovação compartilhada limitada a 8s e uma repetição da chamada após
  401; troca de conta/login/logout impede reaproveitar requisição antiga. Segunda
  recusa encerra sessão local; timeout de renovação permite nova tentativa.
- Coordenador revisou o diff e executou `pnpm.cmd check`: lint, tipos e 115 testes
  aprovados. Backend: 4 testes de regressão do cálculo/confirmação aprovados.
  Build ficará no CI; nenhum build foi executado na .next do servidor dev ativo.

## Publicação verificada

Commit 83e4914 na main. CI 36575280431 aprovado em backend, frontend/build e
PostgreSQL 16/17. Deploy 36575485494 aprovado; script confere imagem exata de
backend, worker, autos-worker e frontend. API pública /health respondeu 200.
Sem validação visual nesta sessão e sem criar prazos reais durante testes.
