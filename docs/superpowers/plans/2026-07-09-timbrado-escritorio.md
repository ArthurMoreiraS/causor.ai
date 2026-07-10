# Papel Timbrado por Escritório — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O PDF da minuta sai com o papel timbrado do escritório (logo + cabeçalho + rodapé em toda página), configurável na UI, com preview via "Baixar PDF" antes do protocolo.

**Architecture:** O renderer artesanal de `backend/app/filing/render.py` é substituído por um único caminho fpdf2 que preserva a assinatura pública (`render_minuta_pdf(texto, *, meta, timbrado=None) -> bytes`, função pura). Um módulo novo `app/filing/timbrado.py` faz a ponte com o SOR (dataclass + `load_timbrado`) e normaliza o logo na entrada (Pillow → PNG ≤1000px). A API estende o perfil operacional existente (GET/PATCH `/settings/profile`) e ganha `GET /peticoes/{id}/pdf`; o job de protocolo passa a entregar o timbrado ao renderer.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy/Alembic (backend), fpdf2 (PDF, traz Pillow), pypdf (dev, extração de texto nos testes), Next.js/React + vitest (frontend).

**Spec:** `docs/superpowers/specs/2026-07-09-timbrado-escritorio-design.md`. Correção descoberta no planejamento: o formulário de perfil vive em `frontend/app/SettingsModal.tsx` (seção "Perfil do software"), não em `ProfileModal.tsx` — a Task 9 aplica lá e a Task 11 corrige o spec.

## Global Constraints

- Comandos do backend rodam **de dentro de `backend/`** com o venv do projeto: `./.venv/Scripts/python.exe` (Windows). Frontend usa `pnpm` de dentro de `frontend/`.
- TDD: teste falhando antes da implementação, em toda task com código.
- Testes rodam em SQLite in-memory (fixture `db_session` de `backend/tests/conftest.py`); **não usar tipos de coluna Postgres-only** (LargeBinary/Text/String são compatíveis).
- Segredos nunca em prompts ou logs; o logo do timbrado NÃO é segredo, mas os bytes não devem ir para o audit log (registrar apenas "atualizado"/"removido").
- Lint: `ruff check .` com line-length 100 (backend); `pnpm lint --max-warnings=0` e `pnpm typecheck` (frontend).
- Strings de UI e mensagens de erro em português, seguindo o padrão dos arquivos tocados.
- Commits frequentes, mensagens no padrão do repo (`feat(escopo): descrição em pt`).

---

### Task 1: Dependências (fpdf2 + pypdf) e fontes DejaVu

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/filing/fonts/DejaVuSans.ttf`
- Create: `backend/app/filing/fonts/DejaVuSans-Bold.ttf`
- Create: `backend/app/filing/fonts/LICENSE` (licença DejaVu — obrigatória para redistribuir)

**Interfaces:**
- Consumes: nada.
- Produces: `import fpdf`, `import pypdf`, `from PIL import Image` funcionam no venv; fontes em `backend/app/filing/fonts/` para a Task 4.

- [ ] **Step 1: Adicionar dependências ao pyproject**

Em `backend/pyproject.toml`, acrescentar `"fpdf2>=2.8"` à lista `dependencies` (após `"playwright>=1.45",`) e `"pypdf>=5.0"` à lista `dev` (após `"pytest-httpx>=0.30",`).

- [ ] **Step 2: Instalar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pip install -e ".[dev]"`
Expected: instala `fpdf2`, `pillow` (dependência do fpdf2) e `pypdf` sem erro.

- [ ] **Step 3: Baixar as fontes DejaVu para o repo**

Run (em `backend/`, PowerShell):

```powershell
New-Item -ItemType Directory -Force app\filing\fonts
Invoke-WebRequest -Uri https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip -OutFile $env:TEMP\dejavu.zip
Expand-Archive $env:TEMP\dejavu.zip -DestinationPath $env:TEMP\dejavu -Force
Copy-Item $env:TEMP\dejavu\dejavu-fonts-ttf-2.37\ttf\DejaVuSans.ttf app\filing\fonts\
Copy-Item $env:TEMP\dejavu\dejavu-fonts-ttf-2.37\ttf\DejaVuSans-Bold.ttf app\filing\fonts\
Copy-Item $env:TEMP\dejavu\dejavu-fonts-ttf-2.37\LICENSE app\filing\fonts\LICENSE
```

- [ ] **Step 4: Verificar**

Run (em `backend/`): `./.venv/Scripts/python.exe -c "import fpdf, pypdf, PIL; print(fpdf.__version__)"`
Expected: imprime a versão do fpdf2 (≥2.8) sem erro.

Run (em `backend/`, PowerShell): `Get-ChildItem app\filing\fonts`
Expected: `DejaVuSans.ttf`, `DejaVuSans-Bold.ttf`, `LICENSE`.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/filing/fonts/
git commit -m "feat(filing): adiciona fpdf2/pypdf e fontes DejaVu para o timbrado"
```

---

### Task 2: Colunas de timbrado no `Escritorio` + migração Alembic

**Files:**
- Modify: `backend/app/sor/models.py:46-55` (classe `Escritorio`) e o bloco de imports do sqlalchemy
- Create: `backend/alembic/versions/f0a1b2c3d4e5_add_escritorio_timbrado.py`
- Test: `backend/tests/test_escritorio_timbrado.py`

**Interfaces:**
- Consumes: nada.
- Produces: colunas ORM `Escritorio.timbrado_logo: bytes | None`, `Escritorio.timbrado_logo_mime: str | None`, `Escritorio.timbrado_cabecalho: str | None`, `Escritorio.timbrado_rodape: str | None`, usadas nas Tasks 3, 5 e 7.

- [ ] **Step 1: Escrever o teste que falha**

Create `backend/tests/test_escritorio_timbrado.py`:

```python
"""Colunas de timbrado no Escritorio persistem no SOR."""

from app.sor import models


