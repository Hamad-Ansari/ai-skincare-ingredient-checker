# System Architecture
## Clarity Checker — approved baseline

**Status:** Approved baseline; M10 deployment docs/scaffold and M11 release-gate automation are prepared and locally checked. The current backend suite passes 81 tests; local `pip-audit` found no known vulnerabilities in the Python lock files. CI is configured to upload Trivy image reports and block on fixable HIGH/CRITICAL OS/library findings, and to run a Chromium/Firefox/WebKit axe accessibility matrix. Local Playwright/axe runs in Chromium, Firefox, and WebKit covered 19 UI states each with zero violations; reported contrast targets were reviewed and representative 320/640 CSS-width overflow checks passed after responsive fixes. Broader manual accessibility review and hosted CI results remain unverified. A supplemental Dockerless remote-tag scan reported fixable HIGH/CRITICAL findings in PostgreSQL, Caddy, and the Python base image, but its timestamps conflict with the canonical session date; the exact built API image and hosted scan are unverified. M6/M7 still use synthetic fixtures and mocked providers, and the production ingredient/evidence/rule corpus remains empty. The owner selected no public source-code license and approved an encrypted off-host daily backup baseline (30-day retention, 24-hour RPO, 4-hour RTO, quarterly drills); code/data rights review and actual destination, scheduler/alerting, and restore-drill evidence remain open. Hosted CI, Docker/PostgreSQL runtime, CVE remediation/triage, broader browser/a11y sign-off, rights-cleared evaluation, live OCR/providers, and production sign-off remain pending.  
**Full review:** [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md)

## 1. High-level architecture

```text
Browser (HTML/CSS/Vanilla JS)
  └─ same-origin HTTPS, session cookie + CSRF token
       └─ FastAPI application
          ├─ Auth/profile/privacy and versioned REST API
          ├─ Scan orchestration + persisted job status
          ├─ OCR/image preprocessing adapter
          ├─ Ingredient normalization/catalog
          ├─ Deterministic rule engine
          ├─ Curated evidence + RAG retrieval
          └─ On-demand LLM explanation providers (optional)
               ├─ Ollama (private, operator-controlled endpoint)
               ├─ OpenAI (account-level opt-in)
               └─ Groq (account-level opt-in)

FastAPI / worker → SQLite (local development) or PostgreSQL (production)
FastAPI / worker → Qdrant (evidence vectors only)
Production worker → Celery + Redis (Linux container deployment)
API → private object storage (label photos retained until user deletion)
```

The browser makes relative `/api/v1/...` requests; it never calls `localhost` to reach another service. OpenAI/Groq credentials are server-side environment secrets, never frontend values or user-entered browser keys.

## 2. Technology choices

| Layer | Decision |
|---|---|
| Frontend | M8 same-origin responsive app using semantic HTML, custom CSS, vanilla JavaScript modules, and Fetch API. FastAPI serves `/` and `/static/`; no production frontend build system or CDN is required. Local Playwright/axe smoke covers 19 UI states in Chromium, Firefox, and WebKit plus representative 320/640 CSS-width overflow checks; formal accessibility/usability review remains pending. |
| API/runtime | Python 3.11, FastAPI, Pydantic, `pydantic-settings`, Uvicorn. |
| Relational database | SQLite for simple local development; PostgreSQL for integration, staging, and production. SQLAlchemy 2.x + Alembic migrations. |
| Vector search | Qdrant; local persistent mode for single-process development, Qdrant server in containerized environments. |
| OCR | Pillow for safe image decode/resize/re-encode; Tesseract baseline behind an adapter; evaluate PaddleOCR before selecting any replacement. |
| LLM providers | M7 provides optional Ollama, OpenAI, and Groq chat adapters for one explicitly requested current finding. OpenAI/Groq require current provider-specific account consent; strict structured output, deterministic fallback, and no provider switching. Live provider behavior/quality is unverified. |
| Background jobs | In-process development worker on Windows; Celery + Redis in Linux containers. Persist job state in the relational database. |
| Storage | Private per-user object storage for label photos; retain until user deletion; deletion/export workflows and backup-retention disclosure are required. |
| Testing | Pytest, Ruff, and the current Starlette TestClient backed by `httpx2`; later add integration tests against PostgreSQL/Qdrant/Redis. Unit tests do not require a live model. |

Milestones 2–6 pin direct dependencies in `backend/requirements.txt` and provide universal Python 3.11 development/runtime transitive locks. Milestone 5 adds Pillow and `python-multipart`; M6 adds `qdrant-client==1.20.0`. See `MILESTONE_5.md` and `MILESTONE_6.md` for test, lock, migration, OCR-engine, and retrieval verification boundaries. Windows CI, Docker image build, PostgreSQL, SMTP, and live Ollama/Qdrant integration remain unverified.

## 3. Data and scan flow

