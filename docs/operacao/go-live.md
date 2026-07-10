# Go-live - estrutura pos-hospedagem

Desenho aprovado do que muda quando o Causor sai da maquina local e vai para
producao (Vercel + Render + Supabase), e do funil de vendas formalizado. O
`deploy.md` diz **como** subir cada peca; este documento diz **o que** existe
em producao, o que muda no fluxo de onboarding e em que ordem cortar.

Funil de vendas hoje (e que permanece no go-live): landing page -> cliente
marca reuniao -> GO na reuniao -> convite por e-mail para criar a conta ->
primeiro login. Vendas-led com convite; sem cadastro self-serve na LP por
enquanto.

## 1. Topologia de producao

| Peca | Onde | Dominio | Observacao |
|---|---|---|---|
| Landing page | Vercel (repo `causor-landing`) | `causor.com.br` | Estatica; CTA de agendar reuniao |
| Frontend (app) | Vercel (este repo, root `frontend/`) | `app.causor.com.br` | Deploy por push na `main` |
| Backend (API) | Render (este repo, root `backend/`) | `api.causor.com.br` | Usa o `Procfile`; `alembic upgrade head` no release |
| Banco/Auth/Vault | Supabase (projeto atual, `sa-east-1`) | - | `CAUSOR_VAULT_PROVIDER=supabase`; regiao BR ajuda na LGPD |
| Captura agendada | Render Cron Job | - | `python -m app.cli capture-due` a cada 6-12h; alertar em exit code 1 |

## 2. Variaveis de ambiente por servico

Backend (Render):

- `CAUSOR_DATABASE_URL` - string do Supabase Postgres (pooler, porta 6543).
- `CAUSOR_SUPABASE_JWT_SECRET` - segredo/chave do Supabase Auth.
- `CAUSOR_DATAJUD_API_KEY` - chave publica DataJud/CNJ.
- `ANTHROPIC_API_KEY` - chave Claude.
- `CAUSOR_CLAUDE_CHAT_MODEL=claude-haiku-4-5`
- `CAUSOR_CLAUDE_CLASSIFICATION_MODEL=claude-haiku-4-5`
- `CAUSOR_CLAUDE_DRAFT_MODEL=claude-sonnet-5`
- `CAUSOR_CORS_ORIGINS=https://app.causor.com.br`
- `CAUSOR_VAULT_PROVIDER=supabase`
- `CAUSOR_FILING_MODE=sandbox` - protocolo real so em piloto controlado.
- `CAUSOR_PJE_ALLOW_PROD` - **nao** setar no Render enquanto a captura de
  sessao for assistida (ver secao 5); o navegador abriria no servidor.

Frontend (Vercel):

- `NEXT_PUBLIC_API_BASE=https://api.causor.com.br`
- `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## 3. Funil de vendas -> conta ativa

1. **LP -> reuniao.** CTA da landing agenda a reuniao (Calendly ou similar).
2. **GO na reuniao.** Voce decide quem entra; nao ha cadastro aberto.
3. **Convite.** No painel do Supabase Auth, "Invite user" com o e-mail do
   advogado e redirect para `https://app.causor.com.br`. O e-mail sai pelo
   mailer padrao do Supabase por enquanto; e-mail interno via Resend e uma
   pendencia registrada (secao 7), nao um bloqueio do corte.
4. **Provisionamento no SOR.** Ate o auto-provision existir, rode da sua
   maquina o mesmo comando de hoje apontando para producao:

   ```powershell
   cd backend
   $env:CAUSOR_DATABASE_URL = "<string do Supabase de producao>"
   .\.venv\Scripts\python.exe -m app.cli provision-pilot `
     --escritorio "Nome" --nome "Advogado" --email "adv@x.com" --oab "123456" --uf "SP"
   ```

   A string de producao entra so como variavel de ambiente da sessao; nunca
   em arquivo commitado.
5. **Primeiro login.** O advogado define a senha pelo link do convite e entra
   em `app.causor.com.br`.
6. **Ativacao.** Checklist de `onboarding-piloto.md` (OAB + primeira captura,
   prazo revisado, minuta gerada, template, aprovacao no gate).

## 4. O que muda: hoje -> depois de hospedar

| Peca | Hoje (local) | Depois (producao) |
|---|---|---|
| Backend | roda na sua maquina | Render, `api.causor.com.br` |
| Provisionamento | CLI contra banco local | mesma CLI contra banco prod; depois auto-provision no 1o login |
| Convite | link manual do Supabase | igual, com redirect para `app.causor.com.br`; depois Resend |
| Captura agendada | manual / task local | Render Cron `capture-due` |
| CORS | `localhost:3000` | `https://app.causor.com.br` |
| Conectar tribunal | abre navegador na sua maquina (funciona) | **quebra** - ver secao 5 |
| Protocolo | sandbox | sandbox (real so em piloto controlado com gate) |

