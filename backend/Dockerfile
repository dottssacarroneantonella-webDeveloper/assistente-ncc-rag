# Immagine del backend (API + worker). Build dalla radice del progetto:
#   docker build -f backend/Dockerfile -t assistente-ncc-rag .
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/backend
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install ".[postgres]"
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY examples /srv/examples

RUN useradd --create-home --uid 10001 appuser && mkdir -p /srv/backend/data && chown -R appuser /srv/backend/data
USER appuser

ENV SEED_DOCS_DIR=/srv/examples/ncc-docs
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health').status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
