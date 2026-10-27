# Operations and production notes

## Deployment sequence

1. Use a production `.env` file held outside source control. Set `ENVIRONMENT=production`, `DEBUG=false`, a random `SECRET_KEY` with at least 32 characters, non-default PostgreSQL credentials, and a non-local `CORS_ALLOWED_ORIGINS` value. Database URL credentials should use URL-safe alphanumeric characters unless percent-encoded.
2. Build and start with `docker compose -f docker-compose.prod.yml up --build -d`.
3. Confirm `docker compose -f docker-compose.prod.yml ps` reports the database, migration job, backend, and frontend healthy/completed. Check `GET /api/v1/health` and `/api/v1/readiness` through the configured HTTPS endpoint.
4. Terminate TLS at a trusted reverse proxy or load balancer. If one is in front of Nginx, configure trusted client-IP forwarding at that edge; do not trust arbitrary `X-Forwarded-For` headers.

The production Compose file runs Alembic as a one-off dependency before the API. It does not run database migrations in the application lifespan. Keep the prior application image and a verified database backup for recovery. The new migration is additive on upgrade; its downgrade drops Brick 15–20 data tables and columns, so do not treat downgrade as a data-preserving rollback.

## Backups and restore

The PostgreSQL volume is persistent, but a volume is not a backup. Store encrypted, access-controlled dumps outside the host and outside the Compose volume. Example from PowerShell after production Compose is running:

```powershell
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U $env:POSTGRES_USER -d $env:POSTGRES_DB -Fc > .\finguide-backup.dump
```

The dump contains sensitive financial and personal data. Restrict access, encrypt it at rest and in transit, and apply the configured retention policy. Test restoration into a separate disposable PostgreSQL database before relying on a backup:

```powershell
docker compose -f docker-compose.prod.yml exec -T db createdb -U $env:POSTGRES_USER finguide_restore_test
docker compose -f docker-compose.prod.yml exec -T db pg_restore -U $env:POSTGRES_USER -d finguide_restore_test --clean --if-exists < .\finguide-backup.dump
```

The restore commands are provided as an operational procedure; a restore drill was not run in this workspace because no PostgreSQL/Docker service was available. Use a database administrator account if the application role cannot create databases.

## Monitoring and security boundaries

- `/api/v1/health` is liveness; `/api/v1/readiness` checks the database. The low-cardinality `/api/v1/metrics` endpoint is hidden by the public Nginx route and should be scraped only from the private Compose network by a trusted monitoring service.
- The API limiter is an in-process fallback. Production Compose also applies Nginx shared-memory request limiting, and Nginx overwrites `X-Real-IP` before forwarding to the private backend. If Nginx is replicated or another proxy is introduced, configure equivalent shared rate limits and explicitly trust only that proxy's client-IP header.
- Request logs contain method, path, status, and duration only. Request bodies, headers, exception text, and SQL parameters are excluded.
- The chatbot defaults to the rule-based engine. If `CHATBOT_PROVIDER=openai` or `gemini` is configured, monitor provider usage and cost; chat content is sent only after provider-specific `ai_conversation_processing` consent. The adapters send bounded chat turns only, not saved profile or market data. Gemini can use a lower-cost fallback model when its primary returns 503. Gemini's data handling differs by account tier; review Google's current Gemini API terms before enabling it. FinBERT is optional and runs only when local model weights and optional runtime libraries are supplied; the service never downloads model weights.
- To enable local FinBERT inference in the development Compose backend, set `INSTALL_FINBERT=true` in `.env`, rebuild with `docker compose build backend`, and recreate the backend with `docker compose up -d backend`. Then download the public `ProsusAI/finbert` model into the bind-mounted, git-ignored `backend/models/finbert` directory using `docker compose exec backend python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='ProsusAI/finbert', local_dir='/app/models/finbert')"`. Set `FINBERT_MODEL_PATH=/app/models/finbert` and `FINBERT_MODEL_VERSION=ProsusAI/finbert` in `.env`; restart the backend after changing environment values. This adds the CPU PyTorch and Transformers runtime only to the opt-in image build. The model is loaded lazily once per backend process and all inference after download is local. This classifier describes wording tone in a headline; it does not predict prices or validate recommendations. Check the model and library licenses before redistributing a build.
- The evidence input endpoint stores user-submitted evidence without fetching its URL. Publisher identity is unverified, credibility remains zero, and recommendations do not consume it. Configure a vetted provider adapter and its source-verification policy before enabling external evidence in recommendations.

## Known production limits

- Authentication supports short-lived HMAC-SHA256 JWTs in HttpOnly SameSite=Strict cookies (or bearer tokens). Email verification, password reset, refresh-token rotation, and account recovery are not implemented.
- Financial-analysis consent is required for production data APIs; external news analysis has a separate consent gate. Consent history is append-only until account deletion.
- Feedback evaluation reports observed user signals and gate outcomes, with explicit denominators. It is not an expert-labeled accuracy benchmark and must not be described as proof of recommendation correctness.
- News summarization is not supplied. FinBERT is opt-in; missing model files or libraries produce an `uncertain` signal without falling back to fabricated sentiment.
- Request counts, durations, and rate-limit state are process-local. Nginx is the shared limiter in the supplied single-edge deployment; deploy a shared monitoring and rate-limit service if the topology changes.
- A clean Alembic upgrade to the current head and the complete database-backed backend suite were run against disposable PostgreSQL containers. The backend suite passed 213 tests. Frontend tests (20), lint, and production build passed. A real-browser end-to-end session, load test, penetration test, and backup restore drill were not run.

