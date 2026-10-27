# FinGuide+ v1.1 — Bricks 01–20

FinGuide+ is a FastAPI, PostgreSQL, SQLAlchemy/Alembic, and React application for validated, evidence-aware, safety-gated personal-finance decision support. The implementation follows the locked architecture and plan included under [`docs/architecture`](docs/architecture/).

## Current implementation

Bricks 01–14 are retained. The application now includes the Brick 15–20 foundation: session authentication, ownership-scoped APIs, evidence provenance and freshness, optional local-only FinBERT, explicit safety-gated recommendation presentation, feedback and harmful-feedback incidents, descriptive evaluation snapshots, lifecycle audit events, consent history, account export/deletion, request metrics, rate limiting, production Compose assets, and an operations runbook.

External evidence submitted by a user is explicitly **unverified** with zero credibility and is never used by the deterministic profile-ratio recommendation engine. The separate market-research endpoint uses the free MFapi.in NAV API to produce a source-attributed equity-fund research shortlist (Nifty index, large-cap, flexi-cap, and, for aggressive profiles with longer horizons, mid-cap) when profile data and fresh NAV history are available. Candidates are held unless the saved emergency fund covers at least three months of expenses. This is a research preview, not an approved investment recommendation, and it does not send profile data to the provider. The NAV-only screen omits expense ratios, holdings, tracking error, taxes, and costs. Other mutual-fund categories, individual bonds, and gold products remain unavailable until verified feeds are configured. Nifty market-index data is not scraped. FinBERT remains optional and local-only; sentiment is `uncertain` when no local model is configured.

## Run locally with Docker Compose

1. Copy `.env.example` to `.env` and set a random local `POSTGRES_PASSWORD`. Use a simple alphanumeric value for the Compose URL.
2. To use Gemini, set `CHATBOT_PROVIDER=gemini`, `GEMINI_API_KEY`, and `GEMINI_MODEL=gemini-3.8-flash` in `.env`. The adapter can fall back to `GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite` during primary-model overload. To use OpenAI instead, set `CHATBOT_PROVIDER=openai`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. Provider keys stay in the backend environment and are not sent to the frontend. If provider credentials are missing, chat reports the provider as not ready.
3. Start the development services:

   ```powershell
   docker compose up --build -d
   docker compose exec backend alembic upgrade head
   ```

4. Open `http://localhost:5173`; the API is at `http://localhost:8000/api/v1`.

When Gemini or OpenAI is enabled, chat messages and bounded recent conversation context are sent to that provider only after the user grants current provider-specific AI conversation-processing consent in Chat or Settings. Gemini current-market questions use Google Search grounding and, when relevant, include a dated NIFTY 50 snapshot or up to four RBI/SEBI headlines retrieved by FinGuide. Earlier conversation turns and the saved financial profile are excluded from these market requests. Replies show links to retrieved and grounded sources; answers fail closed when no source is available. Google's terms say grounding prompts/context/output may be stored for 30 days; grounding can incur charges depending on API project and quota. The consent notice explains this and a policy-version change requires fresh consent. For Gemini's unpaid API quota, Google may use prompts and responses to improve products and human reviewers may process them; avoid sensitive information. OpenAI is not configured for live market retrieval and should not imply it has current data. The development identity remains available only when `ENVIRONMENT=development`. Production requires registered credentials and financial-analysis consent.

## Run without Docker

Use Python 3.12 and Node 22. Install dependencies from `backend/requirements.txt` and `frontend/package-lock.json`. Start PostgreSQL and create both `finguide` and `finguide_test` databases. Set `DATABASE_URL` to the local database URL.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

## Production Compose

Set production values in `.env`: `SECRET_KEY` (at least 32 random characters), database credentials, and the actual frontend origin in `CORS_ALLOWED_ORIGINS`. Set the `POSTGRES_*` values to alphanumeric credentials. Then run:

```powershell
docker compose -f docker-compose.prod.yml up --build -d
```

The migration service runs Alembic before the backend starts. PostgreSQL is not published to the host; the React build is served by Nginx, which proxies API traffic. Terminate HTTPS at a trusted reverse proxy/load balancer before exposing the deployment publicly. The API also supports signed bearer tokens for non-browser clients; browser sessions use HttpOnly, SameSite=Strict cookies.

## API lifecycle

- `POST /api/v1/auth/register` requires an explicit financial-analysis consent; `POST /auth/login` and `/auth/logout` manage the browser session.
- User-owned financial endpoints derive identity from the authenticated session or bearer token. A request-supplied `user_id` is never used for authorization.
- Recommendations begin as candidates. The deterministic suitability gate decides their status. Only approved or modified items can transition to `PRESENTED`; feedback is accepted only after presentation. Harmful feedback opens a safety incident.
- `POST /api/v1/evidence` stores provenance, a content hash, timestamps, duplicate/conflict metadata, and explicit unverified status. It does not fetch arbitrary URLs.
- `/api/v1/privacy/consent`, `/export`, and `/account` support consent history, data export, and confirmed account deletion.
- `/api/v1/evaluation/summary` reports descriptive user-feedback and safety rates with denominators. These are not claims of financial correctness.
- `/api/v1/health` is liveness, `/api/v1/readiness` checks PostgreSQL, and `/api/v1/metrics` exposes low-cardinality process metrics for trusted-network scraping.

OpenAPI is available at `/docs` in development. Every API error uses the shared error envelope.

## Tests and checks

Run backend unit tests without a database:

```powershell
cd backend
python -m pytest -q unit_tests
```

Run the full backend regression/API suite against a disposable PostgreSQL database whose name contains `test`:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://finguide:YOUR_TEST_PASSWORD@localhost:5432/finguide_test'
python -m pytest -q
```

Run frontend checks:

```powershell
cd frontend
npm test
npm run lint
npm run build
```

## Operations

See [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for backups, restore, monitoring, rate-limit scope, migration and rollback notes, and production limitations.

## Architecture sources

The architecture lock, final implementation plan, and seven architecture packs are copied into [`docs/architecture`](docs/architecture/). `AI_PROJECT_INSTRUCTIONS.md` was not present in either supplied workspace; no replacement interpretation was invented. The lock and implementation plan are the controlling project references.