def test_escritorio_persiste_campos_de_timbrado(db_session):
    esc = models.Escritorio(
        nome="Esc",
        timbrado_logo=b"\x89PNG\r\n\x1a\nfake",
        timbrado_logo_mime="image/png",
        timbrado_cabecalho="Av. Paulista, 1000",
        timbrado_rodape="OAB/SP 123.456",
    )
    db_session.add(esc)
    db_session.flush()
    db_session.expire(esc)

    salvo = db_session.get(models.Escritorio, esc.id)
    assert salvo.timbrado_logo == b"\x89PNG\r\n\x1a\nfake"
    assert salvo.timbrado_logo_mime == "image/png"
    assert salvo.timbrado_cabecalho == "Av. Paulista, 1000"
    assert salvo.timbrado_rodape == "OAB/SP 123.456"
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_escritorio_timbrado.py -v`
Expected: FAIL com `TypeError: 'timbrado_logo' is an invalid keyword argument for Escritorio`.

- [ ] **Step 3: Adicionar as colunas ao modelo**

Em `backend/app/sor/models.py`, no bloco `from sqlalchemy import (...)` do topo, acrescentar `LargeBinary` à lista (ordem alfabética). Na classe `Escritorio`, após a linha do `cnpj`, adicionar:

```python
    # Papel timbrado do escritório aplicado no PDF de protocolo (spec 2026-07-09).
    timbrado_logo: Mapped[bytes | None] = mapped_column(LargeBinary)
    timbrado_logo_mime: Mapped[str | None] = mapped_column(String(30))
    timbrado_cabecalho: Mapped[str | None] = mapped_column(Text)
    timbrado_rodape: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 4: Rodar e ver passar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_escritorio_timbrado.py -v`
Expected: PASS.

- [ ] **Step 5: Confirmar o head atual do Alembic**

Run (em `backend/`): `./.venv/Scripts/alembic.exe heads`
Expected: um único head (pela lista de versões, deve ser `e9a3c1f52b8d`). Use a saída real como `down_revision` no passo seguinte.

- [ ] **Step 6: Criar a migração**

Create `backend/alembic/versions/f0a1b2c3d4e5_add_escritorio_timbrado.py` (ajuste `down_revision` para a saída do Step 5):

```python
"""add escritorio timbrado

Revision ID: f0a1b2c3d4e5
Revises: e9a3c1f52b8d
Create Date: 2026-07-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "e9a3c1f52b8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("escritorio", sa.Column("timbrado_logo", sa.LargeBinary(), nullable=True))
    op.add_column(
        "escritorio", sa.Column("timbrado_logo_mime", sa.String(length=30), nullable=True)
    )
    op.add_column("escritorio", sa.Column("timbrado_cabecalho", sa.Text(), nullable=True))
    op.add_column("escritorio", sa.Column("timbrado_rodape", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("escritorio", "timbrado_rodape")
    op.drop_column("escritorio", "timbrado_cabecalho")
    op.drop_column("escritorio", "timbrado_logo_mime")
    op.drop_column("escritorio", "timbrado_logo")
```

- [ ] **Step 7: Validar a migração contra o Supabase (banco de produção)**

Não usamos Postgres local para validar o timbrado: o teste manual roda contra
o Supabase de produção com a conta de teste. No deploy do Render a migração é
aplicada automaticamente (`alembic upgrade head` no release). Para aplicar ou
conferir manualmente antes do deploy:

Run (em `backend/`, PowerShell): `$env:CAUSOR_DATABASE_URL = '<string do Supabase Postgres (pooler, porta 6543)>'; ./.venv/Scripts/alembic.exe upgrade head`
Expected: `Running upgrade e9a3c1f52b8d -> f0a1b2c3d4e5` — ou nenhuma ação, se o release do Render já aplicou. A string de produção entra só como variável de ambiente da sessão; nunca em arquivo commitado (o teste do Step 4 já valida o metadata via `create_all`).

- [ ] **Step 8: Rodar a suíte inteira e commitar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest -q`
Expected: tudo verde.

```bash
git add backend/app/sor/models.py backend/alembic/versions/f0a1b2c3d4e5_add_escritorio_timbrado.py backend/tests/test_escritorio_timbrado.py
git commit -m "feat(sor): colunas de papel timbrado no escritorio"
```

---

### Task 3: Módulo `app/filing/timbrado.py` (dataclass + normalização + carga)

**Files:**
- Create: `backend/app/filing/timbrado.py`
- Test: `backend/tests/test_filing_timbrado.py`

**Interfaces:**
- Consumes: colunas `Escritorio.timbrado_*` (Task 2).
- Produces (usados nas Tasks 4–7):
  - `TimbradoEscritorio` — dataclass frozen com `nome: str`, `cabecalho: str | None`, `rodape: str | None`, `logo: bytes | None`, `logo_mime: str | None` (todos com default `None` exceto `nome`).
  - `normalize_logo(data: bytes) -> bytes` — valida PNG/JPEG ≤2MB, re-encoda para PNG ≤1000px de largura; levanta `LogoInvalidoError`.
  - `load_timbrado(session: Session, escritorio_id: int | None) -> TimbradoEscritorio | None` — `None` quando nada configurado.
  - `LogoInvalidoError(ValueError)`.
  - Constantes `MAX_LOGO_UPLOAD_BYTES = 2 * 1024 * 1024`, `MAX_LOGO_LARGURA_PX = 1000`.

- [ ] **Step 1: Escrever os testes que falham**

Create `backend/tests/test_filing_timbrado.py`:

```python
"""Timbrado: normalização do logo e carga a partir do SOR."""

import io

import pytest
from PIL import Image

from app.filing.timbrado import (
    LogoInvalidoError,
    TimbradoEscritorio,
    load_timbrado,
    normalize_logo,
)
from app.sor import models


def _imagem(formato: str, largura: int = 100, altura: int = 40) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), "navy").save(buf, format=formato)
    return buf.getvalue()


def test_normalize_logo_reencoda_jpeg_para_png():
    resultado = normalize_logo(_imagem("JPEG"))
    assert resultado.startswith(b"\x89PNG")


def test_normalize_logo_redimensiona_acima_de_1000px():
    resultado = normalize_logo(_imagem("PNG", largura=1500, altura=300))
    with Image.open(io.BytesIO(resultado)) as img:
        assert img.width == 1000
        assert img.height == 200


def test_normalize_logo_rejeita_formato_nao_suportado():
    with pytest.raises(LogoInvalidoError):
        normalize_logo(b"GIF89a" + b"\x00" * 32)


def test_normalize_logo_rejeita_acima_de_2mb():
    grande = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024)
    with pytest.raises(LogoInvalidoError):
        normalize_logo(grande)


def test_normalize_logo_rejeita_bytes_corrompidos():
    with pytest.raises(LogoInvalidoError):
        normalize_logo(b"\x89PNG\r\n\x1a\n" + b"lixo")


def test_load_timbrado_sem_configuracao_retorna_none(db_session):
    esc = models.Escritorio(nome="Esc")
    db_session.add(esc)
    db_session.flush()

    assert load_timbrado(db_session, esc.id) is None
    assert load_timbrado(db_session, None) is None


def test_load_timbrado_monta_dataclass(db_session):
    esc = models.Escritorio(
        nome="Moura & Santos",
        timbrado_cabecalho="Av. Paulista, 1000",
        timbrado_rodape="OAB/SP 123.456",
        timbrado_logo=normalize_logo(_imagem("PNG")),
        timbrado_logo_mime="image/png",
    )
    db_session.add(esc)
    db_session.flush()

    timbrado = load_timbrado(db_session, esc.id)

    assert timbrado == TimbradoEscritorio(
        nome="Moura & Santos",
        cabecalho="Av. Paulista, 1000",
        rodape="OAB/SP 123.456",
        logo=esc.timbrado_logo,
        logo_mime="image/png",
    )
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_filing_timbrado.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.filing.timbrado'`.

- [ ] **Step 3: Implementar o módulo**

Create `backend/app/filing/timbrado.py`:

```python
"""Timbrado por escritório: dados para o renderer e normalização do logo.

