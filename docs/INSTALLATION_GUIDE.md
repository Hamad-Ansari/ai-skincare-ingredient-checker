# Installation Guide — local development (Milestones 2–10)

This guide installs the local FastAPI backend, same-origin vanilla-JavaScript UI, authentication/profile APIs, reviewed ingredient catalog, image/OCR intake, deterministic rule administration, private analysis, and on-demand explanation APIs. The frontend is served at `/` with assets under `/static/`; no Node/npm build is required. Commands assume you are running them from the repository root because the SQLite and local Qdrant paths in `.env.example` are relative to that directory. For the separate single-Linux-host Docker Compose deployment path, see the [deployment guide](DEPLOYMENT.md); it has not been runtime-verified and is not production sign-off.

## Prerequisites

- Windows 10/11 with Python 3.11 (64-bit) and the Python Launcher (`py`) available, or Linux with Python 3.11.
- Visual Studio Code is recommended.
- Internet access to install pinned packages.
- Docker, PostgreSQL, Redis, a remote Qdrant server, a live Ollama model, and SMTP are **not required** for local API development or deterministic scan analysis. The local Qdrant client and Ollama are optional when testing live retrieval. Tesseract plus its English trained data is optional: when unavailable, the scan API records an explicit unavailable OCR state and still allows manual correction/confirmation. The local API uses SQLite and the development-only verification/reset token setting. No external ingredient source or license is assumed or auto-imported.

## Windows 10/11 — PowerShell

Open PowerShell in the project folder:

```powershell
Set-Location C:\path\to\ai-skincare-ingredient-checker
py -3.11 --version
```

Create an isolated virtual environment and install the pinned development dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Create a local environment file if you do not already have one:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

The development example uses SQLite and requires neither a secret, provider API key, nor SMTP service. It intentionally enables `AUTH_EXPOSE_DEV_TOKENS=true` so local registration/reset flows can be tested without email; the settings validator rejects this flag in staging/production. If you already have an older `.env`, add this setting manually for local testing. Never enable it on a deployed service. Do not put real credentials in `.env.example` or commit `.env`.

Run all database migrations (including M6 rules/analysis), tests, and lint checks:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check backend scripts
.\.venv\Scripts\ruff.exe format --check backend scripts
.\.venv\Scripts\python.exe -m pip check
```

If Node.js 20 or newer is installed, also run the frontend syntax/security smoke checks (no npm install is needed):

```powershell
node --check frontend\js\api.js
node --check frontend\js\views.js
node --check frontend\js\app.js
node frontend\tests\security-smoke.mjs
```

Start the development API from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

- Clarity Checker web app: `http://127.0.0.1:8000/`
- Liveness: `http://127.0.0.1:8000/health/live`
- Database readiness: `http://127.0.0.1:8000/health/ready`
- Development OpenAPI docs: `http://127.0.0.1:8000/docs`

Stop the server with `Ctrl+C`.

### Optional PowerShell auth API smoke test

With the API running, keep a web session so the CSRF and HttpOnly session cookies persist:

```powershell
$base = 'http://127.0.0.1:8000'
$web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$csrf = Invoke-RestMethod -Uri "$base/api/v1/auth/csrf" -WebSession $web
$headers = @{ 'X-CSRF-Token' = $csrf.csrf_token; Origin = $base }
$email = "local-$([guid]::NewGuid().ToString('N'))@example.com"
$password = 'correct horse battery staple'
$registration = Invoke-RestMethod -Method Post -Uri "$base/api/v1/auth/register" `
  -WebSession $web -Headers $headers -ContentType 'application/json' `
  -Body (@{ email = $email; password = $password } | ConvertTo-Json -Compress)
$verificationToken = $registration.dev_verification_token # development only
Invoke-RestMethod -Method Post -Uri "$base/api/v1/auth/verify-email" `
  -WebSession $web -Headers $headers -ContentType 'application/json' `
  -Body (@{ token = $verificationToken } | ConvertTo-Json -Compress)
$login = Invoke-RestMethod -Method Post -Uri "$base/api/v1/auth/login" `
  -WebSession $web -Headers $headers -ContentType 'application/json' `
  -Body (@{ email = $email; password = $password } | ConvertTo-Json -Compress)
$headers['X-CSRF-Token'] = $login.csrf_token # login rotates the CSRF token
Invoke-RestMethod -Uri "$base/api/v1/users/me" -WebSession $web
Invoke-RestMethod -Method Post -Uri "$base/api/v1/auth/logout" -WebSession $web -Headers $headers
```

