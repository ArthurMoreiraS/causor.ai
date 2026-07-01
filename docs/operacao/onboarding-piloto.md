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
escritorio e OAB; se nao existir, cria o escritorio e o usuario.

## 3. Primeiro acesso

O advogado acessa o frontend e faz login. O backend resolve o usuario pelo
token Supabase via `GET /me`; nao ha mais dependencia do primeiro usuario do
banco.

## 4. Cadastrar OAB e rodar primeira captura

No app, clique em `Captura por OAB`. O frontend agora:

1. registra a OAB em `/capturas/oab`, deixando-a pronta para captura agendada;
2. executa `/capture/oab` para montar a fila inicial.

## 5. Completar ativacao

Checklist minimo do piloto:

- OAB cadastrada e captura inicial executada.
- Ao menos um prazo revisado.
- Ao menos uma minuta gerada.
- Um template do escritorio criado em `Minutas & Templates`.
- Uma minuta aprovada no `Gate OAB`.
- Se houver PJe, preparar protocolo assistido ate `ready_to_sign` e registrar o
  numero final depois da assinatura no PJe/PJeOffice.
