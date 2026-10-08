# Onboarding de piloto

Fluxo para cadastrar o primeiro advogado/escritorio sem depender da seed de demo.

## 1. Criar o usuario no Supabase Auth

No painel do Supabase, crie ou convide o usuario com o e-mail que ele usara no
login do Causor.

## 2. Provisionar escritorio + usuario no SOR

No backend, rode:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli provision-pilot `
  --escritorio "Nome do Escritorio" `
  --nome "Nome do Advogado" `
  --email "advogado@example.com" `
  --oab "123456" `
  --uf "SP"
```

O comando e idempotente por e-mail: se o usuario ja existir, atualiza nome,
escritorio e OAB; se nao existir, cria o escritorio e o usuario como
**administrador** do escritorio.

## 2b. Convidar o resto da equipe

O administrador convida os demais em **Configurações → Equipe**, escolhendo o
papel: administrador (equipe e configuração do escritório), advogado (aprova
minuta e decide prazo) ou assistente (tarefas, documentos e rascunhos). Todos
veem todo o escritório; o papel só restringe ações.

O e-mail de convite sai pelo Supabase Auth quando a VPS tem
`CAUSOR_SUPABASE_SERVICE_ROLE_KEY` e `CAUSOR_APP_URL` (modelo em
`infra/.env.prod.example`). Sem isso o membro é criado e a tela pede o convite
pelo painel do Supabase; o primeiro login liga a conta pelo e-mail. O e-mail
padrão do Supabase só entrega para membros da organização do projeto: para
convidar pessoas de fora, configure um SMTP próprio no Supabase Auth.

## 3. Primeiro acesso

O advogado acessa o frontend e faz login. O backend resolve o usuario pelo
token Supabase via `GET /me`; nao ha mais dependencia do primeiro usuario do
banco.

## 4. Cadastrar OAB e rodar primeira captura

No app, clique em `Captura por OAB`. O frontend agora:

1. registra a OAB em `/capturas/oab`, deixando-a pronta para captura agendada;
2. enfileira `/jobs/capture/oab` e acompanha o resultado pelo job persistente;
   cadastro e enfileiramento são atômicos, com reuso de capturas já ativas.

O serviço `capture-scheduler` mantém ciclos posteriores; consultar
[operação da captura periódica](captura-periodica.md). Não usar o antigo cron
`capture-due` em paralelo. Se não houver publicação na janela, ampliar uma
consulta manual de forma explícita ou começar um trabalho por demanda manual.

## 5. Completar ativacao

Checklist minimo do piloto:

- OAB cadastrada e captura inicial executada.
- Ao menos um prazo revisado.
- Ao menos uma minuta gerada.
- Documentos do caso enviados e conferidos contra inventário do advogado.
- Fontes, lacunas e minuta conferidas pelo advogado; revisão registrada.

Roteiro do primeiro caso: [aceite do MVP](aceite-mvp-2026-10-08.md).
Protocolo judicial permanece uma etapa separada, sujeita a rota validada e
aprovação humana; não é requisito desta primeira demonstração.
