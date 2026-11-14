# Milestone 9 — QA and Security Hardening

**Status:** Local QA/security gate executed with fixes applied; production/release sign-off remains open because cross-database, browser/usability, live OCR/provider, and evaluation-corpus checks could not be run in this environment.  
**Verification date:** 12 November 2026  
**Database migration:** None.  
**Dependency changes:** None.

## Findings addressed

### Production browser policy

- Staging/production responses now include a restrictive Content Security Policy: same-origin defaults, same-origin scripts/connections/forms, no objects, and no frames. No inline scripts are permitted.
- `style-src 'unsafe-inline'` remains necessary because current UI templates use fixed inline style attributes; this is a known CSP exception to remove in a later UI cleanup. Development keeps the policy disabled so local development tools are not broken.
- Existing security headers remain in place: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control: no-store`, and `Pragma: no-cache`.

### LLM link-boundary hardening

- Context and model-output validation now reject scheme-based links, `www.` links, and bare-domain URL forms before provider I/O or response rendering.
- New tests cover `https://`, `www.`, and naked-domain link cases; rejected context is verified not to invoke the transport.

### CI and frontend security checks

- The Windows/Linux CI matrix now runs Node 22 syntax checks and a dependency-free frontend security smoke test, in addition to Ruff and backend tests.
- CI now checks Python dependency consistency with `pip check` and includes `scripts/` in Ruff checks.
- Frontend smoke checks verify dynamic account text is HTML-escaped, API fetches use same-origin credentials, browser storage is not used for session state, and static HTML/CSS do not rely on external origins.

## Verification results

| Check | Result |
|---|---|
| `ruff format --check backend scripts` | Passed; all 101 files already formatted. |
| `ruff check backend scripts` | Passed. |
| Node syntax checks for `api.js`, `views.js`, and `app.js` | Passed. |
| `node frontend/tests/security-smoke.mjs` | Passed. |
| Full backend suite, `python -m pytest -q backend/tests` | **81 passed in 9.42 s.** |
| `pip check` in dev and runtime environments | Passed; no broken requirements found in either environment. |
| Alembic current/check | `0005_rules_rag_analysis` is head; **No new upgrade operations detected.** |
| Production header tests | Passed for restrictive CSP and existing secure-cookie/Origin behavior. |
| LLM outbound/output tests | Passed for bounded payloads, consent, provider isolation, malformed/invented citation fields, and link rejection before network access. |

### Local loopback performance smoke

Measured against the M8 preview server using the isolated temporary SQLite database, Uvicorn on loopback, one sequential keep-alive client, five warm-up requests and 100 measured `GET`s per endpoint:

| Endpoint | Requests | p50 | p95 | Max |
|---|---:|---:|---:|---:|
| `/health/live` | 100 | 1.020 ms | 1.169 ms | 1.287 ms |
| `/health/ready` | 100 | 1.206 ms | 1.502 ms | 1.539 ms |
| `/static/js/app.js` | 100 | 2.520 ms | 2.953 ms | 3.178 ms |

These are local loopback smoke measurements only—not production benchmarks, concurrency results, an SLA, or measurements of OCR/RAG/LLM latency.

## Existing coverage exercised

The current suite also covers Argon2id password handling, token hashing/expiry, CSRF/origin checks, secure cookies, session revocation, generic login errors, authentication/upload/explanation rate limits, image byte/type/pixel validation, upload-body limits, private scan ownership, export/deletion cascades, versioned provider consent, deterministic rule/citation freshness, and mocked LLM provider schemas/fallbacks.

## Not run / release gates still open

- PostgreSQL migrations/integration tests: not run; `psql`/`pg_isready` and a PostgreSQL service are unavailable. Migrations have SQLite coverage only.
- Docker image build and Windows CI: not run here. The CI workflow is configured, but its GitHub-hosted runs have not been observed.
- Live Tesseract OCR/accuracy, live Ollama/Qdrant retrieval quality, OpenAI/Groq calls, provider retention terms, and generated-explanation quality: not run. No live provider call was made.
- Real ingredient/evidence/rule corpus and evaluation data: empty. No ingredient extraction, warning precision/recall, citation semantic support, or clinical/safety metric can be reported.
- Browser/device matrix, keyboard/screen-reader audit, WCAG 2.2 AA review, user testing, and formal usability/performance study: not run. Node syntax and static integration checks are not browser QA.
- Dependency vulnerability/CVE audit: not run. `pip check` checks dependency consistency, not known vulnerabilities.
- Production SMTP, backup/restore, object-storage lifecycle, multi-worker rate-limit behavior, and operational monitoring: not run.

## Remaining risks and next actions

1. Run the Windows/Linux GitHub matrix and Docker build, then execute PostgreSQL migration and integration tests before deployment.
2. Obtain a licensed, reviewed evaluation corpus and qualified review for rules/citations; measure OCR, extraction, rule, and citation quality before real findings are enabled.
3. Complete keyboard, screen-reader, mobile/browser and WCAG review; add user testing and broader automated frontend tests.
4. Replace process-local limiters with shared enforcement before horizontal scaling, and decide on a production storage/backup policy.
5. Evaluate a dependency vulnerability scan and establish an update/patch process; `pip check` is not a security scanner.

M9 local checks pass, but this report does not claim production readiness or complete the release gates above. “No finding” remains no evidence of safety.
