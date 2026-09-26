from datetime import datetime, timedelta, timezone
from threading import Event

import pytest

from app.agent_runtime import service
from app.local_agent.guard import CommandGuard, GuardedHandler, OwnershipLost
from app.local_agent.worker import AgentWorker
from app.sor import models


def installation(session, seeded, user, token):
    row = models.AgentInstallation(escritorio_id=seeded.escritorio_id, usuario_id=user.id,
        nome="Simulador de executor", token_hash=token * 64, ativo=True, version="0.2.0")
    session.add(row)
    session.flush()
    return row


def test_claim_respects_identity_target_and_capabilities(db_session, seeded):
    first_user = db_session.query(models.Usuario).first()
    other_user = models.Usuario(escritorio_id=seeded.escritorio_id, nome="Outro advogado", email="other@example.invalid")
    db_session.add(other_user)
    db_session.flush()
    first = installation(db_session, seeded, first_user, "a")
    second = installation(db_session, seeded, first_user, "b")
    other = installation(db_session, seeded, other_user, "c")
    command = service.enqueue_command(db_session, escritorio_id=seeded.escritorio_id, usuario_id=first_user.id,
        tipo="prepare_filing", payload={}, idempotency_key="guard-simulation", target_installation_id=first.id)
    assert service.claim_next_command(db_session, installation=other) is None
    assert service.claim_next_command(db_session, installation=second) is None
    assert service.claim_next_command(db_session, installation=first, supported_types=["open_court_login"]) is None
    assert service.claim_next_command(db_session, installation=first, supported_types=["prepare_filing"]).id == command.id
    command.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    with pytest.raises(service.AgentCommandTransitionError):
        service.heartbeat_command(db_session, command=command, installation=first)
    with pytest.raises(service.AgentCommandTransitionError):
        service.complete_command(db_session, command=command, installation=first, resultado={})


def test_after_submit_checkpoint_failure_is_uncertain_and_not_claimable(db_session, seeded):
    user = db_session.query(models.Usuario).first()
    agent = installation(db_session, seeded, user, "d")
    command = service.enqueue_command(db_session, escritorio_id=seeded.escritorio_id, usuario_id=user.id,
        tipo="prepare_filing", payload={}, idempotency_key="guard-submit")
    service.claim_next_command(db_session, installation=agent)
    for stage in ("prepared", "submitting"):
        service.checkpoint_command(db_session, command=command, installation=agent, stage=stage)
    command.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    service.fail_command(db_session, command=command, installation=agent, erro_codigo="network_error")
    assert command.status == "resultado_incerto"
    assert service.claim_next_command(db_session, installation=agent) is None


class SimulatedApi:
    def __init__(self):
        self.command = {"id": 1, "tipo": "prepare_filing", "payload": {"simulation": True}}
        self.stages, self.failures, self.completed = [], [], []
        self.supported = []
        self.online = True

    def claim(self, supported_types):
        self.supported = supported_types
        if "prepare_filing" not in supported_types:
            return None
        result, self.command = self.command, None
        return result

    def heartbeat(self, command_id):
        if not self.online:
            raise ConnectionError("connection unavailable")

    def checkpoint(self, command_id, stage):
        self.stages.append(stage)

    def fail(self, command_id, code, detail):
        self.failures.append(code)

    def complete(self, command_id, result):
        self.completed.append(result)


def test_simulated_timeout_after_submit_never_repeats_operation():
    api = SimulatedApi()
    submissions = []
    def run(payload, guard):
        guard.stage("prepared")
        def submit():
            submissions.append(1)
            raise TimeoutError("response lost after submission")
        return guard.submit_once(submit)
    worker = AgentWorker(api, handlers={"prepare_filing": GuardedHandler(run)})
    assert worker.run_once()
    assert not worker.run_once()
    assert submissions == [1] and api.stages == ["prepared", "submitting"]
    assert api.failures == ["result_uncertain"] and not api.completed


def test_lost_ownership_prevents_next_step_and_unguarded_filing_is_not_claimed():
    api = SimulatedApi()
    guard = CommandGuard(api, 1, Event())
    api.online = False
    calls = []
    with pytest.raises(OwnershipLost):
        guard.submit_once(lambda: calls.append(1) or {})
    assert not calls and not api.stages
    worker = AgentWorker(api, handlers={"prepare_filing": lambda payload: {"wrong": True}})
    assert not worker.run_once()
    assert "prepare_filing" not in api.supported


def test_simulator_rejects_retargeted_package_or_changed_bytes_before_submit():
    from hashlib import sha256
    from dataclasses import replace
    from app.filing.package_contract import ApprovedFile, ApprovedPackage
    data = b"synthetic-approved-pdf"
    package = ApprovedPackage(1, "a" * 64, (("tribunal", "SINTETICO"), ("grau", "2")),
        (ApprovedFile("peticao.pdf", data, sha256(data).hexdigest()),))
    package.verify(fingerprint="a" * 64, destination={"tribunal": "SINTETICO", "grau": "2"})
    with pytest.raises(ValueError):
        package.verify(fingerprint="a" * 64, destination={"tribunal": "OUTRO", "grau": "2"})
    changed = replace(package, files=(replace(package.files[0], content=b"changed"),))
    with pytest.raises(ValueError):
        changed.verify(fingerprint="a" * 64, destination=dict(package.destination))


def test_old_executor_cannot_claim_irreversible_command(db_session, seeded):
    user = db_session.query(models.Usuario).first()
    agent = installation(db_session, seeded, user, "f")
    agent.version = "0.1.0"
    service.enqueue_command(db_session, escritorio_id=seeded.escritorio_id, usuario_id=user.id,
        tipo="prepare_filing", payload={}, idempotency_key="old-executor")
    assert service.claim_next_command(db_session, installation=agent, supported_types=["prepare_filing"]) is None
