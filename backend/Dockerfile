FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Tesseract (OCR pt) para process-autos-due. Sem browsers do Playwright:
# o backend hospedado nunca abre navegador (ver Global Constraints).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependencias + o pacote 'app' a partir do pyproject.
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
RUN pip install .

# Diretorio de artefatos (autos) — montado como volume no Compose.
RUN mkdir -p /app/artifacts

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
