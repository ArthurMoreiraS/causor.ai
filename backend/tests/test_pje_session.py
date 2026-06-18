"""Tests for PJe browser-session safety guards."""

import pytest

from app.connectors.pje.session import PjeSessionError, validate_training_base_url


def test_validate_training_base_url_allows_training_hosts():
    validate_training_base_url("https://pje-treinamento.tjsp.jus.br/pje")
    validate_training_base_url("https://pje-homolog.trf3.jus.br/pje")


def test_validate_training_base_url_blocks_production_looking_hosts(monkeypatch):
    monkeypatch.delenv("CAUSOR_PJE_ALLOW_PROD", raising=False)

    with pytest.raises(PjeSessionError, match="bloqueado"):
        validate_training_base_url("https://pje.tjsp.jus.br/pje")


def test_validate_training_base_url_allows_prod_only_with_explicit_flag(monkeypatch):
    monkeypatch.setenv("CAUSOR_PJE_ALLOW_PROD", "1")

    validate_training_base_url("https://pje.tjsp.jus.br/pje")
