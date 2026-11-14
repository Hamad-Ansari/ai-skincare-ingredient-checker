# Milestone 3 — Authentication, Profiles, and Account Privacy

**Status:** Implemented and locally verified on CPython 3.11.18/Linux. Windows CI, Docker, PostgreSQL, and live SMTP delivery remain unverified.  
**Date:** 9 November 2026

## Implemented

- Added exact runtime pins for `argon2-cffi==25.1.0` and `email-validator==2.3.0`; refreshed universal Python 3.11 development/runtime locks.
- Added migration `0002_auth_profiles` for users, opaque server sessions, hashed one-time tokens, user-reported profiles/declarations, and provider-specific AI consent history. Foreign keys cascade on account deletion; SQLite enforces foreign keys locally.
- Added normalized email registration, email verification, login/logout, password-reset request/confirmation, safe generic authentication errors, and configurable SMTP STARTTLS delivery.
- Password hashes use Argon2id (`m=19456 KiB`, `t=2`, `p=1`) with library-generated salts. This matches OWASP's minimum recommended Argon2id configuration. Passwords are not returned, logged, or stored as plaintext.
- Session cookies are opaque, HttpOnly, SameSite=Lax, fixed-expiry, and Secure in staging/production. Only a SHA-256 digest of each high-entropy session token is stored. Logout revokes its session; password reset revokes all active sessions.
- Unsafe API requests require a signed double-submit CSRF cookie/header pair and Origin validation. The signing key is derived from the configured secret; production requires a matching Origin and a stable 32+ character secret. Sensitive API responses use `Cache-Control: no-store`.
- Authentication endpoints have bounded per-IP/per-account rate limits in process memory; identifiers are hashed in the in-memory buckets and are not persisted or logged.
- Added current-user/profile CRUD, display-name updates, user-declared ingredient term list/create/delete, and tested per-user data isolation. Profile and declared-term responses are explicitly labeled user-reported, not verified medical information.
- Added versioned, provider-specific OpenAI/Groq opt-in and revocation, with the exact text-only disclosure surfaced by the API. No provider API keys are accepted by these endpoints.
- Added JSON account export and password-confirmed account deletion, cascading current account records and clearing browser cookies.
- Added generic validation/database error responses that omit submitted values, SQL text, and connection details.

## Local API routes

- `GET /api/v1/auth/csrf`
- `POST /api/v1/auth/register`, `/verification/request`, `/verify-email`, `/login`, `/logout`
- `POST /api/v1/auth/password-reset/request`, `/password-reset/confirm`
- `GET/PATCH /api/v1/users/me`; `GET/PATCH /api/v1/users/me/profile`
- `GET/POST/DELETE /api/v1/users/me/declared-ingredients`
- `GET /api/v1/users/me/ai-consents`; `POST/DELETE /api/v1/users/me/ai-consents/{openai|groq}`
- `GET /api/v1/privacy/export`; `DELETE /api/v1/users/me` (requires password confirmation)

For local API testing, `.env.example` sets `AUTH_EXPOSE_DEV_TOKENS=true`; this exposes verification/reset tokens in development responses only. The settings validator refuses this flag in staging/production. Production/staging require PostgreSQL, SMTP host/from with STARTTLS, and a stable secret. No email server was available here, so delivery was not integration-tested.

## Dependencies

Direct pins added in this milestone: `argon2-cffi==25.1.0` and `email-validator==2.3.0`. Package metadata was checked and both packages installed into the CPython 3.11.18/Linux environment. Exact transitive resolutions are in `backend/requirements-lock.txt` and `backend/requirements-runtime-lock.txt`.

References: [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [argon2-cffi 25.1.0 on PyPI](https://pypi.org/project/argon2-cffi/25.1.0/), [email-validator 2.3.0 on PyPI](https://pypi.org/project/email-validator/2.3.0/).

## Verification performed

- `pytest -q` from a fresh Python 3.11 development-lock environment: **37 passed**.
- `ruff check backend`: **passed**.
- `ruff format --check backend`: **passed**.
- `uv pip check` on the fresh development lock: **all 42 packages compatible**; on the fresh runtime lock: **all 33 packages compatible**.
- SQLite Alembic upgrade/downgrade coverage includes account tables and revision `0002_auth_profiles`; the local database reports `0002_auth_profiles (head)` via `alembic current`.
- Restarted the local API on port 8000; `/health/live`, `/health/ready`, `/openapi.json`, and `/api/v1/auth/csrf` returned HTTP 200, with the CSRF endpoint issuing its cookie.
- Integration tests cover registration/verification, login, password reset and revocation, session expiration/logout, CSRF/Origin handling, profile/declaration ownership, consent/revocation, export/deletion cascades, rate limiting, and safe error output.

## Limitations and next steps

- Windows CI and Docker image build are configured but have not run. PostgreSQL and external SMTP delivery were not available for integration tests; do not treat Linux/SQLite success as Windows/PostgreSQL production verification.
- The rate limiter is process-local and does not coordinate multiple workers. Replace or supplement it with a shared limiter before horizontal scaling.
- SMTP delivery is synchronous with a bounded timeout. A transactional email/outbox worker and delivery monitoring are future hardening work.
- There is no frontend yet. Local verification/reset tokens are only surfaced because the development-only setting is enabled; never expose them in a deployed environment.
- No scan, image, OCR, ingredient evidence, safety-rule, RAG, or LLM functionality is implemented by this milestone. Provider consent is stored and queryable, but no provider calls exist yet.
- No production-readiness, regulatory, or security-certification claim is made.

**Follow-on status:** Milestone 4 added the reviewed ingredient/evidence catalog and Milestone 5 added image/OCR intake APIs. The current evaluation gate and remaining product scope are recorded in `docs/MILESTONE_5.md` and the architecture review.
