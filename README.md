# Clarity Checker
### AI Skincare Ingredient Checker

An educational skincare ingredient analysis platform. The same-origin responsive vanilla-JavaScript interface covers account flows, profile, private label scans, review-first ingredient entry, deterministic findings, server-validated citations, settings, and privacy controls. OCR is unavailable in the current app image, so label ingredients must be entered manually. The production evidence/rule corpus remains intentionally empty; comparison and routine APIs are still forthcoming.

> **Safety scope:** This product provides educational information. It does not diagnose, prescribe, or guarantee that a product is safe for an individual. “No configured rule triggered” is not proof of safety.

## Project status

- **Milestone 1 — requirements and architecture:** complete and approved.
- **Milestone 2 — backend foundation:** implemented and tested locally on Linux/Python 3.11.
- **Milestone 3 — authentication and profiles:** implemented and tested locally.
- **Milestone 4 — ingredient/evidence catalog foundation:** schemas, exact resolver, source/license registry, reviewed import workflow, admin controls, and audit trail implemented and tested locally. The production seed manifest is intentionally empty until a real source and its reuse rights are reviewed.
- **Milestone 5 — image intake and OCR:** authenticated/CSRF-protected upload, byte/pixel validation, safe metadata-free re-encoding, private per-user storage, persisted OCR state, correction/confirmation APIs, photo retrieval, export, and deletion are implemented and tested locally. The sandbox has no Tesseract executable, so live OCR and accuracy are not verified; missing-engine behavior is explicit.
- **Milestone 6 — deterministic rules, evidence retrieval, and private analysis:** versioned ingredient-presence rules, separately reviewed evidence mappings, optional Ollama/Qdrant retrieval, confirmed-scan owner-scoped analysis, and current SQL-validated citations are implemented and locally tested with synthetic-only fixtures. Full backend suite: 67 passed at M6 completion; Ruff and SQLite migration-drift checks passed. Live Ollama/Qdrant quality and any real evidence corpus are not verified; production rules/evidence remain empty.
- **Milestone 7 — on-demand LLM explanations:** optional structured Ollama/OpenAI/Groq adapters explain one current deterministic finding only when explicitly requested. Cloud calls require current provider-specific consent; prompts contain only one confirmed ingredient, reviewed finding text, and currently approved evidence summaries/permitted excerpts. Generated prose is ephemeral and cannot add warnings or citations; failures show deterministic rule text without switching providers. M7 backend suite: 76 passed; Ruff passed; no migration added. Live providers and explanation quality are not verified.
- **Milestone 8 — frontend modules:** a same-origin responsive vanilla-JS interface covers landing/auth/onboarding, dashboard, profile, scan review/results, history, settings/privacy, and safety notes. Compare/routines are honest placeholders because those APIs do not exist yet. Formal accessibility/usability review remains pending.
- **Milestone 9 — local QA/security hardening:** production CSP, broader LLM URL rejection, and frontend escaping/security smoke checks added. Full backend suite: 81 passed; Ruff, Node checks, `pip check`, and SQLite migration-drift checks passed. Cross-database, live OCR/providers, Docker, Windows CI, CVE audit, and user/accessibility evaluation remain unverified.
- **Milestone 10 — deployment/docs scaffold:** single-Linux-host Compose path adds Caddy TLS termination, PostgreSQL with a restricted app role, private scan storage, health checks, and encrypted backup/restore helpers. The owner selected no public code license and approved daily encrypted off-host backups with 30-day retention, 24-hour RPO, 4-hour RTO, and quarterly restore drills. Destination setup, target-host scheduling/alerts, restore-drill evidence, and deployment sign-off remain open. Docker/PostgreSQL/hosted CI have not been verified here.
- **Milestone 11 — release-gate preparation:** PostgreSQL, Compose backup/restore, Python dependency-audit, Trivy image-scan, and Chromium/Firefox/WebKit accessibility CI jobs are configured. Trivy reports upload before enforcement and the selected gate blocks fixable HIGH/CRITICAL OS/library findings. A supplemental Dockerless remote-tag scan reported findings in PostgreSQL, Caddy, and the Python base; its timestamps conflict with the canonical session date, so results are provisional and must be rerun. Local Playwright/axe runs covered 19 states in each engine with zero violations; 19 keyboard/focus, contrast, and reflow assertions passed per engine. A 320px test uncovered and fixed public-header/settings overflow. This is not WCAG sign-off; native-device, screen-reader, actual zoom, and user review remain open. Local suite: 81 passed; `pip-audit` reported no known vulnerabilities in either Python lock file. The owner selected no public source license and approved daily encrypted off-host backups with 30-day retention, 24-hour RPO, 4-hour RTO, and quarterly restore drills; data/reviewer intake, destination setup, target-host timer/alerting, live restore drills, hosted CI, Docker/PostgreSQL, and exact built-image results remain unverified/open; no production sign-off.
- **Hosted Windows/Linux CI and Docker image build:** configured but not yet observed; PostgreSQL and live SMTP also remain unverified.
- Comparison/routine APIs, real ingredient/evidence data, and evaluation corpus remain future work. “No finding” is not evidence of safety; generated explanations may be incomplete or inaccurate.

