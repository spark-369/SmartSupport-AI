# SmartSupport AI — Product-Manual RAG Customer Support Platform

SmartSupport is a full-stack, self-hosted customer-support assistant built around
**Retrieval-Augmented Generation (RAG)**. Support teams upload product manuals
(PDF / DOCX / MD / TXT), documents are ingested asynchronously into a vector
index, and an AI assistant answers customer questions **strictly from those
manuals** — with numbered citations, confidence scores and follow-up questions.
Every conversation can be escalated into an **AI-triaged support ticket**
(classification, fact extraction, deterministic human-escalation decision) and
worked in a live triage queue. Admins get semantic manual search and product
insights (grounding rate, knowledge gaps, most-asked questions).

```
┌────────────────────────────┐      ┌──────────────────────────────────────────────┐
│  React 19 + Vite 8 (TS)    │      │  FastAPI (Pydantic v2)                       │
│  Tailwind 4 · shadcn/ui    │  /api│  ├─ JWT auth (access + rotating refresh)     │
│  Zustand · TanStack Query  ├─────►│  ├─ Redis sliding-window rate limiting       │
│  RHF + Zod · fetch-SSE ◄───┼─SSE──┤  ├─ SSE: status → sources → answer → done    │
└────────────────────────────┘      │  └─ LangChain RAG (3 chained stages)         │
                                    │        │ format = Schema.model_json_schema() │
      ┌─────────────────┐           │        ▼                                     │
      │ Celery worker   │──────────►│  Ollama (localhost:11434)                    │
      │ extract→chunk→  │  embed    │   · Qwen3-Embedding-0.6B (Q8_0)   1024 dim   │
      │ embed→store     │◄──────────│   · Qwen2.5-0.5B-Instruct (Q4_K_M)           │
      └────────┬────────┘           └──────────┬───────────────────────────────────┘
               │                               │ NumPy cosine similarity (float4[])
      ┌────────▼────────┐           ┌──────────▼──────────┐   ┌──────────────────┐
      │ Local filesystem│           │ PostgreSQL (JSONB + │   │ Redis 7          │
      │ data/uploads/   │           │  real[] embeddings) │   │ cache·rl·broker  │
      └─────────────────┘           └─────────────────────┘   └──────────────────┘
```

---

## Features

### Knowledge base & ingestion
- **Product catalog** with slug-based detail pages; per-product manual libraries.
- **Manual upload** (PDF, DOCX, MD, TXT; ≤ 20 MB) handled by admins; the original
  file is kept on disk and can be re-downloaded.
- **Asynchronous ingestion pipeline** (Celery): text extraction → chunking
  (1000 chars / 150 overlap) → batch embedding (1024-dim) → storage with page
  numbers and chunk metadata in JSONB. The task is **idempotent** — retries
  clear existing chunks first, so retries/backoff never duplicate data.
- Live per-document status (`pending → processing → ready / failed`) with a
  **retry** action for failed ingestions; per-product document stats are embedded
  in product payloads (no extra fetches).

### Grounded chat (RAG)
- **Three chained LLM stages**, each schema-constrained via Ollama native
  `format` (JSON-schema constrained decoding — zero manual JSON parsing):
  1. **Query rewrite** — pronouns resolved against recent history into a
     standalone search query.
  2. **Grounded answer** — answers *only* from retrieved manual excerpts, cites
     them by number (resolved server-side into full source refs), reports
     `found_in_manual` + `confidence`, and proposes follow-up questions.
  3. **Conversation title** — a 3–6 word title after the first exchange.
- **Token-level streaming** over SSE: answer prose is decoded incrementally from
  the constrained JSON stream and rendered live as markdown — no frozen composer.
- **Citations UI**: source chips with document name, quote, similarity score and
  page number; follow-up questions render as clickable chips.
- **Semantic manual search** across one or all products with highlightable
  excerpts and an "Ask in chat" deep link.

### Ticket triage & human workflow
- **One-click escalation from chat** → the latest customer message is triaged by
  AI: `category` (9 classes), `urgency` (low→critical), `sentiment`, extracted
  facts (`product`, `issue`, `requested_action`, `topics`) and a one-line summary.