The development token is returned only when `AUTH_EXPOSE_DEV_TOKENS=true`; production/staging reject that setting. All unsafe API requests need the CSRF header, and production also requires a matching `Origin`.

### Granting catalog-editor access

After registering and verifying an account, a trusted operator can grant its admin role from the repository root. There is no user-facing role-promotion route:

```powershell
.\.venv\Scripts\python.exe scripts\grant_admin.py --email verified-user@example.com
```

```bash
.venv/bin/python scripts/grant_admin.py --email verified-user@example.com
```

The command refuses missing, inactive, or unverified accounts. Keep the command available only to trusted operators with database access.

## Linux

From the repository root:

```bash
python3.11 --version
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
```

Create the local environment file once:

```bash
cp .env.example .env
```

Then run:

```bash
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini current
python -m pytest -q
ruff check backend scripts
ruff format --check backend scripts
python -m pip check
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

If Node.js 20 or newer is installed, run the optional frontend checks (no npm install is required):

```bash
node --check frontend/js/api.js
node --check frontend/js/views.js
node --check frontend/js/app.js
node frontend/tests/security-smoke.mjs
```

## Optional fully pinned dependency set

`backend/requirements.txt` and `backend/requirements-dev.txt` pin direct dependencies. `backend/requirements-lock.txt` pins the development/test transitive packages for Python 3.11 across common platforms; `backend/requirements-runtime-lock.txt` is used by the Docker image. To install the development environment from the dev lock file instead of resolving the input files again:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
```

```bash
python -m pip install -r backend/requirements-lock.txt
```

Refresh the lock only after reviewing dependency updates and running the full test matrix.

## Optional local Tesseract OCR

The OCR adapter calls the configured local Tesseract executable through stdin; uploaded photos are not sent to a cloud service. Install Tesseract and the language trained data you intend to use, then verify `tesseract --version` and `tesseract --list-langs` from the same environment that launches FastAPI. See the [official Tesseract installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html).

Set these optional values in `.env` if the executable or language differs from the defaults:

```dotenv
OCR_TESSERACT_COMMAND=tesseract
OCR_TESSERACT_LANGUAGE=eng
OCR_TIMEOUT_SECONDS=30
```

`OCR_TESSERACT_COMMAND` may be an absolute executable path (quote it in `.env` if it contains spaces). The configured language must have its trained data installed. Without the executable or language data, scans remain reviewable and return an explicit OCR error state; no OCR accuracy is assumed.

## Scan storage and limits

`PRIVATE_SCAN_STORAGE_DIR` defaults to `./data/private/scans`, outside the frontend/public assets. The application creates per-user directories and opaque file keys; it does not use the uploaded filename. Default limits are `SCAN_MAX_UPLOAD_BYTES=10485760` (10 MiB) and `SCAN_MAX_IMAGE_PIXELS=20000000`. Supported actual image formats are JPEG, PNG, and WebP; successful uploads are re-encoded to metadata-free JPEG. Photos remain stored until per-scan or account deletion. The local filesystem adapter is not a substitute for encrypted production object storage, backup policy, or deployment-level access controls.

## Optional live evidence retrieval

M6's rule analysis works without an embedding model or vector backend; retrieval then reports `not_configured` or `unavailable`, and the API still uses deterministic rules plus current SQL-backed citations. No real source/evidence records or active production rules are seeded.

To exercise the optional retrieval path:

1. Install and start Ollama using its official installation instructions.
2. Install the embedding model configured by `OLLAMA_EMBED_MODEL` (the example default is `embeddinggemma`), for example with `ollama pull embeddinggemma`.
3. Configure exactly one vector backend in `.env`: `VECTOR_DB_PATH=./data/qdrant` for the single-process local Qdrant client, or `QDRANT_URL=https://...` for a Qdrant server. For remote Qdrant, clear `VECTOR_DB_PATH` and set `QDRANT_API_KEY` only if the server requires it. The settings validator rejects simultaneous backends and keys without a remote URL.
4. Set `QDRANT_COLLECTION`, `RAG_EMBEDDING_TIMEOUT_SECONDS`, and `RAG_TOP_K` as needed. Local Qdrant data is ignored by Git. Do not share an embedded local path across multiple API/worker processes; deploy a Qdrant server for multi-process use.

