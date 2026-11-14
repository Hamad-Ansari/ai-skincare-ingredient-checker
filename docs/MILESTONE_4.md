# Milestone 4 — Ingredient and Evidence Base

**Status:** Implemented and locally verified on CPython 3.11.18/Linux with SQLite. Windows CI, Docker, and PostgreSQL remain unverified. The production seed is intentionally empty because no external source and reuse license have been approved.  
**Date:** 9 November 2026

## Implemented

- Added Alembic revision `0003_ingredient_evidence` for reviewed ingredients, aliases, evidence sources/records, import batches/rows, and admin audit events. Source and editorial records survive account deletion; actor references are nulled rather than blocking deletion.
- Added a conservative normalizer: Unicode NFKC, case folding, and whitespace collapse. It preserves punctuation, does not use edit distance or fuzzy suggestions, and version-labels the behavior as `exact_normalized_v1`.
- Added a public exact resolver and ingredient detail endpoint. A unique exact match resolves; multiple active ingredients for the same alias return `ambiguous` with no canonical ID; no match or a typo remains `unresolved`.
- Added a source registry with publisher/title/URL/type, license and attribution metadata, source version/checksum/retrieval time, pending/approved/restricted/rejected reuse status, reviewer note, and separate excerpt-reproduction permission. Rights begin pending. No server-side URL fetching or arbitrary-source crawling is performed.
- Added an admin-only import workflow. Submission validates and hashes the manifest but does not activate it. Every row must receive a reviewer decision; activation is an explicit transaction, requires current source-rights approval, and inserts only approved rows. Rejected rows are not activated; duplicate batches and canonical-name conflicts are blocked.
- Added source-linked evidence records with reviewer notes and rights-filtered public output. Excerpts are returned only when the current source review permits excerpt reproduction. Evidence records do not implement or imply safety rules.
- Added role-checked and CSRF-protected admin endpoints plus an audit trail containing only allowlisted action metadata. `scripts/grant_admin.py` promotes only an existing, active, verified account from a trusted operator shell and records a non-PII role-grant event; no API self-promotion path exists.
- Added `data/seed/ingredient_seed_manifest.json`. It intentionally contains no sources or imports. The test-only synthetic fixture demonstrates an alias shared by two distinct candidates and confirms the resolver does not guess.

## API routes

- `POST /api/v1/ingredients/resolve` — exact normalized lookup; requires the standard CSRF cookie/header pair.
- `GET /api/v1/ingredients/{ingredient_id}` — active catalog detail with source and approved evidence metadata.
- `POST/GET /api/v1/admin/sources` — register source metadata and list source rights state.
- `POST /api/v1/admin/sources/{source_id}/rights-review` — approve, restrict, or reject reuse and separately set excerpt permission.
- `POST/GET /api/v1/admin/ingredient-imports` — submit a source-approved manifest and list batches.
- `GET /api/v1/admin/ingredient-imports/{batch_id}` — inspect rows and review status.
- `POST /api/v1/admin/ingredient-imports/{batch_id}/rows/{row_id}/review` — approve or reject one row with a review note.
- `POST /api/v1/admin/ingredient-imports/{batch_id}/activate` or `/reject` — explicit batch activation or rejection.
- `GET /api/v1/admin/audit-events` — paginated editorial action history.

## Data and licensing boundary

No external ingredient records, aliases, or evidence have been imported or seeded. This is deliberate: no specific dataset has been approved, and the project must not invent ingredient evidence, citations, or license terms. The current registry captures the facts an operator must review before importing. An internal approval flag is not legal advice or proof that a source's terms permit every future use; obtain appropriate license/legal review before adding real data. Test fixtures use reserved example URLs and synthetic non-factual text only.

The new evidence table is provenance infrastructure, not a medical evidence grading system. No warnings, safety classifications, ingredient compatibility claims, or product-analysis results are produced by Milestone 4.

## Verification performed

- `pytest -q` from a Python 3.11 development-lock environment: **44 passed**.
- `ruff check backend scripts`: **passed**.
- `ruff format --check backend scripts`: **passed**.
- `uv pip check`: all **42** packages in the fresh development-lock environment and all **33** in the fresh runtime-lock environment are compatible; runtime FastAPI/SQLAlchemy imports passed.
- Migration integration coverage upgrades to `0003_ingredient_evidence`, downgrades to `0002_auth_profiles`, and then to `0001_schema_baseline`, checking the expected tables at each step. The local database reports `0003_ingredient_evidence (head)` via `alembic current`.
- Integration tests cover non-admin denial and role self-promotion denial, rights approval and excerpt gating, duplicate/incomplete import rejection, row-level approve/reject, explicit activation, source-rights revocation, audit records, exact matches, unresolved typos, locale filtering, and ambiguous alias handling.

The API was restarted on port 8000 after migration; `/health/live`, `/health/ready`, `/openapi.json`, and `POST /api/v1/ingredients/resolve` returned HTTP 200. With the intentionally empty seed manifest, the resolver correctly returned `unresolved` for an unseeded term. Windows CI, Docker, PostgreSQL, and SMTP are not part of this milestone's verified environment.

## Limitations and next steps

- The production catalog is empty until a specific source and reuse terms are reviewed and approved; do not treat synthetic tests as ingredient data.
- Source metadata and excerpt permissions are admin-managed controls, not a substitute for legal review, subject-matter review, or source-specific attribution obligations. A rights-status change blocks public lookup and future activation, but does not automatically purge historical import payloads; honor any source-specific deletion/retention requirement manually until a dedicated purge workflow is implemented.
- No ingredient safety rules, OCR, scan processing, Qdrant/RAG, provider calls, frontend, or product analysis are implemented yet.
- PostgreSQL-specific and Windows behavior have not been exercised; SQLite migration and Linux test success do not establish production readiness.

**Follow-on status:** Milestone 5 has implemented authenticated image upload, private storage, persisted OCR state, and correction/confirmation APIs. Live Tesseract verification, an evaluation corpus, and ground-truth OCR metrics remain pending; see `docs/MILESTONE_5.md`.
