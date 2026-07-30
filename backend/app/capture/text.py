"""Saneamento de texto vindo de API de terceiro.

Os dados do DataJud chegam com corrupção de encoding **na origem**. Verificado ao
vivo em 2026-07-29: para o processo ``00018704220198140069`` do STJ, a API pública
devolve ``PRESID`` + U+FFFD + U+008A + ``NCIA`` onde deveria vir ``PRESIDÊNCIA``.
Não é o nosso decode — ``response.json()`` lê os bytes corretamente; o CNJ já
serializa o caractere quebrado.

Dois padrões são tratados:

1. **U+FFFD seguido de um caractere na faixa U+0080..U+00BF.** É uma sequência
   UTF-8 de dois bytes cujo byte-líder foi substituído antes de chegar até nós.
   Para letra acentuada do português o líder é sempre ``0xC3``, o que torna a
   reconstrução determinística: ``codepoint = 0xC0 | (seguinte & 0x3F)``.
   Exemplo: U+008A vira ``0xC0 | 0x0A`` = U+00CA = ``Ê``.
2. **Mojibake clássico** (UTF-8 lido como cp1252). Recuperável pelo round-trip;
   se o texto não for de fato mojibake o decode falha e devolvemos o original
   intacto.

O que sobrar irrecuperável (U+FFFD sem par válido) é removido, porque a UI o
renderiza como caixa/losango e isso lê como bug do Causor.
"""

from __future__ import annotations

REPLACEMENT_CHAR = chr(0xFFFD)

# Faixa de byte de continuação de UTF-8 (10xxxxxx) preservada pelo decode.
_CONTINUACAO_MIN = 0x80
_CONTINUACAO_MAX = 0xBF

# Assinaturas de UTF-8 lido como cp1252/latin-1.
_MARCADORES_MOJIBAKE = ("Ã", "Â", "â€")


def _reconstruir_lider_perdido(texto: str) -> str:
    """Reune U+FFFD + continuação numa única letra acentuada."""
    saida: list[str] = []
    i = 0
    while i < len(texto):
        char = texto[i]
        if char != REPLACEMENT_CHAR:
            saida.append(char)
            i += 1
            continue

        seguinte = ord(texto[i + 1]) if i + 1 < len(texto) else None
        if seguinte is not None and _CONTINUACAO_MIN <= seguinte <= _CONTINUACAO_MAX:
            saida.append(chr(0xC0 | (seguinte & 0x3F)))
            i += 2
            continue

        # Sem par válido não há o que reconstruir: descarta o ilegível.
        i += 1

    return "".join(saida)


def sanitize_upstream_text(value: str | None) -> str | None:
    """Devolve o texto legível, ou o original quando não há nada a recuperar."""
    if not value:
        return value

    texto = _reconstruir_lider_perdido(value)

    if any(marcador in texto for marcador in _MARCADORES_MOJIBAKE):
        try:
            texto = texto.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass  # não era mojibake; mantém como está

    return texto
