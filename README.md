# Causor

SaaS operacional para escritórios jurídicos brasileiros. O fluxo principal é:

`captura oficial → prazo determinístico → minuta com IA → aprovação humana → protocolo assistido → auditoria`

## Estado atual

> **Revisão de 04/09/2026:** há componentes implementados que ainda não formam
> um fluxo operacional completo. Os handlers atuais do agente local não executam
> leitura/preparo real. A execução posterior integrou upload, extração, resumos
> e contexto, com teste HTTP ponta a ponta usando provedores simulados.
> A lista abaixo descreve componentes existentes, não homologação em tribunais.
> Consulte o [diagnóstico atualizado](docs/areas/diagnostico-causor-2026-09-04.md)
> e o [estado do projeto](docs/estado.md) antes de iniciar um piloto.
> O [registro da execução](docs/produto/execucao-2026-09-04.md) explica operação,
> configuração do Astra, validação e dependências externas.

O MVP já possui:

- captura de intimações por DJEN/Comunica e enriquecimento via DataJud;
- System of Record multi-tenant com autenticação Supabase;
- cálculo determinístico de prazos;
- classificação, chat operacional e geração de minutas com Claude;
- templates do escritório, fila de revisão e Gate OAB;
- upload por grau, extração, resumos citados e contexto integrado ao worker,
  com gate fail-closed e retomada de documentos anteriores;
- canal MNI para leitura no servidor, dependente de credenciamento e validação,
  com roteamento para o agente quando não há canal MNI elegível;
- infraestrutura de agente local e conector PJe legado; os handlers atuais de
  leitura/preparo real ainda não estão implementados;
- registro manual do protocolo informado pelo advogado;
- vault local/Supabase para referências e credenciais, sem segredos no SOR;
- jobs persistidos, captura agendada com retry e recuperação de jobs interrompidos;
- frontend Next.js para o fluxo operacional e onboarding do piloto;
- auditoria das mutações relevantes.

Na modalidade manual, o envio é feito pelo advogado no sistema do tribunal.
O registro posterior do número no Causor não verifica por si só o comprovante.

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
