# Equipe e papéis no escritório

Data: 07/10/2026. Decisões do fundador na mesma data.

## Escopo

Um escritório tem várias pessoas, com hierarquia. Até aqui havia `usuario`
por escritório e `responsavel_id` em tarefa e trabalho, mas sem papéis, sem
convite pelo app e sem permissão aplicada.

Decisões:

- **Três papéis fixos.** `administrador` (sócio: equipe e configuração do
  escritório), `advogado` (todo o fluxo, aprova minuta e decide prazo),
  `assistente` (estagiário/paralegal: tarefas, documentos, rascunhos; não
  aprova minuta nem altera prazo).
- **Todos veem tudo** dentro do escritório. "Minhas tarefas" é só filtro.
- **Avisos de prazo** vão para o responsável e os administradores; prazo sem
  responsável avisa o escritório inteiro.
- **Responsável** continua só em tarefa e trabalho jurídico.

## Permissões (matriz única em `app/auth/papeis.py`)

| Permissão | Administrador | Advogado | Assistente |
|---|---|---|---|
| `gerir_equipe` (convidar, mudar papel, desativar) | sim | não | não |
| `configurar_escritorio` (nome, CNPJ, timbrado, OABs monitoradas, credenciais MNI) | sim | não | não |
| `aprovar_minuta` | sim | sim | não |
| `decidir_prazo` (corrigir, confirmar, marcar cumprido) | sim | sim | não |

O backend responde 403; a interface só esconde o que não se pode fazer.

## Aceite

- Migração: `usuario.papel` e `usuario.ativo`; usuários existentes viram
  administradores.
- Convite pela aba Equipe: cria o membro e envia o convite do Supabase Auth
  (chave service-role só no backend, lida do ambiente na hora do envio). Sem a
  chave, o membro é criado e a tela diz para convidar pelo painel do Supabase.
- Sempre resta ao menos um administrador ativo; ninguém altera o próprio papel
  nem se desativa.
- Membro desativado recebe 403, não recebe aviso e não pode ser escolhido como
  responsável. Nada é apagado.
- Convite, mudança de papel, desativação e reativação entram na auditoria.
- Aviso de prazo: um e-mail por pessoa por execução; um prazo só é marcado como
  avisado quando todos os destinatários dele receberam.

## Verificação

- `pytest -q`, `ruff check .` e `pnpm check`.
- Implantação depende de configurar `CAUSOR_SUPABASE_SERVICE_ROLE_KEY` e
  `CAUSOR_APP_URL` na VPS e de `/set-password` estar nas Redirect URLs do
  Supabase.
