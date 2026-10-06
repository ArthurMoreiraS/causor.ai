# Migração para outro projeto Supabase Free

Fundador escolheu em 06/10 preparar outro projeto Free e migrar para permitir
login antes da reunião com advisor. Não há autorização para contratar plano,
excluir origem ou produzir protocolo judicial. Preservar dados/auditoria e
validar destino antes de trocar configuração de produção.
Steering inicial: fundador pediu somente preparar a estrutura e fornecerá
as chaves depois. Depois forneceu conexão/chaves e autorizou realizar a troca.
Esse novo pedido autoriza publicar ferramentas, pausar, migrar e trocar a
configuração mantendo origem e rollback. Não registrar credenciais neste plano.

## Condições encontradas

- Origem continua com Auth 402; conexão SQL estava acessível para leitura.
- Sem navegador conectado e in-app browser indisponível nesta sessão.
- Não há Supabase CLI, pg_dump/psql ou token administrativo configurado.
- Docker Desktop iniciado; daemon Linux 29.7.2 e clientes oficiais PG17
  disponíveis para ensaio isolado com dados fictícios.
- Deploy atual usa VPS/Compose por GitHub Actions, não Render/Vercel. Configuração
  da VPS é privada; Actions tem SSH, mas seus secrets não podem ser lidos pela API.
- Novo projeto e elegibilidade Free ainda não verificados. Limite documentado é
  de dois projetos Free ativos por conta envolvida; quotas são por organização.
  Criar na organização restrita não constitui liberação da mesma organização.

## Escopo

1. Preparar inventário somente leitura e procedimento de backup/restauração;
   usar pg_dump compatível com versão da origem e validar no destino descartável.
   Não copiar tabelas manualmente por ORM nem recriar auditoria como novos eventos.
2. Novo projeto Free em organização não restrita, sujeito à elegibilidade/regras
   do Supabase. Fundador precisa criá-lo ou disponibilizar acesso administrativo
   seguro: não há acesso ao painel nesta sessão. Credenciais somente em arquivo
   local ignorado, nunca no chat/log/diff.
3. Preservar SOR, Auth identidades/senhas, extensões e Vault quando usado. Vault
   requer atenção à chave de criptografia; dump simples de ciphertext não basta.
   PDFs no volume da VPS devem permanecer acessíveis; banco não contém esses bytes.
4. Ao revisar troca de Auth, encontrado JWKS escolhido pelo `iss` não verificado
   do próprio token. Restringir consulta ao projeto configurado; cobrir token de
   emissor externo, configuração ausente e alias com JWKS válido, preservando
   verificação por chave PEM fixa e caminho HS256 existente.
5. Configurar URL/chave pública no frontend e issuer/projeto de Auth no backend;
   atualizar DSN na VPS somente após restore validado e pausa controlada dos
   consumidores. Não colocar conexão do banco/JWT secret no frontend.
6. Testar login real → `/me` → isolamento, inventário/contagens/sequences,
   auditoria preservada, arquivo original, operação em fila e captura autorizada.
   Voltar configurações anteriores se falhar; preservar origem até aceite.

## Verificação

Testes de autenticação com chaves fictícias; inventário SQL em READ ONLY;
restauração em destino explicitamente novo; comparação de dados e constraints;
CI/versões/health separados de login e uso real. Não executar restore/DDL em
conexão derivada da origem. Não publicar credenciais ou dados de pessoas.

## Resultado desta preparação

- Criados `backend/scripts/supabase_free.py`, modelo de env e
  `docs/operacao/migracao-supabase-free.md`.
- Destino privado vazio e ignorado pelo Git; nenhuma configuração existente
  substituída. Verificação offline não chama banco ou Auth.
- Inventário inicial somente leitura: PG17.6, 35 tabelas do modelo/1.246 linhas,
  das quais 1.235 eventos de auditoria; Auth um usuário/uma identidade.
  Vault/Storage vazios. Não constitui backup final.
- Backup exige declaração de pausa das escritas; public/Auth usam snapshot
  comum. Restore recusa origem/destino ocupado e preserva schema Auth gerenciado.
  Erro SQL reverte public/Auth; SHA-256, fingerprints e sequences conferidos.
  Vault/Storage usados ou triggers personalizados gerenciados exigem revisão.
- 28 testes direcionados de migração/Auth/tenant aprovados, dois PG opcionais
  ignorados nessa execução; depois os 14 da migração passaram com PG17 local.
  Regressão prova hash de senha/UUID/auditoria/sequence fictícios, bloqueio de
  sobrescrita e rollback quando Auth falha. Ruff direcionado aprovado.
- Suíte backend completa hermética: 821 aprovados, 110 ignorados, 12 avisos
  exclusivamente de chaves curtas fictícias. SQLite descartável e credenciais
  externas vazias; dois testes de restore rodados separadamente com PG17.
  Ruff completo e diff check aprovados. Container de teste encerrado.
- Novo projeto, schema Auth gerenciado, elegibilidade Free, restauração real,
  login real e troca de produção permanecem para a etapa com credenciais.

## Referências atuais

- [Quotas e restrições por organização](https://supabase.com/docs/guides/platform/billing-faq)
- [Transferência e limite de projetos Free](https://supabase.com/docs/guides/platform/project-transfer)
- [Backup/restauração e Vault](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore)

Transferir organização não é garantia documentada de remover uma restrição já
aplicada; não depender dessa hipótese para afirmar login restabelecido.

## Retomada autorizada com credenciais

- Destino diferente da origem, PG17.11, public/Auth usuários vazios. Conexão
  Session pooler confirmada em leitura após conexão direta sem IPv4.
- Auth health 200 com chave pública e JWKS ES256; segredo HS256 antigo deve ser
  retirado no cutover. Chave administrativa somente no arquivo privado.
- Workflow manual `Supabase migration` usa SSH já configurado e mesma trava de
  produção: pause/configure/resume/rollback. Configure exige serviços de escrita
  parados, origem/destino correspondentes, backup privado e substituição atômica.
- Deploy manual para reconstruir frontend com as variáveis novas exige CI do
  mesmo SHA aprovado e main. Nada pode incluir segredo no frontend/repositório.
- 40 testes direcionados aprovados/2 opcionais ignorados, Ruff aprovado;
  ensaio PG17 anterior aprovado. Backup final/restore/cutover ainda pendentes.