1. Authenticated user uploads a label image. The API verifies CSRF/auth, size, actual image format, dimensions, and rate limits; re-encodes and strips metadata; then stores it privately under a generated ID.
2. A persisted in-process job moves through queued/extracting/OCR states and runs the local Tesseract CLI through stdin/TSV. Raw OCR text and word confidence/bounds are unconfirmed. M5 does not automatically parse ingredient candidates; the editable list starts empty. If Tesseract or trained data is unavailable, the state reports that safely and manual correction remains possible.
3. User supplies/corrects the ingredient draft through the scan API and must explicitly confirm it. The resolver uses Unicode NFKC, case folding, and whitespace collapse for exact matches only; fuzzy matches stay unresolved, and aliases mapping to multiple catalog entries return `ambiguous` without a canonical ID.
4. Only explicitly confirmed items reach M6 analysis. Active rules are immutable, versioned ingredient-presence conditions over canonical IDs; their evidence mappings and the rules themselves have separate review/activation gates. No arbitrary rule code is executed.
5. Optional Qdrant retrieval uses an Ollama embedding and filters by the exact ingredient plus IDs from currently approved SQL mappings and approved Qdrant metadata. Qdrant supplies candidate ranks only; it does not determine warnings, ingredient identity, or citation text. If retrieval is absent or unavailable, deterministic analysis and SQL-backed citations remain available with an explicit retrieval status.
6. The API builds citations from current SQL source/evidence rows, rechecks mapping/review/source rights, and suppresses stale analysis results. No active/matching rule is explicitly not an assessment of safety; no safety score is provided.
7. M7 optionally explains one current deterministic finding only after it is explicitly requested. The caller selects Ollama, OpenAI, or Groq; OpenAI/Groq require current provider-specific consent. Only that confirmed ingredient, the current finding, and currently approved evidence summaries/permitted excerpts are sent. Source URLs, images, email, profile/skin data, other scan ingredients, full scans, arbitrary prompts, and conversation history are excluded. Provider failure returns deterministic rule text without switching providers; generated prose is ephemeral and cannot change findings or citations. The explanation endpoint does not accept or return model-supplied citations; the deterministic analysis remains authoritative.
8. The metadata-stripped JPEG remains in a generated-key per-user local private directory until scan/account deletion. Its authenticated photo endpoint returns only the owner's retained image. Account export includes scan/OCR/correction and analysis history; scan deletion cascades analysis rows and removes the photo. M5's BackgroundTasks runner is local and non-durable; production queue integration/recovery is still future work.

## 4. Key security boundaries

- Every user-owned database query and object-storage operation is scoped to the authenticated user.
- Browser auth uses an opaque server-side session cookie; no bearer/session token in localStorage. Unsafe requests require CSRF validation.
- OpenAI/Groq consent is persisted by provider and disclosure version (`clarity-cloud-consent-v2`), checked at request time, and revocable. Send only one finding's minimal text and currently approved evidence summaries/permitted excerpts; do not send source URLs, images, email, full scan, or profile/skin data. Store API credentials only on the backend.
- Public evidence indexing contains no user images, scans, profiles, or sensitivity data.
- Source/import workflows are admin-only and CSRF protected. Rights start pending; content is not fetched from arbitrary URLs; activation requires approved reuse rights, explicit row decisions, and an audit record. Rights revocation hides associated catalog entries from public lookup.
- LLMs cannot call tools, change rules, choose trusted citations, or make safety decisions.
- Logs exclude passwords, session tokens, provider keys, full images, and sensitive model prompts.

## 5. Scale and deployment

Local Windows development can run FastAPI, Tesseract, and Ollama natively with SQLite and a single-process worker. The production-like profile uses Linux containers for FastAPI, Celery, PostgreSQL, Redis, and Qdrant. Production requires HTTPS, a secrets manager, private encrypted object storage, email delivery, backups, monitoring, per-user quotas, and provider-cost monitoring.

Celery workers are not supported on native Windows; the production worker must run in a Linux container. A native Windows development worker is explicitly non-durable and single-process.

## 6. Related design documents

Milestone records: [MILESTONE_6.md](MILESTONE_6.md), [MILESTONE_7.md](MILESTONE_7.md), [MILESTONE_8.md](MILESTONE_8.md), the [MILESTONE_9.md QA/security report](MILESTONE_9.md), and the [MILESTONE_10.md deployment/docs report](MILESTONE_10.md). The [deployment guide](DEPLOYMENT.md), [launch checklist](DEPLOYMENT_CHECKLIST.md), and [license/attribution status](LICENSE_AND_ATTRIBUTION.md) record the M10 operational scope. The full architecture review contains the detailed PRD, feasibility review, database schema, API routes, threat assessment, roadmap, directory structure, QA strategy, risk register, and current approval decisions: [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md).