O renderer é função pura; este módulo faz a ponte com o SOR (load_timbrado)
e garante na entrada (normalize_logo) que todo logo armazenado é um PNG
pequeno e válido — o render nunca falha por imagem ruim e o PDF fica dentro
dos limites de tamanho dos tribunais.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image
from sqlalchemy.orm import Session

from app.sor import models

MAX_LOGO_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_LOGO_LARGURA_PX = 1000


class LogoInvalidoError(ValueError):
    """Upload de logo rejeitado (formato, tamanho ou bytes corrompidos)."""


@dataclass(frozen=True)
class TimbradoEscritorio:
    nome: str
    cabecalho: str | None = None
    rodape: str | None = None
    logo: bytes | None = None
    logo_mime: str | None = None


def normalize_logo(data: bytes) -> bytes:
    """Valida e re-encoda o logo para PNG sem metadados, largura <= 1000px."""
    if len(data) > MAX_LOGO_UPLOAD_BYTES:
        raise LogoInvalidoError("logo acima do limite de 2MB")
    eh_png = data.startswith(b"\x89PNG\r\n\x1a\n")
    eh_jpeg = data.startswith(b"\xff\xd8\xff")
    if not (eh_png or eh_jpeg):
        raise LogoInvalidoError("logo deve ser PNG ou JPEG")
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                img = img.convert("RGB")
            if img.width > MAX_LOGO_LARGURA_PX:
                proporcao = MAX_LOGO_LARGURA_PX / img.width
                img = img.resize((MAX_LOGO_LARGURA_PX, max(1, round(img.height * proporcao))))
            saida = io.BytesIO()
            img.save(saida, format="PNG", optimize=True)
            return saida.getvalue()
    except LogoInvalidoError:
        raise
    except Exception as exc:
        raise LogoInvalidoError("logo inválido ou corrompido") from exc


def load_timbrado(session: Session, escritorio_id: int | None) -> TimbradoEscritorio | None:
    """Monta o timbrado do escritório; None quando nada foi configurado."""
    if escritorio_id is None:
        return None
    esc = session.get(models.Escritorio, escritorio_id)
    if esc is None:
        return None
    if not (esc.timbrado_logo or esc.timbrado_cabecalho or esc.timbrado_rodape):
        return None
    return TimbradoEscritorio(
        nome=esc.nome,
        cabecalho=esc.timbrado_cabecalho,
        rodape=esc.timbrado_rodape,
        logo=esc.timbrado_logo,
        logo_mime=esc.timbrado_logo_mime,
    )
```

- [ ] **Step 4: Rodar e ver passar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_filing_timbrado.py -v`
Expected: PASS (7 testes).

- [ ] **Step 5: Lint e commit**

Run (em `backend/`): `./.venv/Scripts/python.exe -m ruff check app/filing/timbrado.py tests/test_filing_timbrado.py`
Expected: sem findings.

```bash
git add backend/app/filing/timbrado.py backend/tests/test_filing_timbrado.py
git commit -m "feat(filing): dataclass de timbrado, normalizacao de logo e carga do SOR"
```

---

### Task 4: Renderer fpdf2 com timbrado

**Files:**
- Rewrite: `backend/app/filing/render.py`
- Rewrite: `backend/tests/test_filing_render.py`

**Interfaces:**
- Consumes: `TimbradoEscritorio` (Task 3); fontes em `backend/app/filing/fonts/` (Task 1).
- Produces: `render_minuta_pdf(texto: str, *, meta: dict | None = None, timbrado: TimbradoEscritorio | None = None) -> bytes` — mesma assinatura usada por `jobs.py` hoje, com o parâmetro novo opcional. Tasks 6 e 7 chamam com `timbrado=`.

- [ ] **Step 1: Reescrever os testes (falham contra o renderer atual)**

Rewrite `backend/tests/test_filing_render.py` por inteiro (o teste antigo fazia grep de bytes crus, o que deixa de funcionar com streams comprimidos e fonte TTF subsetada — a extração passa a usar pypdf):

```python
"""Tests for rendering petition drafts into a filing PDF."""

import io

from PIL import Image
from pypdf import PdfReader

from app.filing.render import render_minuta_pdf
from app.filing.timbrado import TimbradoEscritorio


def _texto_do_pdf(pdf: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _png_bytes(largura: int = 60, altura: int = 20) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), "red").save(buf, format="PNG")
    return buf.getvalue()


def _timbrado(**overrides) -> TimbradoEscritorio:
    base = dict(
        nome="Moura & Santos Advogados",
        cabecalho="Av. Paulista, 1000 - São Paulo/SP\ncontato@moura.adv.br",
        rodape="OAB/SP 123.456 · moura.adv.br",
        logo=_png_bytes(),
        logo_mime="image/png",
    )
    base.update(overrides)
    return TimbradoEscritorio(**base)


def test_render_sem_timbrado_mantem_formato_neutro():
    pdf = render_minuta_pdf(
        "Excelentissimo Juizo\n\nRequer a juntada da manifestacao.",
        meta={"processo": "0000001-00.2024.8.26.0100", "tipo": "Manifestacao"},
    )

    assert pdf.startswith(b"%PDF")
    texto = _texto_do_pdf(pdf)
    assert "Causor - Minuta para protocolo" in texto
    assert "Excelentissimo Juizo" in texto
    assert "0000001-00.2024.8.26.0100" in texto


def test_render_com_timbrado_estampa_cabecalho_e_rodape():
    pdf = render_minuta_pdf("Corpo da peça.", meta={"processo": "123"}, timbrado=_timbrado())

    texto = _texto_do_pdf(pdf)
    assert "Moura & Santos Advogados" in texto
    assert "Av. Paulista, 1000 - São Paulo/SP" in texto
    assert "OAB/SP 123.456 · moura.adv.br" in texto
    assert "Corpo da peça." in texto
    assert "página 1 de 1" in texto
    assert "Causor - Minuta para protocolo" not in texto


def test_render_multipagina_repete_timbrado_em_toda_pagina():
    corpo = "\n".join(f"Parágrafo {i} da fundamentação." for i in range(200))
    pdf = render_minuta_pdf(corpo, timbrado=_timbrado())

    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) >= 2
    ultima = reader.pages[-1].extract_text() or ""
    assert "Moura & Santos Advogados" in ultima
    assert f"página {len(reader.pages)} de {len(reader.pages)}" in ultima


def test_render_aceita_caracteres_fora_do_latin1():
    pdf = render_minuta_pdf("Cita-se o “precedente” — grifo nosso.", timbrado=_timbrado())

    texto = _texto_do_pdf(pdf)
    assert "“precedente”" in texto
    assert "—" in texto


def test_render_timbrado_sem_logo_nao_quebra():
    pdf = render_minuta_pdf("Texto.", timbrado=_timbrado(logo=None, logo_mime=None))

    assert pdf.startswith(b"%PDF")
    assert "Moura & Santos Advogados" in _texto_do_pdf(pdf)
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_filing_render.py -v`
Expected: FAIL (`render_minuta_pdf` atual não aceita `timbrado=` e o texto neutro não extrai via pypdf do PDF artesanal — qualquer um dos dois erros serve como vermelho).

