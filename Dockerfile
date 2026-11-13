# Immagine completa per la demo: frontend React compilato + API FastAPI in un solo servizio.
#   docker build -t assistente-ncc-rag .
#   docker run -p 8000:8000 -e SECRET_KEY=... -e CONTACT_HASH_KEY=... assistente-ncc-rag
# Per lo sviluppo con PostgreSQL e RabbitMQ usa docker-compose.yml (backend/Dockerfile).

# --- 1. build del frontend --------------------------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. backend + file statici ----------------------------------------------------------------
FROM python:3.12-slim

# commit della build, mostrato da /api/v1/health (su Render vale anche RENDER_GIT_COMMIT)
ARG GIT_COMMIT=""
ENV GIT_COMMIT=${GIT_COMMIT}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/backend
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install "." && apt-get purge -y git && apt-get autoremove -y
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY examples /srv/examples
COPY --from=frontend /build/dist /srv/frontend

RUN useradd --create-home --uid 10001 appuser && mkdir -p /srv/backend/data && chown -R appuser /srv/backend/data
USER appuser

# Valori della demo: SQLite, coda in memoria, risposte estrattive (nessun LLM a pagamento).
# SECRET_KEY e CONTACT_HASH_KEY vanno passati all'avvio: con APP_ENV=demo l'avvio fallisce senza.
ENV APP_ENV=demo \
    STATIC_DIR=/srv/frontend \
    SEED_DOCS_DIR=/srv/examples/ncc-docs \
    DATABASE_URL=sqlite:///./data/app.db \
    QUEUE_BACKEND=memory \
    ANSWER_GENERATOR=extractive \
    PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/api/v1/health').status==200 else 1)"
# FORWARDED_ALLOW_IPS: indirizzi dei proxy fidati (su Render "*") per leggere il vero IP del client
# (virgolette obbligatorie: senza, la shell espanderebbe "*" nell'elenco dei file)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT}\" --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\""]
