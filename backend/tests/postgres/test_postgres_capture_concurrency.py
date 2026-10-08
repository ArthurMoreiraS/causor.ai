"""Real row lock and tenant isolation for manual capture enqueueing."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.main import create_app
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.sor import models
from app.sor.db import get_session


def _client(pg_engine, office_id):
    app = create_app()
    factory = sessionmaker(pg_engine, autoflush=False, expire_on_commit=False)

    def session_dependency():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        usuario_id=1, escritorio_id=office_id, email="test@example.com",
        papel="administrador",
    )
    return TestClient(app)


def test_simultaneous_capture_reuses_one_job_and_isolates_tenant(pg_engine):
    with Session(pg_engine) as session:
        offices = [models.Escritorio(nome="A"), models.Escritorio(nome="B")]
        session.add_all(offices)
        session.commit()
        own_id, other_id = (office.id for office in offices)

    client = _client(pg_engine, own_id)
    barrier = Barrier(2)

    def post():
        barrier.wait()
        return client.post("/jobs/capture/oab", json={"oab": "123.456", "uf": "sp"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: post(), range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 1

    with Session(pg_engine) as session:
        own_oabs = session.scalars(select(models.OabMonitorada).where(models.OabMonitorada.escritorio_id == own_id)).all()
        own_jobs = session.scalars(select(models.JobExecucao).where(models.JobExecucao.entidade == "escritorio", models.JobExecucao.entidade_id == own_id)).all()
        assert [(row.oab, row.uf) for row in own_oabs] == [("123456", "SP")]
        assert len(own_jobs) == 1

    other = _client(pg_engine, other_id)
    response = other.post("/jobs/capture/oab", json={"oab": "123456", "uf": "SP"})
    assert response.status_code == 200
    assert response.json()["id"] != responses[0].json()["id"]
    assert other.get(f"/jobs/{responses[0].json()['id']}").status_code == 404