- [ ] **Step 3: Reescrever o renderer**

Rewrite `backend/app/filing/render.py` por inteiro:

```python
"""Render petition drafts into PDF bytes for court filing."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image

from app.filing.timbrado import TimbradoEscritorio

_FONT_DIR = Path(__file__).parent / "fonts"
_PAGE_WIDTH_MM = 210.0


class _MinutaPDF(FPDF):
    """A4 com cabeçalho/rodapé repetidos por página quando há timbrado."""

    def __init__(self, timbrado: TimbradoEscritorio | None) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.timbrado = timbrado
        self.add_font("DejaVu", "", str(_FONT_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(_FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=30)

    def header(self) -> None:
        t = self.timbrado
        if t is None:
            return
        y = 10.0
        if t.logo:
            # Centraliza o logo com 14mm de altura preservando a proporção.
            with Image.open(io.BytesIO(t.logo)) as img:
                largura_mm = min(14.0 * img.width / img.height, 60.0)
            self.image(io.BytesIO(t.logo), x=(_PAGE_WIDTH_MM - largura_mm) / 2, y=y, h=14.0)
            y += 16.0
        self.set_y(y)
        self.set_font("DejaVu", "B", 11)
        self.cell(0, 5.5, t.nome, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if t.cabecalho:
            self.set_font("DejaVu", "", 8)
            self.set_text_color(90)
            for linha in t.cabecalho.splitlines():
                self.cell(0, 4, linha, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_text_color(0)
        self.ln(2)
        self.set_draw_color(170)
        self.line(self.l_margin, self.get_y(), _PAGE_WIDTH_MM - self.r_margin, self.get_y())
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-24)
        self.set_font("DejaVu", "", 7.5)
        self.set_text_color(120)
        t = self.timbrado
        if t is not None:
            self.set_draw_color(170)
            self.line(self.l_margin, self.get_y(), _PAGE_WIDTH_MM - self.r_margin, self.get_y())
            self.ln(2)
            if t.rodape:
                for linha in t.rodape.splitlines():
                    self.cell(0, 3.8, linha, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 3.8, f"página {self.page_no()} de {{nb}}", align="R")
        self.set_text_color(0)


def render_minuta_pdf(
    texto: str,
    *,
    meta: dict | None = None,
    timbrado: TimbradoEscritorio | None = None,
) -> bytes:
    """PDF da minuta: neutro sem timbrado; com timbrado, identidade do
    escritório em toda página. Função pura — o timbrado chega pronto de
    load_timbrado, sem acesso a banco aqui."""

    meta = meta or {}
    pdf = _MinutaPDF(timbrado)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(90)
    if timbrado is None:
        pdf.set_font("DejaVu", "B", 11)
        pdf.set_text_color(0)
        pdf.cell(0, 6, "Causor - Minuta para protocolo", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(90)
        gerado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        pdf.cell(0, 5, f"Gerado em: {gerado}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for rotulo, chave in (("Processo", "processo"), ("Tipo", "tipo"), ("Tribunal", "tribunal")):
        if meta.get(chave):
            pdf.cell(0, 5, f"{rotulo}: {meta[chave]}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0)
    pdf.ln(4)

    pdf.set_font("DejaVu", "", 10.5)
    pdf.multi_cell(0, 5.5, texto or "", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())
```

Nota de design registrada no spec: o renderer antigo era byte-determinístico; nenhum teste depende disso (as asserções são por texto extraído), então a data de criação real do fpdf2 é mantida — ela é útil como evidência de protocolo.

- [ ] **Step 4: Rodar e ver passar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_filing_render.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Rodar a suíte inteira (o job de protocolo usa o renderer)**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest -q`
Expected: tudo verde — a assinatura antiga (`texto`, `meta=`) continua aceita.

- [ ] **Step 6: Lint e commit**

Run (em `backend/`): `./.venv/Scripts/python.exe -m ruff check app/filing/ tests/test_filing_render.py`
Expected: sem findings.

```bash
git add backend/app/filing/render.py backend/tests/test_filing_render.py
git commit -m "feat(filing): renderer fpdf2 com papel timbrado por pagina"
```

---

### Task 5: API do perfil — timbrado no GET/PATCH `/settings/profile`

**Files:**
- Modify: `backend/app/api/schemas.py:159-184` (`EscritorioOut`, `OperationalProfileUpdate`)
- Modify: `backend/app/api/main.py:401-442` (handler do PATCH) + imports do topo
- Test: `backend/tests/test_api.py` (novos testes ao final)

**Interfaces:**
- Consumes: `normalize_logo`, `LogoInvalidoError` (Task 3); colunas `Escritorio.timbrado_*` (Task 2).
- Produces: contrato da API usado pela Task 8/9 — GET devolve `escritorio.timbrado_cabecalho: str | null`, `escritorio.timbrado_rodape: str | null`, `escritorio.timbrado_logo: str | null` (base64 de PNG); PATCH aceita os três (logo em base64; string vazia remove; strings de texto vazias limpam o campo).

- [ ] **Step 1: Escrever os testes que falham**

Ao final de `backend/tests/test_api.py`, adicionar (e garantir no topo do arquivo os imports `import base64`, `import io`, `from PIL import Image` — mantenha os imports existentes):

```python
def _png_para_upload(largura: int = 10, altura: int = 10) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), "red").save(buf, format="PNG")
    return buf.getvalue()


