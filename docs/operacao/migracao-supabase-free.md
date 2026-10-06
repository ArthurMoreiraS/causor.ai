# Preparação da migração Supabase Free

Fundador autorizou preparar um novo destino Free e migrar depois de fornecer
as credenciais. Em 06/10, pediu apenas preparar a estrutura. Não houve backup
final, restore real, troca de produção ou contratação de plano nesta etapa.
Posteriormente entregou conexão/chaves e autorizou realizar a troca; ver registro
de execução no plano de migração e estado atual em `docs/estado.md`.

## Arquivos e pré-requisitos

- Modelo: `backend/scripts/supabase-free.env.example`.
- Destino privado: `backend/artifacts/supabase-free/destino.env`, ignorado pelo Git.
- Origem: `backend/.env`; o script não altera este arquivo.
- Ferramenta: `backend/scripts/supabase_free.py`, usa dependências da venv e
  clientes da imagem oficial `postgres:17` via Docker Desktop Linux.
- Origem inventariada somente em leitura: PostgreSQL 17.6, 35 tabelas do modelo,
  1.246 registros incluindo 1.235 eventos de auditoria; um usuário e uma
  identidade Auth. Vault e Storage vazios. Este inventário inicial não é backup.

Projeto de destino deve ser novo, Free e elegível, em organização não restrita.
Quotas são compartilhadas pela organização; criar outro banco na organização
restrita não restaura seu acesso. A elegibilidade e os limites devem ser
conferidos no painel. Referências:
[restrições](https://supabase.com/docs/guides/platform/billing-faq) e
[limites de projetos](https://supabase.com/docs/guides/platform/project-transfer).

## Quando as credenciais chegarem

Preencher localmente o arquivo privado com conexão Session pooler na porta
5432 (ou conexão direta), URL e chave pública correspondentes ao destino.
Senha na URL precisa estar percent-encoded. O segredo JWT é necessário somente
para tokens HS256; ES256 usa o projeto confiável/JWKS. Não é necessário entregar
uma chave `service_role` para este procedimento. Login, SMTP, redirecionamentos
e provedores de Auth são configurações do projeto, não conteúdo do dump.

Executar de `backend`:

```powershell
./.venv/Scripts/python.exe scripts/supabase_free.py check
```

`check` é offline: valida formato, projetos diferentes, porta e correspondência
entre DSN/URL de Auth; não testa senha, disponibilidade, plano ou chave pública.
Nenhum comando troca as configurações de produção.

## Backup final e restauração

Antes do backup final, impedir novas escritas na API, finalizar jobs em execução
e pausar `backend`, `worker`, `autos-worker` e `capture-scheduler` na VPS.
Preservar o volume `causor_artifacts`; nunca executar `down -v`.
Guardar uma cópia privada da configuração atual da VPS e das configurações
públicas de build do frontend. O sinalizador abaixo declara que essa pausa foi
realizada: o script não controla a VPS nem confirma a pausa.

```powershell
./.venv/Scripts/python.exe scripts/supabase_free.py backup --source-quiesced --backup-dir artifacts/supabase-free/backup-final
./.venv/Scripts/python.exe scripts/supabase_free.py restore --backup-dir artifacts/supabase-free/backup-final --confirm-target PROJECT_REF_DO_DESTINO
./.venv/Scripts/python.exe scripts/supabase_free.py verify --backup-dir artifacts/supabase-free/backup-final
```

A pasta de backup deve ser nova e ficar dentro do diretório ignorado. O export
usa um snapshot PostgreSQL comum para as tabelas e os dois dumps:

- `public.dump`: schema, dados, grants, RLS, funções, trigger de auditoria,
  sequences e histórico Alembic.
- `auth-data.sql`: dados de Auth, preservando UUIDs/identidades/hash de senha;
  exclui `auth.schema_migrations`, que pertence à versão gerenciada do destino.
- `manifest.json`: SHA-256 dos arquivos, colunas, contagens, fingerprints
  calculados no servidor e estado das sequences. Não contém valores das linhas.

Somente dados Auth são restaurados; seu schema gerenciado não é substituído.
O restore recusa origem, destino com estruturas/dados existentes, versão PG
diferente, colunas Auth incompatíveis e backup corrompido. Não há DROP/clean.
O namespace public existente é conservado; grants e trigger de auditoria
permanecem no dump. O acesso amplo de anon/authenticated/PUBLIC encontrado na
origem é retirado na mesma transação: SOR permanece acessível pelo backend
privado e não pela API pública Supabase. Defaults de tabelas/sequences futuras
também ficam privados. Migração Alembic aplica essa regra nos deploys.
Schema/dados public e dados Auth entram em uma transação:
erro SQL interrompe e reverte toda a restauração. A conferência posterior
compara conteúdo e sequences; divergência impede liberar a troca de produção.

Ferramenta é restrita ao inventário atual. Vault/Storage não vazios ou triggers
personalizados em Auth/Storage interrompem o backup para revisão específica.
Roles, extensões e qualquer alteração gerenciada devem ser conferidos antes de
usar outro inventário. Não extrapolar os testes locais para todo schema Supabase.
Documentação oficial de referência:
[backup e restauração](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore).

## Troca de produção e retorno

A conexão local não configura automaticamente a VPS. Depois da conferência:

1. Atualizar privadamente na VPS `CAUSOR_DATABASE_URL`,
   `CAUSOR_SUPABASE_URL` e `CAUSOR_SUPABASE_JWT_SECRET` do destino
   (retirar segredo antigo se destino usa ES256/JWKS).
2. Atualizar no repositório GitHub a variável `NEXT_PUBLIC_SUPABASE_URL` e o
   secret `NEXT_PUBLIC_SUPABASE_ANON_KEY`; frontend incorpora esses valores
   no build. Não colocar senha do banco/segredo JWT nessas variáveis públicas.
3. Fazer CI/deploy com novas configurações. A produção atual é VPS/Compose em
   `/opt/causor`, por Actions; não é Render/Vercel. Conferir SHA dos cinco
   serviços e health. O agendador deve continuar pausado até validar Auth.
4. Fazer novo login real, `/me`, teste de isolamento, leitura da auditoria e
   arquivo original quando houver; depois reativar consumidores. Tokens do
   projeto antigo não estabelecem login no projeto novo.
5. Validar consulta manual OAB/UF, fila, documentos, contexto, minuta e revisão
   com os dados apropriados. OAB sem publicações pode concluir vazia.

Se falhar antes de receber novas escritas, restaurar env da VPS/variáveis de
build anteriores e redeploy da versão anterior. Isso retorna à origem ainda
restrita, sem prometer login. Se destino já recebeu novas escritas, não trocar
de volta cegamente: comparar e preservar essas linhas antes de decidir.
Manter origem e backups até aceite explícito do fundador.

### Operação via Actions

Workflow manual `Supabase migration` compartilha a trava de produção do Deploy.
Inputs: ação, project ref de origem e project ref de destino, sem credenciais.
Secrets temporários `CAUSOR_MIGRATION_DATABASE_URL`,
`CAUSOR_MIGRATION_SUPABASE_URL` e, somente se necessário,
`CAUSOR_MIGRATION_JWT_SECRET` chegam ao helper privado da VPS.

`pause` para os quatro serviços de escrita. Conferir jobs/interrupções no
inventário SQL depois da pausa, antes do backup; signal de parada não constitui
prova de conclusão de jobs. `configure` recusa serviços de escrita em execução,
salva `.env.pre-supabase` sem sobrescrever outro rollback e troca `.env`
atomicamente, preservando proprietário/permissões privadas e demais settings.
`rollback` repõe somente a configuração; `resume` retoma a configuração ativa.
Nenhuma dessas ações exporta/restaura dados nem altera o frontend.

Depois do restore, configure e atualização da variável/chave pública do GitHub,
dispatch manual do Deploy reconstrói o frontend. Esse dispatch exige main e
CI aprovado do mesmo SHA. Remover os secrets temporários após conclusão; manter
backup privado da configuração e dados. Retorno após novas escritas exige
conciliação; não executar rollback automático ao menor erro de health.

## Evidência de preparação

Testes isolados cobrem bloqueio de origem, Auth de outro projeto, porta de
transaction pooler, credenciais sem eco e arquivo corrompido. Testes opcionais
com PostgreSQL 17 descartável cobrem restore, identidade/hash de senha fictícios,
sequence, auditoria imutável, recusa de sobrescrever destino e rollback de
public quando Auth falha. Schema Auth desses testes é reduzido e fictício:
não é validação do novo serviço Supabase nem teste de login real.

Com servidor local de teste em 127.0.0.1:55433, senha fictícia, Docker ativo:

```powershell
$env:RUN_MIGRATION_PG='1'
./.venv/Scripts/python.exe -m pytest -q tests/test_supabase_free_migration.py
Remove-Item Env:RUN_MIGRATION_PG
```
