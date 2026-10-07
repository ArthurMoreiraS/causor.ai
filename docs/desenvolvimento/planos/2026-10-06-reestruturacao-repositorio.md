# Reestruturação do repositório — 06–07/10/2026

## Objetivo e autorização

O fundador aprovou em 06/10 a remoção de documentação e código que descrevem
a direção anterior (protocolo automático, agente local, MNI como eixo,
interface "Hoje"). Confirmou que o agente local existia só para o protocolo
automático, que não será estruturado agora, e autorizou executar todo o
diagnóstico, incluindo apagar os artefatos locais.

## O que foi feito

**Documentação.** Apagados os planos e specs executados ou abandonados
(`docs/superpowers/`, `docs/historico/superpowers/`, planos concluídos de
27/09 a 06/10, registros de setembro e o plano de UI/UX rejeitado). Pesquisas
e trilhas adiadas foram para `docs/historico/`; a pesquisa vigente foi para
`docs/mercado/`. `AGENTS.md`, `README.md`, `docs/README.md` e `docs/estado.md`
foram reescritos; o log anterior do estado virou
`historico/estado-ate-2026-10-06.md`. `RODAR-LOCAL.md`, `DEPLOY-VPS.md` e
`IA.md` foram consolidados em `docs/operacao/`.

**Frontend.** Removidos o assistente de acesso ao tribunal, os componentes
órfãos (agente, vault, protocolo, pacote, histórico de envios), as views
Protocolos e Integrações (inalcançáveis), o botão "Capturar autos" e o caminho
morto de minuta direta pela intimação, com as funções de API correspondentes.

**Backend.** Removidos `local_agent`, `agent_runtime`, rotas de agente,
conectores/sessões/acesso a tribunais, conector PJe e simuladores de portal,
pacotes e tentativas de protocolo, `signing`, jobs e endpoints de protocolo e
de credenciais de assinatura, comandos CLI do simulador e da cobertura. A
captura automática agora só usa MNI com perfil confirmado e credencial ativa;
sem isso responde `409 sem_canal_automatico`, e o gate de contexto indica
`upload_autos`. Configurações órfãs saíram; `playwright` virou dependência de
desenvolvimento e `keyring` foi removido.

**Mantido de propósito:** leitor MNI (sem UI), `vault`, `filing/approval`,
`render` e `timbrado` (aprovação e PDF da minuta), as tabelas do banco (sem
migração) e o endpoint antigo `POST /intimacoes/{id}/draft`, que não é mais
chamado pela interface.

**Scripts e arquivos locais.** Removidos os agendamentos de captura no Windows,
o validador de login de tribunal e os smokes visuais de telas antigas;
`probe_mni.py` foi para `backend/scripts/`. Apagados `artifacts/` da raiz
(1,6 GB), demos e saídas de smoke em `backend/artifacts/` e `.codex/`.
`backend/artifacts/supabase-free` (backup e credenciais da migração) e
`objects/` foram preservados. Transcrição da reunião e briefing seguem fora do
git: o repositório no GitHub é público.

## Verificação

- Backend: Ruff aprovado; suíte completa com 669 aprovados e 100 ignorados
  (PostgreSQL/live rodam no CI). Linha de base antes da mudança: 843 aprovados;
  a diferença são testes de código removido.
- Frontend: lint, tipos, 140 testes (antes 163) e build de produção aprovados.
- Links dos documentos vivos conferidos por script. Nos arquivados, links para
  arquivos que só mudaram de pasta foram reescritos; os que apontam para
  arquivos apagados ficam cobertos pelo aviso de `historico/README.md`.
- Não houve commit, push nem deploy nesta etapa.