def test_settings_profile_atualiza_timbrado(client, db_session, seeded):
    resp = client.patch(
        "/settings/profile",
        json={
            "timbrado_cabecalho": "Rua X, 100 - São Paulo/SP",
            "timbrado_rodape": "OAB/SP 123.456 · causor.com",
            "timbrado_logo": base64.b64encode(_png_para_upload()).decode("ascii"),
        },
    )

    assert resp.status_code == 200
    esc = resp.json()["escritorio"]
    assert esc["timbrado_cabecalho"] == "Rua X, 100 - São Paulo/SP"
    assert esc["timbrado_rodape"] == "OAB/SP 123.456 · causor.com"
    armazenado = base64.b64decode(esc["timbrado_logo"])
    assert armazenado.startswith(b"\x89PNG")

    lido = client.get("/settings/profile").json()["escritorio"]
    assert lido["timbrado_cabecalho"] == "Rua X, 100 - São Paulo/SP"
    assert lido["timbrado_logo"] == esc["timbrado_logo"]


def test_settings_profile_remove_logo_com_string_vazia(client, db_session, seeded):
    client.patch(
        "/settings/profile",
        json={"timbrado_logo": base64.b64encode(_png_para_upload()).decode("ascii")},
    )

    resp = client.patch("/settings/profile", json={"timbrado_logo": ""})

    assert resp.status_code == 200
    assert resp.json()["escritorio"]["timbrado_logo"] is None


def test_settings_profile_rejeita_logo_invalido(client, db_session, seeded):
    nao_imagem = client.patch(
        "/settings/profile",
        json={"timbrado_logo": base64.b64encode(b"nao-e-imagem").decode("ascii")},
    )
    assert nao_imagem.status_code == 422

    base64_quebrado = client.patch("/settings/profile", json={"timbrado_logo": "###"})
    assert base64_quebrado.status_code == 422
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k timbrado -v`
Expected: FAIL — o PATCH ignora os campos (schema não os aceita) e o GET não os devolve.

- [ ] **Step 3: Estender os schemas**

Em `backend/app/api/schemas.py`: adicionar `import base64` no topo (junto dos imports stdlib). Substituir `EscritorioOut` e estender `OperationalProfileUpdate`:

```python
class EscritorioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cnpj: str | None = None
    timbrado_cabecalho: str | None = None
    timbrado_rodape: str | None = None
    # Logo armazenado como bytes no SOR; trafega como base64 na API.
    timbrado_logo: str | None = None

    @field_validator("timbrado_logo", mode="before")
    @classmethod
    def _logo_em_base64(cls, valor: object) -> object:
        if isinstance(valor, (bytes, bytearray, memoryview)):
            return base64.b64encode(bytes(valor)).decode("ascii")
        return valor
```

Em `OperationalProfileUpdate`, após `oab_uf`:

```python
    timbrado_cabecalho: str | None = Field(default=None, max_length=2000)
    timbrado_rodape: str | None = Field(default=None, max_length=2000)
    # Base64 de PNG/JPEG; string vazia remove o logo.
    timbrado_logo: str | None = None
```

- [ ] **Step 4: Estender o handler do PATCH**

Em `backend/app/api/main.py`: adicionar aos imports do topo `import base64` e `import binascii` (stdlib) e `from app.filing.timbrado import LogoInvalidoError, normalize_logo`. No handler `atualizar_perfil_operacional`, após o bloco do `oab_uf` (linha ~427) e antes do `if changes:`, inserir:

```python
        if payload.timbrado_cabecalho is not None:
            escritorio.timbrado_cabecalho = payload.timbrado_cabecalho.strip() or None
            changes["timbrado_cabecalho"] = escritorio.timbrado_cabecalho
        if payload.timbrado_rodape is not None:
            escritorio.timbrado_rodape = payload.timbrado_rodape.strip() or None
            changes["timbrado_rodape"] = escritorio.timbrado_rodape
        if payload.timbrado_logo is not None:
            if payload.timbrado_logo == "":
                escritorio.timbrado_logo = None
                escritorio.timbrado_logo_mime = None
                changes["timbrado_logo"] = "removido"
            else:
                try:
                    bruto = base64.b64decode(payload.timbrado_logo, validate=True)
                except binascii.Error:
                    raise HTTPException(status_code=422, detail="logo deve ser base64 válido")
                try:
                    escritorio.timbrado_logo = normalize_logo(bruto)
                except LogoInvalidoError as exc:
                    raise HTTPException(status_code=422, detail=str(exc))
                escritorio.timbrado_logo_mime = "image/png"
                # Bytes ficam fora do audit log; registra só a ação.
                changes["timbrado_logo"] = "atualizado"
```

- [ ] **Step 5: Rodar e ver passar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v`
Expected: PASS — novos e antigos (os testes existentes de perfil não enviam campos de timbrado e não são afetados).

- [ ] **Step 6: Lint e commit**

Run (em `backend/`): `./.venv/Scripts/python.exe -m ruff check app/api/ tests/test_api.py`
Expected: sem findings.

```bash
git add backend/app/api/schemas.py backend/app/api/main.py backend/tests/test_api.py
git commit -m "feat(api): timbrado do escritorio no perfil operacional"
```

---

### Task 6: Endpoint `GET /peticoes/{peticao_id}/pdf`

**Files:**
- Modify: `backend/app/api/main.py` (novo endpoint junto aos demais de petições) + imports
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `render_minuta_pdf(texto, *, meta, timbrado)` (Task 4), `load_timbrado(session, escritorio_id)` (Task 3), `get_owned_or_404` (já existe em `app/auth/tenant.py` e já é usado em `main.py`).
- Produces: `GET /peticoes/{peticao_id}/pdf` → `200 application/pdf` com `Content-Disposition: attachment; filename="minuta-<numero>.pdf"`; `404` para petição de outro tenant. Usado pela Task 8.

- [ ] **Step 1: Escrever os testes que falham**

Ao final de `backend/tests/test_api.py`, adicionar (garanta no topo os imports `import io` e `from pypdf import PdfReader` — o `io` pode já existir vindo da Task 5; `models` já é importado pelo arquivo — confirme e mantenha):