The runtime constructs the vector client lazily. Evidence indexing is an explicit admin action, limited to a reviewed evidence summary and currently approved rights. Qdrant stores no private scan content. Live model quality, remote service behavior, and citation support have not been evaluated as a production corpus.

## Optional on-demand LLM explanations (M7)

The explanation endpoint is optional and has no database migration or additional dependency. It can explain only one current deterministic finding after the scan and every ingredient have been explicitly confirmed and analysis has completed. The provider is selected per request; it is never silently replaced.

Configure only the provider(s) you intend to offer in the backend `.env`:

```dotenv
# Private/local Ollama chat; provide a chat model already available to the Ollama service.
OLLAMA_CHAT_MODEL=

# Optional cloud providers; keep keys on the server and out of frontend code.
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=
GROQ_API_KEY=
GROQ_CHAT_MODEL=
LLM_TIMEOUT_SECONDS=30
```

`LLM_TIMEOUT_SECONDS` is bounded to 1–120 seconds. Ollama also uses `OLLAMA_BASE_URL`; the default is the local endpoint. OpenAI/Groq require both a server-side API key and a configured chat model. A missing provider configuration or provider/validation failure returns the reviewed deterministic rule message (`status: "fallback"`); it does not try another provider. Do not send secrets in API requests.

The endpoint is `POST /api/v1/scans/{scan_id}/analysis/findings/{finding_id}/explanation`, with a body such as `{"provider":"ollama"}`, `{"provider":"openai"}`, or `{"provider":"groq"}`. The response contains supplemental prose and a disclaimer, not citations. Keep displaying citations from `GET /api/v1/scans/{scan_id}/analysis`, where they are revalidated from SQL. The provider payload is limited to one confirmed ingredient, its current finding, and current approved evidence summaries/permitted excerpts; source URLs, images, email, the full scan, other scan ingredients, and profile/skin data are excluded. The text is not persisted and may be incomplete or inaccurate.

OpenAI/Groq are blocked until the user grants current, provider-specific consent. First call `GET /api/v1/users/me/ai-consents` and present its disclosure text. After the user explicitly accepts it, POST the returned `current_disclosure_version` to `/api/v1/users/me/ai-consents/openai` or `/groq` with `{"disclosure_version":"<current_disclosure_version>","accepted":true}`. Revoke consent with `DELETE /api/v1/users/me/ai-consents/{provider}`. These account routes require the normal authenticated session and CSRF protections. The active disclosure is `clarity-cloud-consent-v2`; an older consent version is not current. Ollama is a private operator-configured endpoint and does not require cloud consent.

An in-memory limit allows 10 explanation requests per user per hour per API process; it is not shared across multiple workers. Live provider connectivity, retention behavior, cost, latency, and explanation quality have not been verified. See [Milestone 7](MILESTONE_7.md).

## Current limitations

The local stack includes health/readiness, same-origin frontend modules, account/privacy APIs, provider consent, exact ingredient resolution, source/license registration, admin-reviewed import/activation, private scan/photo APIs, OCR-state/correction/confirmation, versioned deterministic rule administration, separate evidence-mapping reviews, optional Qdrant/Ollama retrieval, owner-scoped private scan analysis with server-validated citations, and M7's on-demand ephemeral Ollama/OpenAI/Groq explanations for one current finding. No configured findings are not an assessment of safety. The production seed and rule/evidence corpus are empty; tests use synthetic fixtures and mocked provider calls. Compare/routine endpoints and persistence are not implemented; their UI pages say so and do not create mock results. A formal accessibility/usability review is still required. The scan OCR runner uses in-process FastAPI `BackgroundTasks` and is non-durable across process restarts. The sandbox lacks Tesseract; live OCR/accuracy, Ollama/Qdrant retrieval quality, live LLM behavior/quality, Windows CI, Docker image build, PostgreSQL, and real SMTP delivery remain unverified. Development uses SQLite; staging/production settings require PostgreSQL and configured SMTP STARTTLS. Rate limiters are process-local and do not coordinate multiple workers.
