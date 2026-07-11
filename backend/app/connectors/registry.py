"""Registry fail-closed de drivers reais por (sistema, tribunal, grau).

Sem fallback silencioso de família: um perfil não registrado levanta
``UnsupportedConnectorProfile`` em vez de tentar um driver genérico. O modo
sandbox continua separado em ``drivers.get_filing_driver``.
"""

from __future__ import annotations


class UnsupportedConnectorProfile(RuntimeError):
    """Perfil (sistema, tribunal, grau) sem driver registrado."""


class DuplicateConnectorProfile(RuntimeError):
    """Tentativa de registrar duas vezes o mesmo perfil."""


def _key(sistema: str, tribunal: str, grau: str) -> tuple[str, str, str]:
    return (sistema.casefold(), tribunal.upper(), grau)


class ConnectorRegistry:
    def __init__(self) -> None:
        self._readers: dict[tuple[str, str, str], type] = {}
        self._filings: dict[tuple[str, str, str], type] = {}

    def register_reader(self, sistema: str, driver: type, *, tribunal: str, grau: str) -> None:
        key = _key(sistema, tribunal, grau)
        if key in self._readers:
            raise DuplicateConnectorProfile(f"reader já registrado: {key}")
        self._readers[key] = driver

    def register_filing(self, sistema: str, driver: type, *, tribunal: str, grau: str) -> None:
        key = _key(sistema, tribunal, grau)
        if key in self._filings:
            raise DuplicateConnectorProfile(f"filing já registrado: {key}")
        self._filings[key] = driver

    def reader(self, sistema: str, *, tribunal: str, grau: str) -> type:
        key = _key(sistema, tribunal, grau)
        try:
            return self._readers[key]
        except KeyError:
            raise UnsupportedConnectorProfile(
                f"sem leitor registrado para {sistema} · {tribunal} · {grau}º grau"
            ) from None

    def filing(self, sistema: str, *, tribunal: str, grau: str) -> type:
        key = _key(sistema, tribunal, grau)
        try:
            return self._filings[key]
        except KeyError:
            raise UnsupportedConnectorProfile(
                f"sem protocolo registrado para {sistema} · {tribunal} · {grau}º grau"
            ) from None


_REGISTRY: ConnectorRegistry | None = None


def get_connector_registry() -> ConnectorRegistry:
    """Registry global; drivers reais se registram na importação do agente."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ConnectorRegistry()
    return _REGISTRY