## Approved decisions

- **Brand:** Clarity Checker. **Descriptor:** AI Skincare Ingredient Checker.
- **Frontend/backend:** semantic responsive HTML, custom CSS, vanilla JavaScript ES modules served by FastAPI; Python 3.11.
- **Data:** SQLite for simple local development; PostgreSQL for integration and production; Qdrant for evidence retrieval.
- **AI:** M6 uses Ollama embeddings for retrieval; M7 adds optional on-demand chat explanations through Ollama, OpenAI, and Groq. OpenAI/Groq calls require current provider-specific account consent. Only one confirmed ingredient, its deterministic finding, and current approved evidence summaries/permitted excerpts are sent; source URLs, raw images, email addresses, other scan ingredients/full scans, and profile/skin data are excluded. No arbitrary prompt/history is accepted. Generated text is not stored and cannot change findings or SQL-validated citations.
- **Image privacy:** uploaded label photos are private and retained until the user deletes them. Export/deletion workflows and backup-retention disclosure are required.
- **Analysis:** user confirmation before analysis; deterministic, versioned, evidence-linked rules; optional LLM prose is a supplemental explanation only and cannot decide warnings, alter findings, or supply citations. Model output is not fact-verified and is labeled accordingly.

## Documentation

- [Product requirements](docs/PRD.md)
- [Architecture summary](docs/ARCHITECTURE.md)
- [Full architecture and feasibility review](docs/ARCHITECTURE_REVIEW.md)
- [Milestone 1 record](docs/MILESTONE_1.md)
- [Milestone 2 record](docs/MILESTONE_2.md)
- [Milestone 3 record](docs/MILESTONE_3.md)
- [Milestone 4 record](docs/MILESTONE_4.md)
- [Milestone 5 record](docs/MILESTONE_5.md)
- [Milestone 6 record](docs/MILESTONE_6.md)
- [Milestone 7 record](docs/MILESTONE_7.md)
- [Milestone 8 record](docs/MILESTONE_8.md)
- [Milestone 9 QA/security report](docs/MILESTONE_9.md)
- [Milestone 10 deployment/docs report](docs/MILESTONE_10.md)
- [Installation guide](docs/INSTALLATION_GUIDE.md)
- [Single-host Docker Compose deployment guide](docs/DEPLOYMENT.md)
- [Deployment and launch checklist](docs/DEPLOYMENT_CHECKLIST.md)
- [Hosting recommendation and budget check](docs/HOSTING_RECOMMENDATION.md)
- [Hosting and backup vendor quote request](docs/HOSTING_VENDOR_RFQ.md)
- [End-user guidebook (HTML draft)](docs/USER_GUIDEBOOK.html)
- Bilingual pre-launch walkthrough: [English MP4](frontend/assets/clarity-walkthrough-en.mp4) · [English WebM](frontend/assets/clarity-walkthrough-en.webm) · [Urdu MP4](frontend/assets/clarity-walkthrough-ur.mp4) · [Urdu WebM](frontend/assets/clarity-walkthrough-ur.webm) · [English transcript](frontend/assets/clarity-walkthrough-transcript-en.txt) · [Urdu transcript](frontend/assets/clarity-walkthrough-transcript-ur.txt). Caption tracks and posters live beside the videos in `frontend/assets/`; keep that folder with the guidebook so its embedded media resolves.
- [License and attribution status](docs/LICENSE_AND_ATTRIBUTION.md)
- [Production data/reviewer intake](docs/PRODUCTION_DATA_INTAKE.md)
- [Production source/reviewer worksheet](docs/PRODUCTION_REVIEW_WORKSHEET.md)
- [External verification handoff (redacted results only)](docs/EXTERNAL_VERIFICATION_HANDOFF.md)
- [M11 accessibility source review](docs/ACCESSIBILITY_REVIEW.md)
- [M11 container CVE review](docs/CONTAINER_CVE_REVIEW.md)
- [Milestone 11 release-gate report](docs/MILESTONE_11.md)

## Quick start — Windows PowerShell

From the repository root, use Python 3.11:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Full Windows and Linux instructions are in [INSTALLATION_GUIDE.md](docs/INSTALLATION_GUIDE.md).

## Current API