```python
def _cria_peticao(db_session, seeded, escritorio_id=None, processo_id=None):
    pet = models.Peticao(
        escritorio_id=escritorio_id if escritorio_id is not None else seeded.escritorio_id,
        processo_id=processo_id if processo_id is not None else seeded.id,
        tipo="Manifestacao",
        conteudo="Excelentíssimo Juízo, requer a juntada.",
        status="rascunho",
    )
    db_session.add(pet)
    db_session.flush()
    return pet


def test_peticao_pdf_download(client, db_session, seeded):
    pet = _cria_peticao(db_session, seeded)

    resp = client.get(f"/peticoes/{pet.id}/pdf")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")
    assert "minuta-" in resp.headers["content-disposition"]


def test_peticao_pdf_usa_timbrado_do_escritorio(client, db_session, seeded):
    esc = db_session.get(models.Escritorio, seeded.escritorio_id)
    esc.timbrado_rodape = "OAB/SP 123.456"
    db_session.flush()
    pet = _cria_peticao(db_session, seeded)

    resp = client.get(f"/peticoes/{pet.id}/pdf")

    paginas = PdfReader(io.BytesIO(resp.content)).pages
    texto = "\n".join(p.extract_text() or "" for p in paginas)
    assert "Escritório Teste" in texto
    assert "OAB/SP 123.456" in texto


def test_peticao_pdf_de_outro_tenant_retorna_404(client, db_session, seeded):
    outro = models.Escritorio(nome="Outro Escritório")
    db_session.add(outro)
    db_session.flush()
    proc2 = models.Processo(
        escritorio_id=outro.id, numero="0000002-00.2024.8.26.0100", tribunal="TJSP"
    )
    db_session.add(proc2)
    db_session.flush()
    pet2 = _cria_peticao(db_session, seeded, escritorio_id=outro.id, processo_id=proc2.id)

    resp = client.get(f"/peticoes/{pet2.id}/pdf")

    assert resp.status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k peticao_pdf -v`
Expected: FAIL com 404/405 (rota não existe).

- [ ] **Step 3: Implementar o endpoint**

Em `backend/app/api/main.py`: garantir nos imports `from fastapi import Response` (acrescente `Response` ao import existente do fastapi), `from app.filing.render import render_minuta_pdf` e `from app.filing.timbrado import load_timbrado` (o import de `load_timbrado` pode compartilhar linha com o da Task 5: `from app.filing.timbrado import LogoInvalidoError, load_timbrado, normalize_logo`). Junto aos demais endpoints de petições, adicionar:

```python
    @app.get("/peticoes/{peticao_id}/pdf")
    def baixar_peticao_pdf(
        peticao_id: int,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> Response:
        """Preview da peça final: o mesmo PDF (timbrado incluso) que o job de
        protocolo anexa, renderizado sob demanda para o gate humano."""
        peticao = get_owned_or_404(session, models.Peticao, peticao_id, current)
        processo = session.get(models.Processo, peticao.processo_id)
        pdf = render_minuta_pdf(
            peticao.conteudo or "",
            meta={
                "processo": processo.numero if processo else None,
                "tipo": peticao.tipo,
                "tribunal": processo.tribunal if processo else None,
            },
            timbrado=load_timbrado(session, current.escritorio_id),
        )
        nome_arquivo = f"minuta-{processo.numero if processo else peticao.id}.pdf"
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
        )
```

- [ ] **Step 4: Rodar e ver passar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 5: Lint e commit**

Run (em `backend/`): `./.venv/Scripts/python.exe -m ruff check app/api/ tests/test_api.py`
Expected: sem findings.

```bash
git add backend/app/api/main.py backend/tests/test_api.py
git commit -m "feat(api): download do PDF timbrado da peticao para o gate humano"
```

---

### Task 7: Job de protocolo anexa o PDF timbrado

**Files:**
- Modify: `backend/app/queue/jobs.py:488-501` (chamada do `render_minuta_pdf`) + import
- Test: `backend/tests/test_protocolo_roteado.py`

**Interfaces:**
- Consumes: `load_timbrado` (Task 3); `render_minuta_pdf(..., timbrado=)` (Task 4); `Peticao.escritorio_id` (existente).
- Produces: o pacote de protocolo (`package.pdf_bytes`) idêntico ao preview do endpoint da Task 6.

- [ ] **Step 1: Escrever o teste que falha**

Ao final de `backend/tests/test_protocolo_roteado.py`, adicionar:

```python
def test_protocolo_renderiza_pdf_com_timbrado_do_escritorio(db_session, monkeypatch):
    u, pet = _seed(db_session, tribunal="TJSP", sistema="e-SAJ")
    esc = db_session.get(models.Escritorio, pet.escritorio_id)
    esc.timbrado_rodape = "OAB/SP 123.456"
    db_session.flush()
    store_court_session(
        db_session, usuario_id=u.id, sistema="e-SAJ", tribunal="TJSP", grau="1",
        url_base="https://esaj-treino.tjsp.jus.br",
        storage_state={"cookies": [{"name": "x", "value": "secret-cookie"}]},
    )

    import app.queue.jobs as jobs_mod

    original = jobs_mod.render_minuta_pdf
    capturado = {}

    def espiao(texto, *, meta=None, timbrado=None):
        capturado["timbrado"] = timbrado
        return original(texto, meta=meta, timbrado=timbrado)

    monkeypatch.setattr(jobs_mod, "render_minuta_pdf", espiao)

    job = run_pje_protocol_job(
        db_session, pet.id, usuario_id=u.id, submit=True, filing_mode="sandbox"
    )

    assert job.status == "completed"
    assert capturado["timbrado"] is not None
    assert capturado["timbrado"].rodape == "OAB/SP 123.456"
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_protocolo_roteado.py -v`
Expected: FAIL — `capturado["timbrado"] is None` (o job ainda não passa o timbrado).

- [ ] **Step 3: Passar o timbrado no job**

Em `backend/app/queue/jobs.py`: adicionar aos imports do topo `from app.filing.timbrado import load_timbrado` (junto do import existente de `app.filing.render`). Na chamada de `render_minuta_pdf` (linha ~491), acrescentar o argumento:

```python
            pdf_bytes=render_minuta_pdf(
                package.conteudo or "",
                meta={
                    "processo": package.numero_processo,
                    "tipo": package.tipo_peticao,
                    "tribunal": package.tribunal,
                },
                timbrado=load_timbrado(session, peticao.escritorio_id),
            ),
```

- [ ] **Step 4: Rodar e ver passar**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest tests/test_protocolo_roteado.py tests/test_protocolar_async_multisistema.py -v`
Expected: PASS (novo teste e os existentes do fluxo de protocolo).

- [ ] **Step 5: Suíte completa, lint e commit**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest -q` e `./.venv/Scripts/python.exe -m ruff check .`
Expected: tudo verde, sem findings.

```bash
git add backend/app/queue/jobs.py backend/tests/test_protocolo_roteado.py
git commit -m "feat(queue): protocolo anexa PDF com timbrado do escritorio"
```

---

### Task 8: Frontend — tipos e `baixarPeticaoPdf` em `lib/api.ts`