## 5. Restricao estrutural: Conectar tribunal remoto

A captura de sessao (`capture_pje_storage_state`) abre o Playwright **na
maquina onde o backend roda**. Local, isso e a maquina do proprio operador e
funciona. No Render, o navegador abriria no servidor - o advogado nunca ve a
tela de login do tribunal. O botao "Conectar" do app nao funciona de ponta a
ponta com backend hospedado.

Saida definitiva (implementada): **agente local Causor**. O advogado pareia o
computador dele uma vez e o agente executa navegador/sessao localmente; o
backend hospedado **nunca** abre navegador de tribunal - ele apenas publica
comandos, e o agente online os reivindica e devolve resultado/evidencia.

Pareamento (uma vez por computador do advogado):

```powershell
cd backend
$PAIRING_CODE = "copie-o-codigo-exibido-no-Causor"
.\.venv\Scripts\python.exe -m app.local_agent pair `
  --api http://127.0.0.1:8000 `
  --code $PAIRING_CODE `
  --name "Notebook jurídico"

.\.venv\Scripts\python.exe -m app.local_agent run
```

O codigo de pareamento e gerado em Configuracoes → "Agente local" e expira em
10 minutos. O token do agente fica no keyring do Windows (nunca em arquivo);
a sessao do tribunal fica no perfil Playwright em `%LOCALAPPDATA%\Causor\profiles`.
Para leitura/protocolo autenticados funcionarem, o agente precisa estar
online (`python -m app.local_agent run`).

Paliativo anterior (captura assistida em reuniao com backend local) permanece
documentado no historico, mas nao e mais o caminho principal.

## 6. Checklist de corte (dia da hospedagem)

Em ordem; nao pule a verificacao de cada passo.

1. Supabase: habilitar extensao Vault; conferir backup/PITR ativo.
2. Render: criar Web Service (root `backend`, build `pip install -e .`,
   start via `Procfile`, release `alembic upgrade head`) + env vars da secao 2.
3. Verificar `GET https://<render>.onrender.com/health` -> `{"status":"ok"}`.
4. Vercel: importar `frontend/` + env vars da secao 2. Build verde.
5. DNS: `app` -> Vercel, `api` -> Render (CNAMEs); aguardar TLS.
6. Ajustar `CAUSOR_CORS_ORIGINS` para a URL final e redeploy do backend.
7. Supabase Auth: adicionar `https://app.causor.com.br` as Redirect URLs.
8. Teste ponta a ponta com conta descartavel: convite -> senha -> login ->
   `GET /me` 200 -> provisionamento -> dashboard carrega.
9. Captura de teste: `Captura por OAB` com uma OAB real; conferir intimacoes.
10. Render Cron: agendar `capture-due`; conferir primeiro run e alerta.
11. Monitoramento: uptime em `/health` (UptimeRobot ou similar).
12. Registrar URLs finais e donos de cada servico neste arquivo.

## 7. Pendencias de codigo (prioridade pos-corte)

1. **Auto-provision no primeiro login** - backend cria escritorio/usuario a
   partir do token Supabase no primeiro `GET /me`, eliminando o passo 4 do
   funil (CLI manual).
2. **E-mails internos via Resend** (decisao registrada em 2026-07-08; "mais
   pra frente"). Convite/boas-vindas/reset com dominio e template proprios.
   Caminho curto sem codigo: configurar o SMTP custom do Supabase Auth
   apontando para o Resend (e-mail ja sai brandado). Caminho completo:
   `admin.generateLink()` + envio pela API do Resend, controle total do
   template e da jornada.
3. **Helper local do Conectar tribunal** (secao 5, saida 1).
4. **Observabilidade minima**: Sentry no backend + logs estruturados dos jobs.
