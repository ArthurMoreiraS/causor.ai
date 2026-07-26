"""Varre candidatos de endpoint MNI e reporta quais servem WSDL de verdade.

Evidencia, nao palpite: so entra no relatorio quem devolve wsdl:definitions.
"""
from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor

import httpx

TJ_UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DFT", "ES", "GO", "MA", "MG", "MS",
    "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
    "SE", "SP", "TO",
]

def candidates() -> list[tuple[str, str, str]]:
    """(tribunal, grau, url)"""
    out: list[tuple[str, str, str]] = []
    for uf in TJ_UFS:
        t = f"TJ{uf}"
        host = f"tj{uf.lower()}.jus.br"
        out += [
            (t, "1", f"https://pje.{host}/pje/intercomunicacao?wsdl"),
            (t, "1", f"https://pje1g.{host}/pje/intercomunicacao?wsdl"),
            (t, "1", f"https://pje.{host}/1g/intercomunicacao?wsdl"),
            (t, "2", f"https://pje2g.{host}/pje/intercomunicacao?wsdl"),
            (t, "2", f"https://pje2i.{host}/pje/intercomunicacao?wsdl"),
            (t, "2", f"https://pje2.{host}/pje2g/intercomunicacao?wsdl"),
            (t, "2", f"https://pje.{host}/2g/intercomunicacao?wsdl"),
        ]
    for n in range(1, 7):
        t, host = f"TRF{n}", f"trf{n}.jus.br"
        out += [
            (t, "1", f"https://pje.{host}/pje/intercomunicacao?wsdl"),
            (t, "1", f"https://pje1g.{host}/pje/intercomunicacao?wsdl"),
            (t, "2", f"https://pje2g.{host}/pje/intercomunicacao?wsdl"),
        ]
    for n in range(1, 25):
        t, host = f"TRT{n}", f"trt{n}.jus.br"
        out += [
            (t, "1", f"https://pje.{host}/primeirograu/servicosweb/mni222/intercomunicacao?wsdl"),
            (t, "2", f"https://pje.{host}/segundograu/servicosweb/mni222/intercomunicacao?wsdl"),
            (t, "1", f"https://pje.{host}/pje-integracao-api/mni300/intercomunicacao?wsdl"),
            (t, "1", f"https://pje.{host}/primeirograu/intercomunicacao?wsdl"),
        ]
    return out


NS = re.compile(r'targetNamespace="http://www\.cnj\.jus\.br/servico-intercomunicacao-([\d.]+)/"')


def check(item: tuple[str, str, str]) -> tuple[str, str, str, str] | None:
    tribunal, grau, url = item
    try:
        r = httpx.get(url, timeout=15, verify=False, follow_redirects=True)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    body = r.text
    if "wsdl:definitions" not in body and "<definitions" not in body:
        return None
    m = NS.search(body)
    versao = m.group(1) if m else "?"
    ops = sorted(set(re.findall(r'operation name="([^"]+)"', body)))
    return (tribunal, grau, url.replace("?wsdl", ""), f"{versao}|{','.join(ops)}")


def main() -> int:
    cands = candidates()
    print(f"probing {len(cands)} candidates...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=32) as pool:
        results = [r for r in pool.map(check, cands) if r]
    for tribunal, grau, url, meta in sorted(results):
        print(f"{tribunal}\t{grau}\t{url}\t{meta}")
    print(f"\n{len(results)} endpoints vivos", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