**Files:**
- Modify: `frontend/lib/api.ts:202-219` (tipos `Escritorio`/`OperationalProfilePatch`) e nova função junto de `carregarPerfilOperacional` (~linha 468)
- Test: `frontend/lib/api.test.ts`

**Interfaces:**
- Consumes: contrato da API das Tasks 5–6.
- Produces (usados nas Tasks 9–10):
  - `Escritorio` com `timbrado_cabecalho: string | null`, `timbrado_rodape: string | null`, `timbrado_logo: string | null`.
  - `OperationalProfilePatch` aceitando `timbrado_cabecalho: string`, `timbrado_rodape: string`, `timbrado_logo: string` (`""` remove o logo).
  - `baixarPeticaoPdf(peticaoId: number): Promise<Blob>`.

- [ ] **Step 1: Escrever o teste que falha**

Em `frontend/lib/api.test.ts`, dentro do `describe` existente, adicionar:

```typescript
  it("baixa o PDF da petição com o bearer token", async () => {
    const blob = new Blob(["%PDF-1.4"], { type: "application/pdf" });
    const fetchMock = vi.fn(
      async () =>
        ({
          ok: true,
          status: 200,
          blob: async () => blob
        }) as unknown as Response
    );
    vi.stubGlobal("fetch", fetchMock);
    const { baixarPeticaoPdf } = await import("./api");

    const result = await baixarPeticaoPdf(11);

    expect(result).toBe(blob);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/peticoes/11/pdf");
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `frontend/`): `pnpm test`
Expected: FAIL — `baixarPeticaoPdf` não é exportado.

- [ ] **Step 3: Implementar tipos e função**

Em `frontend/lib/api.ts`, substituir o tipo `Escritorio` e estender `OperationalProfilePatch`:

```typescript
export type Escritorio = {
  id: number;
  nome: string;
  cnpj: string | null;
  timbrado_cabecalho: string | null;
  timbrado_rodape: string | null;
  /** PNG em base64, já normalizado pelo backend. */
  timbrado_logo: string | null;
};

