"""Tests for the signature provider seam (manual_handoff mode)."""

import pytest

from app.signing.providers import (
    SignatureHandoff,
    SignatureProvider,
    get_signature_provider,
)


def test_birdid_manual_handoff_message_and_actions():
    provider = get_signature_provider("birdid", modo="manual_handoff")
    handoff = provider.handoff()

    assert isinstance(handoff, SignatureHandoff)
    assert handoff.provedor == "birdid"
    assert handoff.modo == "manual_handoff"
    assert "BirdID" in handoff.mensagem
    assert handoff.acoes == ["abrir_pje", "ja_assinei", "cancelar"]
    assert handoff.instrucoes  # non-empty step list


def test_pjeoffice_message_differs_from_birdid():
    birdid = get_signature_provider("birdid").handoff()
    pjeoffice = get_signature_provider("pjeoffice").handoff()

    assert birdid.mensagem != pjeoffice.mensagem
    assert "PJeOffice" in pjeoffice.mensagem


def test_default_modo_is_manual_handoff():
    provider = get_signature_provider("vidaas")
    assert provider.handoff().modo == "manual_handoff"


def test_unknown_provider_falls_back_to_generic():
    handoff = get_signature_provider("provedor-inexistente").handoff()

    assert isinstance(handoff, SignatureHandoff)
    assert handoff.acoes == ["abrir_pje", "ja_assinei", "cancelar"]
    assert handoff.mensagem  # generic message is still produced


def test_none_provider_falls_back_to_generic():
    handoff = get_signature_provider(None).handoff()
    assert handoff.mensagem


def test_request_signature_not_implemented_in_manual_handoff():
    provider = get_signature_provider("birdid", modo="manual_handoff")
    with pytest.raises(NotImplementedError):
        provider.request_signature()


def test_provider_is_signature_provider_instance():
    assert isinstance(get_signature_provider("a3"), SignatureProvider)