- **Deterministic escalation decision** — a second grounded-answer pass over the
  manuals decides `needs_human`: if the manuals can answer the question the
  ticket stays agent-resolvable; otherwise it is escalated with a concrete
  reason. The requested action is always a **solution action** ("deliver the
  missing sugar"), never an echo of the complaint.
- **Live triage desk**: urgency-ranked queue, stat strip + tab counters
  (polled every 15 s), urgency filter, full-text search over message / summary /
  category, resolve (with resolution note) / dismiss / escalate / reopen
  workflow. The default queue shows the **active workload** (open + escalated);
  resolved and dismissed tickets live behind their own tabs.
- **RBAC**: admins see the whole desk; users only their own tickets.

### Analytics (admin)
- Totals: conversations, questions asked, **grounding rate**, average confidence
  and answer latency.
- Per-product performance, **knowledge gaps** (ungrounded questions paired with
  the exact user question that produced them) and most-asked questions.
- All aggregates computed in single grouped SQL queries.

### Platform
- **JWT auth** with 30-minute access tokens and **rotating refresh tokens** in an
  HttpOnly cookie, stored SHA-256-hashed server-side; refresh-token **family
  revocation** on reuse (theft detection).
- **Redis sliding-window rate limiting** (atomic Lua scripts) on all sensitive
  endpoints; fails **open** if Redis is unavailable.
- Structured JSON logging with request IDs; central error handler with consistent
  error payloads; OpenAPI docs at `/docs`.

---

## Tech stack

| Layer | Choice |
| --- | --- |
| Frontend | React 19 + Vite 8 + TypeScript, Tailwind CSS 4 + shadcn/ui-style components, Zustand, TanStack Query, React Hook Form + Zod, SSE via `fetch` |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, Celery + Redis, LangChain (`langchain-ollama`), NumPy |
| Data | PostgreSQL (JSONB + `real[]` float4 embeddings), Redis 7 (cache · rate limiting · Celery broker), local filesystem |
| AI | Ollama · Qwen3-Embedding-0.6B (Q8_0, 1024-dim) · Qwen2.5-0.5B-Instruct (Q4_K_M) · native structured output (`format=` JSON schema) |
| Testing | pytest (108 tests, real PostgreSQL test DB + fakeredis + fake AI), Playwright browser E2E |

---

## Repository layout

```
v1/
├── backend/
│   ├── app/
│   │   ├── core/        config · security (JWT/bcrypt) · cache · rate_limit · errors · logging
│   │   ├── db/          async engine (API) + sync engine (Celery/Alembic) · Base
│   │   ├── models/      users · refresh_tokens · products · documents · chunks ·
│   │   │                conversations · messages · tickets
│   │   ├── schemas/     Pydantic v2 API schemas + Ollama structured-output schemas (ai.py)
│   │   ├── services/    auth · products · documents · chat · embedding · retrieval ·
│   │   │                search · analytics · triage
│   │   │   └── rag/     prompts · chains (ChatOllama + format=…) · streaming · pipeline (SSE events)
│   │   ├── api/         deps (auth, RBAC, rate limits) · router · v1 endpoints
│   │   ├── workers/     celery_app · tasks (ingest_document)
│   │   ├── utils/       extraction (PDF/DOCX/TXT/MD)
│   │   └── main.py      app factory, lifespan, CORS, request-id middleware
│   ├── alembic/         5 migrations (initial schema → message follow-ups → tickets →
│   │                    ticket chat origin → drop suggested_reply)
│   ├── scripts/seed.py  admin + demo product + sample manual (ingested inline)
│   ├── tests/           108 pytest tests (PG test DB + fakeredis + fake AI)
│   └── requirements.txt
├── frontend/
│   ├── src/             pages/ components/ hooks/ stores/ lib (api, sse, validation)
│   └── scripts/         e2e-browser.mjs · e2e-stream-verify.mjs · e2e-fix-verify.mjs
├── sample_data/         aurora_coffee_maker_x100_manual.md (demo manual)
├── docker-compose.yml   optional Redis (`infra` profile) + Ollama (`ollama` profile)
├── Makefile             one-command workflows
└── README.md
```

---

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.12 | venv expected at `backend/venv` |
| Node 20+ | developed on Node 24 |
| PostgreSQL 15+ | running and reachable; needs the `smartsupport` and `smartsupport_test` databases |
| Redis 7 | on `localhost:6379` |
| Ollama | on `localhost:11434` with the two models below |

Pull the models once:

```bash
ollama pull hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0
ollama pull hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M
```

Create the databases (adjust container name to your setup):

```bash
docker exec some-postgres psql -U postgres -c "CREATE DATABASE smartsupport;"
docker exec some-postgres psql -U postgres -c "CREATE DATABASE smartsupport_test;"
```

> `docker-compose.yml` ships optional profiles — `docker compose --profile infra up`
> for a containerized Redis and `--profile ollama` for a containerized Ollama.
> PostgreSQL is intentionally external (assumed already running on port 5432).

---

## Quickstart

### One-command (Makefile)

```bash
make install    # backend venv + pip install + npm install
make migrate    # alembic upgrade head
make seed       # admin user + demo product + sample manual (ingested inline)
make api        # FastAPI dev server        → http://localhost:8000
make worker     # Celery worker (ingestion)
make frontend   # Vite dev server           → http://localhost:5173
```

### Manual (3 terminals)

```bash
# 0) one-time
cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt
cd ../frontend && npm install

# 1) schema + demo data
cd backend && venv/bin/alembic upgrade head && venv/bin/python scripts/seed.py

# 2) API
cd backend && venv/bin/uvicorn app.main:app --port 8000 --reload

# 3) Celery worker
cd backend && venv/bin/celery -A app.workers.celery_app.celery_app worker --loglevel=INFO

# 4) Frontend
cd frontend && npm run dev     # → http://localhost:5173
```

Sign in with the seeded admin: **admin@smartsupport.io / Admin12345!**
(or register a new account — the *first* account in a fresh database is
promoted to admin automatically).

Swagger UI: <http://localhost:8000/docs> · Health check:
<http://localhost:8000/api/v1/health>

---

## Configuration

All settings live in `backend/app/core/config.py` and can be overridden with
`SMARTSUPPORT_`-prefixed environment variables or a `backend/.env` file.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SMARTSUPPORT_DATABASE_URL` | `postgresql+asyncpg://…@localhost:5432/smartsupport` | async engine (API) |
| `SMARTSUPPORT_SYNC_DATABASE_URL` | `postgresql+psycopg2://…` | sync engine (Celery / Alembic) |
| `SMARTSUPPORT_REDIS_URL` | `redis://localhost:6379/0` | cache + rate limiting |
| `SMARTSUPPORT_CELERY_BROKER_URL` | falls back to `REDIS_URL` | Celery broker |
| `SMARTSUPPORT_CELERY_RESULT_BACKEND` | falls back to `REDIS_URL` | Celery results |
| `SMARTSUPPORT_JWT_SECRET` | dev default | **change in production** |
| `SMARTSUPPORT_JWT_ALGORITHM` | `HS256` | JWT signing |
| `SMARTSUPPORT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | access-token lifetime |
| `SMARTSUPPORT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | refresh-token lifetime |
| `SMARTSUPPORT_REFRESH_COOKIE_NAME` | `ss_refresh_token` | refresh cookie |
| `SMARTSUPPORT_COOKIE_SECURE` | `False` | set `True` behind HTTPS |
| `SMARTSUPPORT_CORS_ORIGINS` | localhost:5173 origins | allowed origins |
| `SMARTSUPPORT_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `SMARTSUPPORT_OLLAMA_TIMEOUT_SECONDS` | `120` | per-call timeout |
| `SMARTSUPPORT_EMBEDDING_MODEL` | `…/Qwen3-Embedding-0.6B-GGUF:Q8_0` | 1024-dim embeddings |
| `SMARTSUPPORT_LLM_MODEL` | `…/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M` | generation model |
| `SMARTSUPPORT_LLM_TEMPERATURE` | `0.2` | generation temperature |
| `SMARTSUPPORT_LLM_NUM_CTX` | `8192` | context window |
| `SMARTSUPPORT_ANSWER_MAX_TOKENS` | `1024` | answer token budget |
| `SMARTSUPPORT_RETRIEVAL_TOP_K` | `6` | excerpts per query |
| `SMARTSUPPORT_RETRIEVAL_MIN_SCORE` | `0.20` | cosine similarity floor |
| `SMARTSUPPORT_CHUNK_SIZE` / `_OVERLAP` | `1000` / `150` | chunking |
| `SMARTSUPPORT_EMBED_BATCH_SIZE` | `32` | embedding batch |
| `SMARTSUPPORT_MAX_EMBED_CHARS` | `6000` | per-embed text cap |
| `SMARTSUPPORT_RAG_HISTORY_MESSAGES` | `6` | history for the rewriter |
| `SMARTSUPPORT_UPLOAD_DIR` | `data/uploads` | manual storage |
| `SMARTSUPPORT_MAX_UPLOAD_MB` | `20` | upload cap |
| `SMARTSUPPORT_ALLOWED_UPLOAD_EXTENSIONS` | `.pdf .md .markdown .txt .docx` | upload whitelist |
| `SMARTSUPPORT_RATE_LIMIT_*` | login 10/min · register 20/min · chat 20/min · upload 30/h · search 30/min · triage 20/min | sliding windows |
| `SMARTSUPPORT_EMBEDDING_CACHE_TTL` | 7 days | query-embedding cache |
| `SMARTSUPPORT_RETRIEVAL_INDEX_CACHE_TTL` | 3600 s | per-product vector index cache |
| `SMARTSUPPORT_SEED_ADMIN_EMAIL` / `_PASSWORD` | `admin@smartsupport.io` / `Admin12345!` | seed credentials |

---

## API reference

Base URL: `http://localhost:8000/api/v1` · Interactive docs: `/docs`.
All endpoints except `register`, `login`, `refresh` and `health` require a
Bearer access token. Admin-only endpoints are marked 🔒.

### Health
| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness + dependency check (database, Redis, Ollama) |

### Auth
| Method | Path | Description |
| --- | --- | --- |
| POST | `/auth/register` | Create an account (first account becomes admin) |
| POST | `/auth/login` | Email + password → access token; sets the refresh cookie |
| POST | `/auth/refresh` | Rotate the refresh token → new token pair |
| POST | `/auth/logout` | Revoke the session, clear the cookie |
| GET | `/auth/me` | Current user profile |
| PATCH | `/auth/me` | Update display name |
| POST | `/auth/password` | Change password (revokes all other sessions) |

### Products & documents
| Method | Path | Description |
| --- | --- | --- |
| GET | `/products` | List products (with per-status document stats) |
| POST | `/products` 🔒 | Create a product |
| GET | `/products/{id}` | Product detail (owner or admin) |
| PATCH | `/products/{id}` 🔒 | Update name/category/description |
| DELETE | `/products/{id}` 🔒 | Delete product, conversations and documents |
| POST | `/products/{id}/documents` 🔒 | Upload a manual (202 — ingestion is async) |
| GET | `/products/{id}/documents` | List the product's documents + statuses |
| GET | `/documents/{id}` | Document detail |
| DELETE | `/documents/{id}` 🔒 | Delete document + chunks + vector index |
| POST | `/documents/{id}/retry` 🔒 | Re-enqueue a failed ingestion |
| GET | `/documents/{id}/file` 🔒 | Download the original manual |

### Chat (conversations)
| Method | Path | Description |
| --- | --- | --- |
| POST | `/conversations` | Start a conversation for a product |
| GET | `/conversations` | List the user's conversations |
| GET | `/conversations/{id}` | Detail incl. messages, follow-ups, sources |
| PATCH | `/conversations/{id}` | Rename (owner only) |
| DELETE | `/conversations/{id}` | Delete (owner only) |
| POST | `/conversations/{id}/messages/stream` | **SSE chat** — see protocol below |
| POST | `/conversations/{id}/tickets` | Create an AI-triaged ticket from the conversation |

### Tickets
| Method | Path | Description |
| --- | --- | --- |
| GET | `/tickets` | Queue with filters: `status`, `needs_human`, `product_id`, `urgency`, `search` |
| GET | `/tickets/counts` | Tab + stat-strip counters (polled every 15 s) |
| GET | `/tickets/{id}` | Ticket detail |
| PATCH | `/tickets/{id}` | Workflow: `escalated` / `resolved` (+ `resolution_note`) / `dismissed` / `open` |

### Search & analytics
| Method | Path | Description |
| --- | --- | --- |
| POST | `/search` | Semantic search over manual chunks (optionally scoped to one product) |
| GET | `/analytics/overview` 🔒 | Totals, grounding rate, per-product stats, knowledge gaps, top questions |

---

## The RAG pipeline

```
question ─► [1] rewrite ─► [2] retrieve ─► [3] grounded answer ─► done
              (JSON schema)  (embed + NumPy)   (JSON schema, streamed)
                                     └─► [4] title (first exchange only)
```

1. **Query rewriting** — `ChatOllama(format=QueryRewrite.model_json_schema())`
   rewrites the user's follow-up into a standalone search query using up to six
   recent turns.
2. **Retrieval** — the rewritten query is embedded via Ollama `/api/embed`
   (result cached in Redis for 7 days) and compared against the product's
   `real[]` embedding matrix with **NumPy cosine similarity**. Top-k (6) chunks
   above a 0.20 score floor are kept; the per-product index is materialized once,
   pickled into Redis (1 h TTL) and invalidated on ingestion/deletion.
3. **Grounded answer** — a second chain enforces the `Answer` JSON schema via
   Ollama's native `format` (constrained decoding). The model cites excerpts
   **by number only**; the pipeline resolves those numbers into full
   `SourceRef`s (quote, score, page) taken straight from the retrieved chunks —
   the model can never fabricate a citation. Output:
   `answer, confidence, found_in_manual, cited_excerpts, follow_up_questions`.
4. **Title** — a third chain names the conversation after the first exchange.

### SSE streaming protocol

`POST /conversations/{id}/messages/stream` returns `text/event-stream`:

```
event: status   data: {"stage": "understanding_question" | "searching_manual" | "generating_answer", "detail": "…"}
event: sources  data: [{"chunk_id", "document_name", "quote", "score", "page"}, …]
event: token    data: {"delta": "…"}        ← many; live answer prose
event: answer   data: {full validated Answer object}
event: done     data: {"conversation_id", "assistant_message_id", "title", "latency_ms"}
event: error    data: {"message": "…"}      ← on failure
```

- `token` frames stream the answer prose **while constrained generation is still
  running** — the `answer` field of the JSON object is decoded incrementally from
  the token stream; the final `answer` event is the schema-validated object.
- The user turn and assistant reply are persisted **atomically** — a failed
  stream leaves nothing behind, so retries are clean.
- The frontend consumes the stream with `fetch` (not `EventSource`) so the POST
  body and Authorization header work naturally.

---

## Ticket triage & queue semantics

### Two-pass, deterministic escalation

1. **Classifier pass** — the customer message is triaged with the same Ollama
   native `format` technique into `category` / `urgency` / `sentiment`, plus
   extracted facts (`product`, `issue`, `requested_action`, `topics`) and a
   `summary`. Post-processing guarantees quality: a missing `requested_action`
   is derived from explicit request verbs as a **solution action** ("give me
   sugar" → "deliver sugar"; "how do I cancel…?" stays null), and category-slug
   noise is stripped from `topics`.
2. **Grounded-answer pass** — the same RAG chain used for chat answers the
   customer's question against the manuals. This pass, not the classifier,
   decides `needs_human`:
   - `found_in_manual = true` → the manuals resolve it; `needs_human = false`
     and urgency is normalized (critical/high → medium).
   - `found_in_manual = false` → `needs_human = true` with a concrete
     `escalation_reason` ("Not answerable from the available manuals.").
   - If the answer pass errors, the classifier verdict is kept (fail-safe).

### Queue semantics

| View | Meaning |
| --- | --- |
| **Active** (default) | `status ∈ {open, escalated}` — the actionable workload |
| **Needs human** | `needs_human = true` **and** active (resolved escalations drop out) |
| **Open / Escalated / Resolved** | exact status matches |
| **Dismissed** | archived, excluded everywhere unless explicitly filtered |

- List results are ordered by **urgency rank** (critical → low), then newest first.
- `GET /tickets/counts` returns `active / open / escalated / resolved / dismissed /
  needs_human / critical / high / medium / low` — urgency and needs-human counters
  are scoped to the active workload, so tab badges always match the tab contents.
- Search matches `raw_message`, `summary` and `category`; the urgency filter and
  product filter compose with every tab.
- Status transitions: `open → escalated → open (reopen)`, `open/escalated →
  resolved (note) / dismissed`, `resolved/dismissed → open (reopen)`. A stale
  selection survives refetches (the detail view keeps the mutated ticket object),
  so the resolution note renders immediately even after the row leaves the list.

---

## Authentication & security

- **Access token** — JWT (HS256), 30 min, held in memory by the SPA, sent as
  `Authorization: Bearer …`.
- **Refresh token** — 7 days, random URL-safe string, **HttpOnly cookie**
  (`ss_refresh_token`, `path=/api/v1/auth`, `SameSite=Lax`), stored **SHA-256
  hashed** in the `refresh_tokens` table with a family id.
- **Rotation + reuse detection** — every refresh issues a new token and revokes
  the old one; presenting a revoked token revokes the **entire family**
  (assumed token theft). Logout revokes and clears the cookie.
- **Password change** verifies the current password, revokes every other session
  and re-issues the calling device.
- **RBAC** — `admin` / `user` roles. Admin-only: product create/update/delete,
  document upload/delete/retry/download, analytics. Tickets: admins see all,
  users see their own.
- **Rate limiting** — Redis sliding window via atomic Lua scripts:

  | Scope | Limit |
  | --- | --- |
  | Login (per IP) | 10 / min |
  | Register (per IP) | 20 / min |
  | Chat (per user) | 20 / min |
  | Upload (per user) | 30 / hour |
  | Search (per user) | 30 / min |
  | Triage (per user) | 20 / min |

  The limiter **fails open** when Redis is unavailable (availability over strict
  enforcement) and logs a warning.

---

## Data model

| Table | Purpose |
| --- | --- |
| `users` | accounts (`admin` / `user`), bcrypt-hashed passwords |
| `refresh_tokens` | hashed refresh tokens with family ids for theft detection |
| `products` | support products (slug, name, category, description) |
| `documents` | uploaded manuals: original filename, storage path, status, error |
| `chunks` | manual chunks: text, `real[]` embedding, JSONB metadata (page, index) |
| `conversations` | chat sessions bound to a product + title |
| `messages` | turns with role, content, JSONB sources, confidence, follow-ups |
| `tickets` | triaged tickets: status, category, urgency, sentiment, needs_human, escalation_reason, summary, JSONB extracted_data, chat origin (`conversation_id`, `source_message_id`), resolution_note, triage latency |

Embeddings are stored as PostgreSQL `real[]` (`float4`) — no pgvector extension
required.

---

## Testing & verification

### Backend unit/integration suite (108 tests)

```bash
cd backend && venv/bin/pytest -q          # → 108 passed
make test
```

Runs against a real PostgreSQL `smartsupport_test` database with fakeredis and
fake AI components. Coverage includes: auth + refresh rotation + reuse
detection, RBAC, rate limiting, document lifecycle + ingestion idempotency,
NumPy retrieval math, pipeline orchestration, SSE endpoint, search, analytics,
ticket triage (deterministic escalation, queue filters, counts semantics,
resolution-note workflow) and the requested-action fallback.

### Browser E2E (Playwright, Chromium)

Requires the dev servers running (API :8000, frontend :5173, Ollama up) and
Playwright browsers (`npx playwright install chromium`).

```bash
cd frontend
node scripts/e2e-browser.mjs        # full walkthrough → screenshots in e2e-shots/
node scripts/e2e-stream-verify.mjs  # asserts the SSE event protocol
node scripts/e2e-fix-verify.mjs     # 11 regression checks (profile, dialogs,
                                    # insights, search, ticket workflow, mobile)
```

`e2e-browser.mjs` drives login → dashboard → product → chat (live SSE tokens) →
ticket triage → resolution and saves numbered screenshots into
`frontend/e2e-shots/`; it exits non-zero on the first failed step and dumps
browser console logs on failure.

### Frontend quality gates

```bash
cd frontend && npx tsc -b && npx eslint . && npm run build
```

---

## Design decisions

- **`float4[]` + NumPy instead of pgvector** — keeps the dependency surface small;
  the per-product similarity index is materialized once and cached (pickled in
  Redis), giving O(n·d) cosine per query — ideal for dev-scale corpora. The
  retrieval service is the single swap-in point for pgvector/HNSW later.
- **Ollama native structured output over prompt-hope-JSON** — every LLM stage
  passes its Pydantic schema via `format=`; Ollama constrains decoding so the
  output is always schema-valid JSON. Enums (urgency, sentiment, category) are
  enforced at generation time; responses are re-validated with
  `Schema.model_validate_json` as a final guard. Schema guarantees the *shape*;
  prompts steer the *content*; small deterministic post-processing steps
  (requested-action inference, topic cleanup) cover the semantic gaps a 0.5B
  model leaves.
- **Deterministic escalation over classifier-only flags** — the 0.5B classifier
  alone is too unreliable for `needs_human`; the grounded-answer pass
  (`found_in_manual`) is the actual decision, with the classifier as prior.
- **Idempotent Celery ingestion** — existing chunks are cleared before
  re-insertion, so Celery retries/backoff never duplicate vectors.
- **Atomic message persistence** — the user turn is committed together with the
  assistant reply after the stream completes, keeping the history consistent.
- **Two engines, one codebase** — asyncpg for the API, psycopg2 for Celery and
  Alembic; both point at the same schema.
- **Fail-open rate limiting** — a Redis outage degrades protection but never
  takes the product down; every bypass is logged.
- **SSE via `fetch`** — POST bodies and Authorization headers work naturally,
  unlike `EventSource`.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `/api/v1/health` reports `ollama: unavailable` | Ollama isn't running or models aren't pulled — `ollama serve`, then the two `ollama pull` commands above |
| Uploads stay `pending` | The Celery worker isn't running — start it (`make worker`) |
| `role "postgres" login failed` / DB missing | Create `smartsupport` (+ `smartsupport_test`) and check `DATABASE_URL` |
| 429 responses in bursts | Sliding-window rate limits; wait or raise `SMARTSUPPORT_RATE_LIMIT_*` |
| Slow first question | Ollama cold-start model load (tens of seconds on CPU); subsequent calls are fast |
| Empty answers / `found_in_manual: false` | No manual ingested for that product, or the question is outside the manuals (by design) |
| Login loops in the browser | Clear cookies (`ss_refresh_token`) — a revoked refresh family forces re-login by design |

## Production-hardening checklist

- [ ] Set a strong `SMARTSUPPORT_JWT_SECRET` and `SMARTSUPPORT_COOKIE_SECURE=true` (HTTPS)
- [ ] Restrict `SMARTSUPPORT_CORS_ORIGINS` to the real frontend origin
- [ ] Replace the seeded admin credentials
- [ ] Run PostgreSQL/Redis with TLS + network isolation; back up `data/uploads`
- [ ] Move to pgvector + HNSW when the corpus outgrows NumPy retrieval
- [ ] Consider a larger instruct model (the 0.5B keeps latency/cost low but caps
      reasoning quality) and per-stage temperature tuning
- [ ] Add persistent Celery result backend + monitoring (Flower) and log shipping