export type OperationalProfilePatch = Partial<{
  nome_usuario: string;
  nome_escritorio: string;
  cnpj: string | null;
  oab: string | null;
  oab_uf: string | null;
  timbrado_cabecalho: string;
  timbrado_rodape: string;
  /** Base64 de PNG/JPEG; string vazia remove o logo. */
  timbrado_logo: string;
}>;
```

Após `atualizarPerfilOperacional`, adicionar (o `request()` genérico só trata JSON, por isso o fetch direto):

```typescript
export async function baixarPeticaoPdf(peticaoId: number): Promise<Blob> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const response = await fetch(`${API_BASE}/peticoes/${peticaoId}/pdf`, {
    headers: withAuthHeaders({}, token),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Falha ao baixar PDF: ${response.status}`);
  }
  return response.blob();
}
```

- [ ] **Step 4: Rodar e ver passar**

Run (em `frontend/`): `pnpm test`
Expected: PASS (novo teste e os existentes).

- [ ] **Step 5: Typecheck, lint e commit**

Run (em `frontend/`): `pnpm typecheck` e `pnpm lint`
Expected: sem erros/warnings.

```bash
git add frontend/lib/api.ts frontend/lib/api.test.ts
git commit -m "feat(frontend): tipos de timbrado e download do PDF da peticao"
```

---

### Task 9: SettingsModal — seção "Papel timbrado"

**Files:**
- Modify: `frontend/app/SettingsModal.tsx` (estado do formulário, `loadProfile`, `saveProfile` e JSX da seção "Perfil do software")
- Modify: `docs/superpowers/specs/2026-07-09-timbrado-escritorio-design.md` (correção ProfileModal → SettingsModal)

**Interfaces:**
- Consumes: `Escritorio` e `OperationalProfilePatch` com campos de timbrado (Task 8); PATCH da Task 5.
- Produces: UI de configuração do timbrado salva pelo botão "Salvar perfil" existente.

- [ ] **Step 1: Adicionar estado do timbrado**

Em `frontend/app/SettingsModal.tsx`, após o `useState` de `profileForm` (linha ~48), adicionar:

```tsx
  const [timbrado, setTimbrado] = useState({
    cabecalho: "",
    rodape: "",
    logo: "", // base64 enviado no PATCH ("" remove)
    logoPreview: "", // data URL para o <img>
    logoChanged: false
  });
```

- [ ] **Step 2: Popular no `loadProfile` e após salvar**

Em `loadProfile`, junto do `setProfileForm({...})`, adicionar:

```tsx
      setTimbrado({
        cabecalho: nextProfile.escritorio.timbrado_cabecalho ?? "",
        rodape: nextProfile.escritorio.timbrado_rodape ?? "",
        logo: nextProfile.escritorio.timbrado_logo ?? "",
        logoPreview: nextProfile.escritorio.timbrado_logo
          ? `data:image/png;base64,${nextProfile.escritorio.timbrado_logo}`
          : "",
        logoChanged: false
      });
```

Em `saveProfile`, estender o patch enviado a `atualizarPerfilOperacional` e o reset pós-sucesso:

```tsx
      const updated = await atualizarPerfilOperacional({
        nome_usuario: profileForm.nomeUsuario.trim(),
        nome_escritorio: profileForm.nomeEscritorio.trim(),
        cnpj: profileForm.cnpj.trim() || null,
        oab: profileForm.oab.trim() || null,
        oab_uf: profileForm.oabUf.trim().toUpperCase() || null,
        timbrado_cabecalho: timbrado.cabecalho.trim(),
        timbrado_rodape: timbrado.rodape.trim(),
        ...(timbrado.logoChanged ? { timbrado_logo: timbrado.logo } : {})
      });
```

e, junto do `setProfileForm({...})` pós-sucesso:

```tsx
      setTimbrado({
        cabecalho: updated.escritorio.timbrado_cabecalho ?? "",
        rodape: updated.escritorio.timbrado_rodape ?? "",
        logo: updated.escritorio.timbrado_logo ?? "",
        logoPreview: updated.escritorio.timbrado_logo
          ? `data:image/png;base64,${updated.escritorio.timbrado_logo}`
          : "",
        logoChanged: false
      });
```

- [ ] **Step 3: Handler de upload com validação client-side**

Após `saveProfile`, adicionar:

```tsx
  function onLogoSelected(file: File | null) {
    if (!file) return;
    if (!["image/png", "image/jpeg"].includes(file.type)) {
      setProfileError("Logo deve ser PNG ou JPEG");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setProfileError("Logo deve ter no máximo 2MB");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result);
      const base64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
      setTimbrado((t) => ({ ...t, logo: base64, logoPreview: dataUrl, logoChanged: true }));
      setProfileError(null);
    };
    reader.readAsDataURL(file);
  }
```

- [ ] **Step 4: JSX da seção**

Dentro do bloco `<>...</>` do perfil (após o `</div>` da `settingsRow ufRow`, antes do `{profile ? (...)}` com "Conta conectada"), inserir:

```tsx
              <span className="settingsLabel">Papel timbrado</span>
              <div className="settingsRow single">
                <label>
                  Logo (PNG/JPEG até 2MB)
                  <input
                    type="file"
                    accept="image/png,image/jpeg"
                    disabled={offline}
                    onChange={(e) => onLogoSelected(e.target.files?.[0] ?? null)}
                  />
                </label>
              </div>
              {timbrado.logoPreview ? (
                <div className="settingsRow single">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={timbrado.logoPreview}
                    alt="Logo do escritório"
                    style={{ maxHeight: 48, maxWidth: 180, objectFit: "contain" }}
                  />
                  <button
                    type="button"
                    className="toolbarButton compact"
                    disabled={offline}
                    onClick={() =>
                      setTimbrado((t) => ({ ...t, logo: "", logoPreview: "", logoChanged: true }))
                    }
                  >
                    Remover logo
                  </button>
                </div>
              ) : null}
              <div className="settingsRow single">
                <label>
                  Cabeçalho do timbrado (endereço, contato — uma linha por linha do papel)
                  <textarea
                    rows={3}
                    value={timbrado.cabecalho}
                    disabled={offline}
                    onChange={(e) => setTimbrado((t) => ({ ...t, cabecalho: e.target.value }))}
                  />
                </label>
              </div>
              <div className="settingsRow single">
                <label>
                  Rodapé do timbrado (OABs, site)
                  <textarea
                    rows={2}
                    value={timbrado.rodape}
                    disabled={offline}
                    onChange={(e) => setTimbrado((t) => ({ ...t, rodape: e.target.value }))}
                  />
                </label>
              </div>
```

- [ ] **Step 5: Corrigir o spec (ProfileModal → SettingsModal)**

Em `docs/superpowers/specs/2026-07-09-timbrado-escritorio-design.md`: (a) trocar as duas menções a "ProfileModal" por "SettingsModal (seção Perfil do software)" — na decisão 1 e na seção Frontend; (b) na seção "Riscos e observações", substituir a frase sobre fixar metadados por: "Determinismo: os testes validam por texto extraído (pypdf), não por bytes; a data de criação real do fpdf2 é mantida como evidência de protocolo."

- [ ] **Step 6: Verificar**

Run (em `frontend/`): `pnpm check`
Expected: lint + typecheck + testes verdes.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/SettingsModal.tsx docs/superpowers/specs/2026-07-09-timbrado-escritorio-design.md
git commit -m "feat(frontend): configuracao do papel timbrado nas configuracoes"
```

---

### Task 10: MinutaEditor — botão "Baixar PDF"

**Files:**
- Modify: `frontend/app/MinutaEditor.tsx`

**Interfaces:**
- Consumes: `baixarPeticaoPdf` (Task 8).
- Produces: botão de download no rodapé do editor de minuta.

- [ ] **Step 1: Implementar estado, handler e botão**

Em `frontend/app/MinutaEditor.tsx`:

1. Trocar a linha de imports do lucide por:

```tsx
import { Check, Copy, Download, Loader2, RotateCcw, Save, X } from "lucide-react";
```

2. Adicionar o import da API junto ao existente:

```tsx
import { baixarPeticaoPdf, type Peticao, type Prazo, type Processo } from "@/lib/api";
```

(e remover o `import type { Peticao, Prazo, Processo } from "@/lib/api";` antigo.)

3. Após `const [copied, setCopied] = useState(false);`:

```tsx
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function baixarPdf() {
    setDownloading(true);
    try {
      const blob = await baixarPeticaoPdf(peticao.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `minuta-${processo?.numero ?? peticao.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setDownloadError(null);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "Falha ao baixar PDF");
    } finally {
      setDownloading(false);
    }
  }
```

4. No `editorFooterLeft`, após o botão "Copiar":

```tsx
              <button
                className="toolbarButton compact"
                disabled={downloading || dirty}
                title={dirty ? "Salve a minuta antes de baixar o PDF" : undefined}
                onClick={() => void baixarPdf()}
              >
                {downloading ? <Loader2 className="spin" size={14} /> : <Download size={14} />}
                Baixar PDF
              </button>
```

5. Após o `</div>` que fecha `editorFooter`, exibir erro quando houver:

```tsx
          {downloadError ? (
            <small className="settingsHint vaultError" role="alert">
              {downloadError}
            </small>
          ) : null}
```

- [ ] **Step 2: Verificar**

Run (em `frontend/`): `pnpm check`
Expected: lint + typecheck + testes verdes.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/MinutaEditor.tsx
git commit -m "feat(frontend): baixar PDF timbrado no editor de minuta"
```

---

### Task 11: Verificação de ponta a ponta e documentação de estado

**Files:**
- Modify: `docs/estado.md` (registrar a capacidade nova na seção de estado atual)

**Interfaces:**
- Consumes: tudo acima.
- Produces: suíte completa verde nos dois lados + estado documentado.

- [ ] **Step 1: Suíte completa do backend**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest -q` e `./.venv/Scripts/python.exe -m ruff check .`
Expected: tudo verde, sem findings.

- [ ] **Step 2: Verificação completa do frontend**

Run (em `frontend/`): `pnpm check` e `pnpm build`
Expected: lint, typecheck, testes e build verdes.

- [ ] **Step 3: Verificação manual do fluxo (se backend local disponível)**

Subir backend + frontend locais, abrir Configurações → preencher cabeçalho/rodapé + logo → Salvar perfil → abrir uma minuta → "Baixar PDF" → conferir visualmente: logo/nome/cabeçalho no topo, rodapé + paginação embaixo, acentos corretos. Registrar o resultado (ou a impossibilidade de rodar) no resumo final.

- [ ] **Step 4: Atualizar `docs/estado.md`**

Adicionar, na seção de capacidades/estado atual do documento (seguindo o formato existente do arquivo), uma linha registrando: PDF de protocolo com papel timbrado por escritório (logo + cabeçalho + rodapé configuráveis nas Configurações; preview via "Baixar PDF" na minuta; mesmo PDF anexado pelo job de protocolo).

- [ ] **Step 5: Commit final**

```bash
git add docs/estado.md
git commit -m "docs(estado): registra papel timbrado por escritorio no PDF de protocolo"
```
