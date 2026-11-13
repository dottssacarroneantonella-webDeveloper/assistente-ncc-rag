# Assistente NCC con RAG

[![CI](https://github.com/dottssacarroneantonella-webDeveloper/assistente-ncc-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/dottssacarroneantonella-webDeveloper/assistente-ncc-rag/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React_19-TypeScript-61DAFB?logo=react&logoColor=black)
![License](https://img.shields.io/badge/license-MIT-green)

Assistente virtuale per un servizio **NCC / transfer** che risponde alle domande dei clienti
(tariffe, condizioni, disdette, bagagli, animali…) **usando solo i documenti dell'attività** e
citando le fonti. Il canale finale è **WhatsApp** (Meta Cloud API); per provarlo senza account
Meta c'è una **chat web in stile WhatsApp** che usa esattamente la stessa pipeline.

Il motore di ricerca sui documenti è la mia libreria
[rag-pdf-qa](https://github.com/dottssacarroneantonella-webDeveloper/rag-pdf-qa), usata qui come
dipendenza.

> L'attività "NCC Levante Transfer" e i suoi documenti sono **fittizi**: servono solo per la demo.

## Cosa fa

| Funzione | Stato |
|---|---|
| Chat web con risposte basate sui PDF e fonti citate (file e pagina) | ✅ F1 |
| Benvenuto con domande di esempio, saluti riconosciuti senza RAG | ✅ F1 |
| "Non lo so" onesto + domanda registrata per il titolare | ✅ F1 |
| Ritentativi automatici (3 tentativi, attesa 2/4/8 s) e messaggio di scuse | ✅ F1 |
| Comando `CANCELLA DATI` per eliminare la conversazione | ✅ F1 |
| Endpoint `/health` (database, coda, indice) | ✅ F1 |
| Webhook WhatsApp con verifica della firma `X-Hub-Signature-256` e handshake Meta | ✅ F2 |
| Deduplica dei messaggi (stesso `wamid` → una sola risposta) | ✅ F2 |
| RabbitMQ: coda durevole, ack manuale, code di ritardo e coda di errore (DLQ) | ✅ F2 |
| Worker separato (`python -m app.worker`) e invio delle risposte con la Graph API | ✅ F2 |
| Audio, immagini e posizioni: risposta che invita a scrivere la domanda | ✅ F2 |
| Numeri di telefono mai salvati: solo HMAC-SHA256 + ultime 4 cifre | ✅ F2 |
| Area admin: login sicuro (Argon2id, JWT in cookie HttpOnly, CSRF, limite di tentativi) | ✅ F3 |
| Caricamento ed eliminazione dei PDF (controllo del formato, 10 MB, duplicati) | ✅ F3 |
| Reindicizzazione come job in background con stato visibile | ✅ F3 |
| Conversazioni con risposte, fonti, punteggi e tempi di elaborazione | ✅ F3 |
| Domande senza risposta da gestire con una nota | ✅ F3 |
| Conservazione dei dati: conversazioni eliminate dopo 30 giorni | ✅ F4 |
| Informativa privacy, conversazione ripresa dopo il ricaricamento della pagina | ✅ F4 |
| Limiti della chat per IP (10 messaggi al minuto, 100 al giorno) | ✅ F4 |
| Header di sicurezza (CSP, HSTS, Permissions-Policy) e controlli di accessibilità con axe-core | ✅ F4 |
| pip-audit, npm audit e Dependabot | ✅ F4 |
| Immagine unica (frontend + API) pubblicata su GitHub Container Registry | ✅ F5 |
| Deploy automatico della demo su Render dopo la CI verde, con verifica di `/health` | ✅ F5 |

## Architettura

```mermaid
flowchart LR
    U[Cliente] -->|WhatsApp| W[Webhook /whatsapp]
    U -->|Browser| C[Chat web React]
    C -->|POST 202 + polling| API[FastAPI]
    W --> API
    API -->|salva messaggio| DB[(PostgreSQL / SQLite)]
    API -->|evento message.received| Q{{Coda<br/>RabbitMQ / in memoria}}
    Q --> WK[Worker]
    WK -->|domanda| RAG[rag-pdf-qa<br/>embedding + ricerca]
    RAG --> LLM[Generatore<br/>estrattivo / Ollama / OpenAI]
    WK -->|risposta + fonti| DB
    WK -->|Graph API| U
```

**Perché la coda?** Il webhook di WhatsApp deve rispondere in pochi secondi, mentre un LLM può
impiegarne di più. L'API salva il messaggio e risponde subito (`200` a Meta, `202` alla chat web);
il worker elabora con calma, ritenta se l'LLM non risponde e non perde messaggi.

**Affidabilità con RabbitMQ**

```
ncc.events ──► worker ──ok──► ack
    ▲            │
    │            └─errore temporaneo─► ncc.events.retry.2000 ─(TTL)─┐
    │                                  ncc.events.retry.4000 ─(TTL)─┤
    └───────────────────────────────────────────────────────────────┘
                 └─dopo l'ultimo tentativo─► ncc.events.dlq + messaggio di scuse
```

Il messaggio viene confermato (ack) solo dopo aver salvato la risposta: se il worker si ferma
a metà, RabbitMQ lo riconsegna. Il worker è idempotente, quindi una riconsegna non produce
risposte doppie.

**Scelte principali**

- **Coda astratta** (`MessageQueue`): RabbitMQ in produzione, coda in memoria per demo e test.
- **Generatore configurabile**: `extractive` (gratis, nessun LLM: restituisce le frasi più
  pertinenti dei documenti), `ollama` (LLM locale) oppure `openai`.
- **Reindicizzazione atomica**: il nuovo indice si costruisce in una cartella temporanea e
  sostituisce il vecchio con un rename, così nessuna domanda vede un indice a metà.
- **Database in 3NF** (7 tabelle) con migrazioni Alembic; SQLite per demo e test, PostgreSQL con Docker.
- **Errori in formato unico**: `{"error": {"code", "message", "details"}}`.

La specifica completa (requisiti, schema ER, API, sicurezza, piano di rilascio) è in
[`docs/spec`](docs/spec/2026-11-13-assistente-ncc-rag-spec.md).

## Avvio rapido

Requisiti: Python 3.11+ e Node.js 20+.

```bash
git clone https://github.com/dottssacarroneantonella-webDeveloper/assistente-ncc-rag.git
cd assistente-ncc-rag

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload      # http://localhost:8000/api/v1/docs

# Frontend (in un secondo terminale)
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

Al primo avvio il backend carica i tre PDF di esempio da `examples/ncc-docs/` e costruisce l'indice.
Prova a chiedere: *"Quanto costa il transfer dall'aeroporto di Bari a Monopoli?"*

Per l'area admin (`http://localhost:5173/admin`) imposta prima nel file `backend/.env`
`ADMIN_EMAIL`, `ADMIN_PASSWORD` (almeno 12 caratteri) e `SECRET_KEY`: l'admin viene creato al
primo avvio. Per cambiare la password: `python -m app.cli reset-admin-password <email>`.

### Con un LLM locale (Ollama)

```bash
ollama pull llama3.2
# nel file backend/.env
ANSWER_GENERATOR=ollama
```

### Con Docker (PostgreSQL + RabbitMQ + worker)

```bash
cp .env.example .env
docker compose up --build          # API su http://localhost:8000
                                   # pannello RabbitMQ su http://localhost:15672
```

### Collegare WhatsApp (Meta Cloud API)

1. Su [Meta for Developers](https://developers.facebook.com/) crea un'app di tipo *Business* e
   aggiungi il prodotto **WhatsApp**: ottieni un numero di test, il *Phone number ID* e un token.
2. Compila nel file `.env` (mai su GitHub): `WHATSAPP_ENABLED=true`, `META_ACCESS_TOKEN`,
   `META_PHONE_NUMBER_ID`, `META_APP_SECRET`, `META_VERIFY_TOKEN` e `CONTACT_HASH_KEY`.
3. Esponi l'API in HTTPS (in locale con un tunnel, es. `cloudflared tunnel --url http://localhost:8000`).
4. In *WhatsApp → Configurazione* inserisci come URL di callback
   `https://<tuo-dominio>/api/v1/whatsapp/webhook`, lo stesso `META_VERIFY_TOKEN` e
   iscriviti al campo **messages**.

Senza account Meta si può simulare un messaggio firmato:

```bash
META_APP_SECRET=<valore del .env> python scripts/send_test_webhook.py "Accettate animali a bordo?"
```

## Deploy

```
push su main ──► CI (lint, test, audit, build) ──verde──► Deploy
                                                          ├─ immagine su ghcr.io (latest + sha)
                                                          ├─ prova dell'immagine: /health, chat, admin
                                                          └─ deploy hook Render ──► verifica della demo
```

L'immagine della radice (`Dockerfile`) contiene il frontend compilato e l'API: un solo servizio,
SQLite, coda in memoria e risposte estrattive, quindi gira anche su un piano gratuito.

```bash
docker run -p 8000:8000 \
  -e SECRET_KEY="$(openssl rand -hex 32)" -e CONTACT_HASH_KEY="$(openssl rand -hex 32)" \
  ghcr.io/dottssacarroneantonella-webdeveloper/assistente-ncc-rag:latest
# http://localhost:8000
```

**Demo su Render** (configurazione in `render.yaml`):

1. Render → *New* → *Blueprint* → collega questa repository: `SECRET_KEY` e `CONTACT_HASH_KEY`
   vengono generati da Render; inserisci `ADMIN_EMAIL` e `ADMIN_PASSWORD` nella dashboard.
2. Nelle impostazioni del servizio copia il *Deploy Hook* e salvalo su GitHub come secret
   `RENDER_DEPLOY_HOOK_URL` (*Settings → Secrets and variables → Actions*).
3. Aggiungi la variabile `DEMO_URL` (es. `https://assistente-ncc-rag.onrender.com`): il workflow
   verifica che la demo risponda dopo ogni deploy.

Sul piano gratuito il servizio va in pausa dopo 15 minuti senza visite: la prima richiesta può
richiedere fino a un minuto, e i dati della demo si azzerano a ogni riavvio (i documenti di
esempio vengono ricaricati automaticamente).

## API

| Metodo | Percorso | Descrizione |
|---|---|---|
| GET | `/api/v1/health` | Stato di database, coda e indice |
| POST | `/api/v1/chat/conversations` | Nuova conversazione (201) con messaggio di benvenuto |
| POST | `/api/v1/chat/conversations/{id}/messages` | Invia una domanda (202 + `message_id`) |
| GET | `/api/v1/chat/conversations/{id}/messages?after=` | Messaggi e risposte con fonti |
| GET | `/api/v1/whatsapp/webhook` | Handshake di verifica di Meta (`hub.challenge`) |
| POST | `/api/v1/whatsapp/webhook` | Messaggi WhatsApp in arrivo (firma obbligatoria) |
| POST | `/api/v1/auth/login` · `logout` · GET `me` | Sessione admin (cookie HttpOnly + CSRF) |
| GET/POST | `/api/v1/admin/documents` · DELETE `/{id}` | Elenco, caricamento ed eliminazione dei PDF |
| POST/GET | `/api/v1/admin/index-jobs` · GET `/{id}` | Avvio e stato della reindicizzazione |
| GET | `/api/v1/admin/conversations` · `/{id}` | Conversazioni paginate e dettaglio con fonti |
| GET/PATCH | `/api/v1/admin/unanswered` · `/{id}` | Domande senza risposta, aperte o gestite |

Documentazione interattiva: `http://localhost:8000/api/v1/docs`.

## Test

```bash
cd backend && pytest --cov=app        # API, webhook, worker, coda, intenti, migrazioni
RABBITMQ_TEST_URL=amqp://guest:guest@localhost:5672/ pytest tests/test_rabbitmq.py
cd frontend && npm test               # componenti React e accessibilità (Vitest + axe-core)
```

La CI su GitHub Actions esegue lint (ruff), test con copertura minima dell'80% (con un RabbitMQ
reale come container di servizio), controllo dei tipi TypeScript, build del frontend e build
dell'immagine Docker a ogni push.

## Struttura

```
backend/
  app/
    api/        endpoint FastAPI, schemi, gestione errori
    channels/   consegna delle risposte (web, WhatsApp) e lettura dei payload Meta
    core/       configurazione e log strutturati
    db/         modelli SQLAlchemy e sessioni
    queue/      interfaccia coda: RabbitMQ (aio-pika) e in memoria
    rag/        adattatore verso rag-pdf-qa
    services/   conversazioni, documenti, indicizzazione
    worker/     intenti, elaborazione dei messaggi, worker separato
  alembic/      migrazioni del database
  tests/
frontend/       React + TypeScript (Vite): chat demo e area admin (React Router)
examples/       PDF fittizi dell'attività
scripts/        PDF di esempio e simulatore di webhook firmati
docs/spec/      specifica tecnica
```

## Sicurezza e privacy

- Nessun segreto nel codice: tutto in `.env` (vedi `.env.example`), escluso da Git.
- Validazione degli input (lunghezza massima della domanda, UUID, JSON).
- Header di sicurezza (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) e CORS ristretto al frontend.
- Container eseguito con utente non root.
- Webhook Meta accettati solo con firma HMAC-SHA256 valida (confronto a tempo costante).
- Numeri di telefono mai salvati in chiaro: HMAC-SHA256 con chiave segreta + ultime 4 cifre;
  il numero viaggia solo nell'evento in coda, il tempo necessario a rispondere.
- Area admin: password con Argon2id, sessione JWT in cookie `HttpOnly` + `SameSite=Strict`
  (+ `Secure` fuori dallo sviluppo), token CSRF double-submit sulle modifiche, massimo 5 tentativi
  di accesso in 15 minuti per IP, messaggio d'errore identico per email e password sbagliate.
- Upload: solo `application/pdf` con firma `%PDF-`, massimo 10 MB, nome file ripulito, duplicati
  rifiutati con SHA-256.
- In produzione l'avvio fallisce se `SECRET_KEY` o `CONTACT_HASH_KEY` sono deboli o predefinite.
- Chat limitata per IP (10 messaggi al minuto, 100 al giorno, 30 conversazioni all'ora) con
  risposta `429` e header `Retry-After`.
- Header di sicurezza su ogni risposta: `Content-Security-Policy: default-src 'none'`,
  `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control: no-store` e, fuori
  dallo sviluppo, `Strict-Transport-Security`.
- GDPR: conversazioni eliminate automaticamente dopo `RETENTION_DAYS` giorni (anche a mano con
  `python -m app.cli purge-expired`), comando `CANCELLA DATI`, informativa nella chat, log senza
  il testo dei messaggi.
- Dipendenze controllate a ogni push con `pip-audit` e `npm audit`; Dependabot ogni settimana.

## Accessibilità

La chat e l'area admin usano etichette per tutti i campi, navigazione da tastiera con focus
visibile, annuncio delle nuove risposte agli screen reader (`aria-live`) e rispettano
`prefers-reduced-motion`. I test eseguono **axe-core** (regole WCAG 2.1 A/AA) sulla chat,
sull'informativa e sul login; il contrasto dei colori richiede un browser reale e va verificato
a parte.

## Licenza

[MIT](LICENSE)
