import pytest

from app.connectors.registry import (
    ConnectorRegistry,
    DuplicateConnectorProfile,
    UnsupportedConnectorProfile,
)


class FakeReader:
    sistema = "PJe"


class FakeFiling:
    sistema = "PJe"


def test_registry_resolves_exact_profile_before_family_default():
    registry = ConnectorRegistry()
    registry.register_reader("PJe", FakeReader, tribunal="TJMG", grau="1")
    resolved = registry.reader("PJe", tribunal="TJMG", grau="1")
    assert resolved is FakeReader


def test_registry_fails_closed_without_registered_profile():
    registry = ConnectorRegistry()
    with pytest.raises(UnsupportedConnectorProfile):
        registry.reader("EPROC", tribunal="TJRS", grau="1")


def test_registry_key_is_case_insensitive_for_system_and_court():
    registry = ConnectorRegistry()
    registry.register_reader("PJe", FakeReader, tribunal="TJMG", grau="1")
    assert registry.reader("pje", tribunal="tjmg", grau="1") is FakeReader


def test_registry_rejects_duplicate_registration():
    registry = ConnectorRegistry()
    registry.register_reader("PJe", FakeReader, tribunal="TJMG", grau="1")
    with pytest.raises(DuplicateConnectorProfile):
        registry.register_reader("PJe", FakeReader, tribunal="TJMG", grau="1")


def test_registry_separates_reader_and_filing_registrations():
    registry = ConnectorRegistry()
    registry.register_reader("PJe", FakeReader, tribunal="TJMG", grau="1")
    with pytest.raises(UnsupportedConnectorProfile):
        registry.filing("PJe", tribunal="TJMG", grau="1")
    registry.register_filing("PJe", FakeFiling, tribunal="TJMG", grau="1")
    assert registry.filing("PJe", tribunal="TJMG", grau="1") is FakeFiling


def test_registry_does_not_fall_back_to_another_degree():
    registry = ConnectorRegistry()
    registry.register_reader("PJe", FakeReader, tribunal="TJMG", grau="1")
    with pytest.raises(UnsupportedConnectorProfile):
        registry.reader("PJe", tribunal="TJMG", grau="2")
