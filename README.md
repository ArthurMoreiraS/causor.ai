# Causor

SaaS operacional para escritórios jurídicos brasileiros. O fluxo principal é:

`captura oficial → prazo determinístico → minuta com IA → aprovação humana → protocolo assistido → auditoria`

## Estado atual

O MVP já possui:

- captura de intimações por DJEN/Comunica e enriquecimento via DataJud;
- System of Record multi-tenant com autenticação Supabase;
- cálculo determinístico de prazos;
- classificação, chat operacional e geração de minutas com Claude;
- templates do escritório, fila de revisão e Gate OAB;
- protocolo PJe assistido até `ready_to_sign`;
- vault local/Supabase para referências e sessões, sem segredos no SOR;
- jobs persistidos, captura agendada com retry e recuperação de jobs interrompidos;
- frontend Next.js para o fluxo operacional e onboarding do piloto;
- auditoria das mutações relevantes.

O envio final ainda é feito pelo advogado no PJe/PJeOffice. O número do
protocolo é confirmado depois no Causor.

## Estrutura

- `backend/`: FastAPI, SOR, captura, prazo engine, agente, PJe, vault e jobs.
- `frontend/`: Next.js, React e integração com Supabase Auth.
- `infra/`: Postgres e Redis para desenvolvimento.
- `docs/`: produto, operação, deploy e decisões de arquitetura.

## Desenvolvimento

Consulte [docs/local-dev.md](docs/local-dev.md). Resumo:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload
```

Em outro terminal:

```powershell
cd frontend
pnpm install
pnpm dev
```

## Qualidade

```powershell
cd backend
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
pnpm check
pnpm build
```

O workflow `.github/workflows/ci.yml` executa essas verificações em pushes para
`main` e em pull requests.

## Fonte de verdade

- Estado e próximos passos: [docs/proximos-passos-mvp.md](docs/proximos-passos-mvp.md)
- Operação do piloto: [docs/onboarding-piloto.md](docs/onboarding-piloto.md)
- Deploy: [docs/deploy.md](docs/deploy.md)
- Direção estratégica: [docs/PRD_Causor.md](docs/PRD_Causor.md)

Documentos em `docs/superpowers/` registram decisões e planos históricos; não
devem ser usados isoladamente para inferir o estado atual.