- `GET /` — responsive same-origin web interface; static frontend modules load under `/static/`.
- `GET /health/live` — process liveness.
- `GET /health/ready` — database-backed readiness.
- `GET /api/v1/auth/csrf`; `POST /api/v1/auth/register`, `/login`, `/logout`, `/verify-email`, and password-reset routes.
- `/api/v1/users/me` — current account, user-reported profile, and declared ingredient terms; `GET /api/v1/users/me/ai-consents` returns the current disclosure/status, while `POST/DELETE /api/v1/users/me/ai-consents/{provider}` grants/revokes versioned, provider-specific OpenAI/Groq consent.
- `GET /api/v1/privacy/export`; `DELETE /api/v1/users/me` — current account/profile/scan and analysis-history export, plus password-confirmed deletion including private photos.
- `POST /api/v1/scans` — authenticated multipart upload; `GET /api/v1/scans` and `GET /api/v1/scans/{id}` — current-user history/state.
- `PATCH /api/v1/scans/{id}/ingredients`; `POST /api/v1/scans/{id}/confirm` — edit the draft and explicitly confirm before analysis.
- `POST/GET /api/v1/scans/{id}/analysis` — run and retrieve private deterministic analysis only for the owning user after explicit confirmation; citations are revalidated against current SQL evidence/source rights.
- `POST /api/v1/scans/{id}/analysis/findings/{finding_id}/explanation` — on-demand supplementary explanation for one current finding; choose `ollama`, `openai`, or `groq`. OpenAI/Groq require current provider-specific consent. The response is not stored and does not include model-supplied citations.
- `GET /api/v1/scans/{id}/photo`; `DELETE /api/v1/scans/{id}` — retrieve the owner's retained sanitized photo or delete the scan/photo and cascading analysis history.
- `POST /api/v1/ingredients/resolve`; `GET /api/v1/ingredients/{id}` — exact normalized lookup and source-linked catalog detail. Fuzzy matches are never auto-resolved.
- `/api/v1/admin/sources` and `/api/v1/admin/ingredient-imports` — authenticated, role-restricted source/license review and staged import/activation workflow.
- `/api/v1/admin/rule-versions` — versioned deterministic rule lifecycle with separately reviewed evidence mappings; `/api/v1/admin/evidence/{id}/index` explicitly indexes only a current approved evidence summary.
- `/docs` and `/openapi.json` are enabled in development/test only.

The app UI is served at `/`; its HTML, CSS, and JavaScript assets load from the same origin. Unsafe API requests require a signed CSRF cookie/header pair; production also requires a matching Origin. For local testing, `.env.example` enables `AUTH_EXPOSE_DEV_TOKENS=true` so verification/reset tokens can be copied from responses. Production settings reject that flag and require SMTP STARTTLS, a strong `APP_SECRET_KEY`, and PostgreSQL. Comparison/routine APIs and a formal accessibility/usability review remain future work.

### Optional live evidence retrieval

For live vector retrieval, install and start Ollama, install the configured embedding model (for example, `ollama pull embeddinggemma`), and configure exactly one Qdrant backend: `VECTOR_DB_PATH` for single-process local development or `QDRANT_URL` for a Qdrant server. `RAG_TOP_K` controls the bounded retrieval count. Without a reachable embedding model and vector store, deterministic rules and current SQL-backed citations still work; retrieval is reported as unconfigured or unavailable. The production corpus is empty, and test fixtures are synthetic only. Do not treat retrieval as a safety decision or an absence of findings as proof of safety. See [Milestone 6](docs/MILESTONE_6.md) for configuration and verification boundaries.

To grant catalog-editor access, first create and verify an account, then run this trusted operator command from the repository root; there is no self-service role-promotion endpoint:

```powershell
.\.venv\Scripts\python.exe scripts\grant_admin.py --email verified-user@example.com
```

```bash
.venv/bin/python scripts/grant_admin.py --email verified-user@example.com
```

The initial Alembic baseline has no application tables. Migration `0002_auth_profiles` adds account/profile/consent tables; `0003_ingredient_evidence` adds the source registry, ingredient/alias catalog, evidence records, reviewed imports, and admin audit trail; `0004_image_scans` adds private scan and OCR/correction state; `0005_rules_rag_analysis` adds reviewed rule versions, evidence mappings, private analysis history, findings, and citation links. No external ingredient dataset or production rule is seeded. Local OCR uses Tesseract when installed; the app reports an unavailable engine and still permits manual correction/confirmation when it is absent.

## Dependencies and secrets

Direct dependencies are pinned in `backend/requirements.txt` and development dependencies in `backend/requirements-dev.txt`. `backend/requirements-lock.txt` pins the universal Python 3.11 development/test resolution; `backend/requirements-runtime-lock.txt` is the runtime lock used by the Dockerfile. `.env.example` contains placeholders only; `.env` is ignored by Git. Do not commit real API keys, provider credentials, or user scan data.

## License and data attribution

The owner selected **no public source-code license or reuse grant**; no `LICENSE` file is added. Treat the code as copyrighted and do not redistribute or reuse it without separate written permission. Data, evidence, image, and model rights are reviewed separately; see [license and attribution status](docs/LICENSE_AND_ATTRIBUTION.md), the [production data intake](docs/PRODUCTION_DATA_INTAKE.md), and the [deployment release gates](docs/DEPLOYMENT_CHECKLIST.md).
# ai-skincare-ingredient-checker
