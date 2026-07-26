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
- leitura íntegra dos autos com prova de completude e gate fail-closed;
- canal oficial MNI (webservice do CNJ) para leitura dos autos no servidor,
  com o agente local como fallback automático por processo;
- protocolo PJe assistido até `ready_to_sign`;
- vault local/Supabase para referências e credenciais, sem segredos no SOR;
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

Consulte [`RODAR-LOCAL.md`](RODAR-LOCAL.md) para o quickstart (subir backend +
frontend) e [`docs/operacao/local-dev.md`](docs/operacao/local-dev.md) para
setup completo e troubleshooting. Resumo:

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

- Documentação (índice): [docs/README.md](docs/README.md)
- Estado e próximos passos: [docs/estado.md](docs/estado.md)
- Operação do piloto: [docs/operacao/onboarding-piloto.md](docs/operacao/onboarding-piloto.md)
- Deploy: [docs/operacao/deploy.md](docs/operacao/deploy.md)
- Direção estratégica: [docs/produto/PRD.md](docs/produto/PRD.md)
- Protocolo PJe + vault: [docs/areas/pje-assistido.md](docs/areas/pje-assistido.md)
- Endpoints MNI e credenciamento: [docs/areas/mni-credenciamento.md](docs/areas/mni-credenciamento.md)

Documentos em `docs/historico/superpowers/` registram decisões e planos
históricos; não devem ser usados isoladamente para inferir o estado atual.
