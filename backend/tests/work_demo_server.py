"""Isolated browser test server. Synthetic tenant/providers, loopback only; never production.

Run from backend: python -m tests.work_demo_server
Creates a fresh disposable SQLite database under artifacts for every run.
"""
import os
from pathlib import Path
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
(ROOT / "artifacts").mkdir(exist_ok=True)
DIRECTORY = Path(tempfile.mkdtemp(prefix="work-demo-", dir=ROOT / "artifacts"))
os.environ["CAUSOR_DATABASE_URL"] = "sqlite:///" + (DIRECTORY / "demo.db").as_posix()
os.environ["CAUSOR_OBJECT_STORE_PROVIDER"] = "localdev"
os.environ["CAUSOR_OBJECT_STORE_LOCAL_PATH"] = str(DIRECTORY / "objects")
os.environ["CAUSOR_CORS_ORIGINS"] = "http://127.0.0.1:3099,http://localhost:3099"
os.environ["CAUSOR_DATAJUD_API_KEY"] = ""

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.api.autos_routes import get_datajud_client  # noqa: E402
from app.auth.jwt_auth import CurrentUser, get_current_user  # noqa: E402
from app.sor.db import Base, get_session  # noqa: E402
from app.sor import models  # noqa: E402
from app.agent import work_service  # noqa: E402
from app.agent.drafter import MinutaGerada  # noqa: E402
from app.autos import summarizer, worker  # noqa: E402
from app.queue.worker import WorkerClients, run_once  # noqa: E402
from app.prazo_engine.factory import build_calendar  # noqa: E402

engine = create_engine(os.environ["CAUSOR_DATABASE_URL"], connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
factory = sessionmaker(engine, expire_on_commit=False)
with factory() as db:
    office = models.Escritorio(nome="DEMONSTRAÇÃO SINTÉTICA — sem efeito judicial")
    db.add(office)
    db.flush()
    user = models.Usuario(escritorio_id=office.id, nome="Advogado de demonstração", email="demo@example.invalid")
    db.add(user)
    db.commit()
    principal = CurrentUser(usuario_id=user.id, escritorio_id=office.id, email=user.email, papel="administrador")


def sessions():
    with factory() as db:
        yield db


class NoCourt:
    def consultar(self, *args, **kwargs):
        raise RuntimeError("This isolated demo must never capture court data")

    def consultar_processo(self, *args, **kwargs):
        return None


def synthetic_summary(snapshot):
    chunk = snapshot.chunks[0]
    return summarizer.SummaryResult(summarizer.DocumentDigest(
        resumo="DEMONSTRAÇÃO: documentos contratuais sintéticos para conferência.",
        fatos=[], pedidos=[], decisoes=[], prazos=[], incertezas=["Sem consulta ao tribunal"],
        citations=[summarizer.ChunkCitation(chunk_id=chunk.id, quote=chunk.texto[:120])]), "synthetic-provider", 1)


def synthetic_analysis(*, citations, **kwargs):
    return {"fatos": [{"texto": "DEMONSTRAÇÃO: documento apresentado registra uma contratação fictícia.",
        "fontes": [citations[0]["chunk_id"]], "natureza": "fato_documentado"}], "cronologia": [],
        "contradicoes": [], "lacunas": ["Solicitar comprovante integral do pagamento; caso sintético."]}


summarizer.generate_summary = synthetic_summary
work_service.analyze_sources = synthetic_analysis
work_service.draft_peticao = lambda **kwargs: MinutaGerada(
    contexto_consolidado="DEMONSTRAÇÃO SINTÉTICA — revisão das fontes fornecidas.",
    analise_providencia="Conferir os documentos e a parte representada antes de qualquer uso.",
    minuta="DEMONSTRAÇÃO SINTÉTICA — SEM EFEITO JUDICIAL\n\nMANIFESTAÇÃO\n\nA parte fictícia apresenta os documentos para revisão humana.\n\nNão protocolar esta demonstração.",
    confianca=0.5, alertas=["Demonstração; conteúdo e análise simulados."])

app = create_app()
app.dependency_overrides[get_session] = sessions
app.dependency_overrides[get_current_user] = lambda: principal
app.dependency_overrides[get_datajud_client] = NoCourt


def process_documents():
    while True:
        worker.process_due_documents(factory, max_attempts=1)
        time.sleep(0.5)


def process_work_jobs():
    clients = WorkerClients(djen=NoCourt(), datajud=NoCourt(), calendar=build_calendar([2026]))
    while True:
        run_once(factory, clients=clients)
        time.sleep(0.5)


if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=process_documents, daemon=True).start()
    threading.Thread(target=process_work_jobs, daemon=True).start()
    print(f"SYNTHETIC DEMO ONLY — data at {DIRECTORY}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8099)
