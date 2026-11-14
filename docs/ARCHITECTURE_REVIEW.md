# AI Skincare Ingredient Checker
## Product, Feasibility & Architecture Review

**Status:** Architecture approved; Milestones 1–9 are locally implemented through the M7 owner-private backend, initial same-origin responsive frontend, and QA/security hardening. M10 adds a documented single-host Compose deployment scaffold plus encrypted backup/restore helpers; M11 adds release-gate automation and local accessibility checks. M6/M7 tests use synthetic fixtures and mocked provider calls; the production source/evidence/rule corpus remains empty. The owner selected no public source-code license and approved an encrypted off-host daily backup baseline (30-day retention, 24-hour RPO, 4-hour RTO, quarterly drills). Docker/PostgreSQL/hosted CI, live OCR/retrieval/providers, rights-cleared evaluation corpus/reviewer approval, formal accessibility/usability review, comparison/routine APIs, CVE remediation, selected/configured backup destination, target-host scheduling/alerting, restore-drill evidence, and production SMTP remain pending. Current full backend suite: 81 passed; Ruff, Node checks, dependency consistency, SQLite migration checks, M10 YAML/static assertions, and shell syntax checks passed.  
**Prepared:** 9 November 2026  
**Brand:** *Clarity Checker*  
**Product descriptor:** *AI Skincare Ingredient Checker*  
**Development target:** Windows 10/11, VS Code, Python 3.11, HTML/CSS/vanilla JavaScript; local Ollama plus OpenAI and Groq provider options.

**Approved decisions:** retain uploaded label photos until the user deletes them; offer Ollama, OpenAI, and Groq; require current, provider-specific account consent for cloud explanations; send only one confirmed ingredient, its deterministic finding, and currently approved evidence summaries/permitted excerpts. Do **not** send source URLs, raw images, email addresses, other scan ingredients, the full scan, or profile/skin data to cloud providers.

> This file is the approved design baseline, not a claim that the complete product is implemented or production-ready. Milestone-specific implementation and verification results are recorded in `docs/MILESTONE_2.md` through `docs/MILESTONE_7.md`; M6 uses synthetic-only evidence fixtures and M7 uses mocked provider calls. No OCR accuracy, ingredient accuracy, retrieval-quality, citation-support, explanation-quality, or safety results have been fabricated.

---

## Executive recommendation

**Recommendation: proceed, with a deliberately cautious first release.** The requested application is technically feasible with the selected stack. The hard parts are not the dashboard or CRUD APIs: they are label-reading accuracy, ingredient-name ambiguity, defensible evidence and rules, source licensing, and privacy around user-declared sensitivities. Those must be addressed through manual confirmation, traceable evidence, data minimization, evaluation, and expert review—not by asking an LLM to decide whether a product is safe.

The recommended product is an **educational ingredient-reference and review tool**. It should report exact matches, declared-user-preference matches, and narrowly defined source-backed concerns. It must not issue a universal product “safety score,” guarantee compatibility, diagnose a skin condition, or treat a missing warning as proof of safety.

### Recommended first-release decisions

1. Keep OCR and ingredient analysis as separate stages. Users review/correct the extracted list **before** analysis.
2. Use deterministic, versioned rules for warnings. RAG supplies source context; the LLM may explain approved results but cannot create or suppress warnings.
3. Keep all displayed citations server-generated from stored source records. The model never supplies trusted URLs or source IDs.
4. Offer **Ollama, OpenAI, and Groq** through separate provider adapters. An explanation request names one current finding and explicitly selects one provider; OpenAI/Groq require current provider-specific account consent. Send only that confirmed ingredient, the deterministic finding, and currently approved evidence summaries/permitted excerpts. Exclude source URLs, images, email, the full scan, other ingredients, and profile/skin data. Platform API keys stay server-side; users never submit keys in the browser. Never silently switch providers. Ollama runs as a private, operator-controlled endpoint, not through the user’s browser.
5. Use a small, reviewed ingredient/evidence corpus first. Open Beauty Facts is optional product-catalog enrichment—not an ingredient-safety authority.
6. Retain uploaded label photos privately until the user deletes the scan/account. Make retention visible, provide per-scan and account deletion, and exclude images from cloud requests.
7. Use an in-process worker for simple Windows development and Celery/Redis workers in Linux containers for production-like deployment. Celery does not officially support Windows workers, so do not make a native Windows Celery worker part of the required setup ([Celery FAQ](https://docs.celeryq.dev/en/stable/faq.html)).
8. Use “Clarity Checker” as the brand with “AI Skincare Ingredient Checker” as the descriptor. Treat any evidence-grade badge shown in the supplied image as design inspiration only; do not ship a letter grade or overall safety meter until a transparent, reviewed grading rubric exists.

---

# 1. Final Product Requirements Document

## 1.1 Product statement

Help people understand the ingredient lists printed on cosmetic products by turning a label photo or typed list into a **user-confirmed, normalized ingredient list**, then showing source-linked educational information and matches against preferences the user has explicitly declared.

The product communicates **what is known, what is uncertain, and where the information came from**. It does not diagnose, prescribe, or determine that a product is safe for a particular person.

## 1.2 Target users and jobs to be done

- **General skincare consumers:** “Help me read this ingredient label and explain unfamiliar names.”
- **Users with declared sensitivities:** “Tell me when a confirmed ingredient matches an ingredient or term I have saved.”
- **Skincare enthusiasts/researchers:** “Let me inspect evidence and compare ingredient lists.”
- **Product reviewers:** “Let me organize transparent, source-linked observations without unsupported claims.”

User-provided allergies/sensitivities are stored as **user-reported preferences**, not clinically verified facts. The service must not infer a diagnosis, allergy, skin type, or health status from an image.

## 1.3 MVP scope

### In scope

- Account creation, login/logout, email-verification and password-reset workflows through a configurable email-provider interface.
- Profile with optional skin type, user-declared ingredient terms, sensitivities, concerns, and preferences.
- JPEG, PNG, and WebP label uploads with server-side validation, preprocessing, OCR, confidence metadata, and a manual correction step.
- Ingredient normalization using a versioned, curated INCI/common-name/synonym catalog. Ambiguous fuzzy matches are suggestions, not automatic confirmations.
- Evidence records with source title, URL, publisher, publication/retrieval date, scope, attribution/license metadata, and an internal version/checksum.
- A rule engine for exact declared-ingredient matches and a small, reviewed set of source-backed notices. Every finding has a rule/version and evidence relationship.
- Optional RAG retrieval from a curated corpus; M7 implements on-demand Ollama, OpenAI, and Groq explanation adapters with bounded structured output and deterministic fallback text. Cloud requests require current provider-specific consent and are scoped to one confirmed ingredient, one current deterministic finding, and currently approved evidence summaries/permitted excerpts—not source URLs, raw images, email, other scan ingredients, the full scan, or profile/skin data. Generated explanations are not stored.
- User-scoped scan history, ingredient details, comparison of 2–4 products/lists, editable AM/PM routines, and dashboard summaries.
- Account export and deletion; data-retention controls; privacy and terms pages; accessible responsive interface.
- Admin-only, audited workflows for importing/updating sources and activating reviewed rule versions.

### Deferred until separately approved/evaluated

- An overall product safety score, “safe/unsafe” verdict, or evidence letter grade.
- Automated diagnosis, treatment recommendations, or image-based skin-condition analysis.
- Automatic treatment of fuzzy OCR/ingredient matches as verified.
- Recommendations that a user should start/stop a treatment or combine products.
- Full barcode catalog coverage, subscription billing, social sharing of private scan results, or a broad public product marketplace.
- Sending raw label images, email addresses, or full skin-profile/sensitivity data to a third party; cloud multimodal OCR/vision is not included. Cloud explanations use only the opted-in one-finding payload: one confirmed ingredient, its deterministic finding, and currently approved evidence summaries/permitted excerpts.
- Claims of clinical validation or regulatory clearance.

## 1.4 Core user journeys

1. **First visit:** landing page → register → verify email → onboarding → optionally create a profile.
2. **Scan:** upload/capture a label → validation/preprocessing → OCR job → show text and uncertain tokens → user corrects and confirms ingredients → analysis job → result with findings, limits, evidence, and source links → optionally save.
3. **Compare:** select two or more saved scans/products → show shared, unique, unresolved, and preference-matching ingredients in separate groups → show only configured rule findings and evidence.
4. **Routine:** add saved products/scans to a morning/evening list → reorder/edit/remove → show configured notices without prescribing a regimen.
5. **Privacy:** export account data → delete individual scan/profile entries or request full account deletion → confirm deletion status and explain any backup-retention window.

## 1.5 Functional requirements

| ID | Requirement | Acceptance condition |
|---|---|---|
| FR-01 | Authentication and account lifecycle | Passwords are Argon2id-hashed; sessions can be revoked; verification/reset tokens are single-use and expire; another user cannot access an account’s objects. |
| FR-02 | Skin profile | Users can edit/delete optional fields and declared ingredient terms; the UI labels these as user-reported. |
| FR-03 | Scan intake | Only configured raster types are accepted; actual image bytes are decoded and checked; size/pixel caps are enforced; original filenames are not used as storage paths. |
| FR-04 | OCR review | OCR text, word/token confidence where available, and uncertain ingredients are visible; user can add, remove, reorder, and correct items before analysis. |
| FR-05 | Normalization | Each confirmed term maps to a canonical ingredient ID or stays unresolved; original spelling and match method/confidence are retained for audit/debugging. |
| FR-06 | Rule analysis | Findings are deterministic, versioned, bounded to configured rules, and traceable to source records. No finding is not represented as “safe.” |
| FR-07 | Explanations and RAG | An explicit request may explain one current deterministic finding using current approved evidence; validated model text is supplemental and cannot change findings or citations. Citations remain generated/validated by the server. OpenAI/Groq require current provider-specific consent; send only the one confirmed ingredient, finding details, and approved evidence summaries/permitted excerpts. Failure uses deterministic text without switching providers. |
| FR-08 | Product comparison | A comparison clearly separates overlap, unique ingredients, unresolved items, declared matches, and rule findings. |
| FR-09 | Routine planner | The user can create/edit/reorder/delete routine steps; checks are notices, not automatic prescriptions. |
| FR-10 | Dashboard/history | Users see only their own scans, saved products, comparisons, routines, and profile. |
| FR-11 | Privacy operations | A user can export and delete account data; deletion includes relational records, stored objects, queued work, and vector payloads if any user data was ever indexed. |
| FR-12 | Editorial/admin controls | Source and rule changes are permission-controlled, versioned, reviewed, attributable, and auditable. |
| FR-13 | Disclaimers | Scan and result pages state educational scope, uncertainty, and that absence of a warning is not proof of safety. |

## 1.6 Non-functional requirements

- **Security:** least privilege, per-user authorization, secure cookies, CSRF protection, upload restrictions, rate limits, safe error responses, secret management, and privacy-aware logs.
- **Privacy:** retain label images privately until user deletion; provide clear per-scan/account deletion. OpenAI/Groq explanations require current provider-specific consent and send only one finding's confirmed ingredient, deterministic details, and current approved evidence summaries/permitted excerpts. Never send source URLs, raw images, email, the rest of the scan, or profile/skin data to cloud providers.
- **Accessibility:** target WCAG 2.2 AA, including keyboard access, visible focus, labels, contrast, status announcements, and understandable errors ([W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/)).
- **Maintainability:** typed, modular Python; separate route/service/repository/provider layers; migrations; pinned, tested dependencies; documentation synchronized with implementation.
- **Reliability:** scans are jobs with persisted status; retryable operations are idempotent; a model/provider outage does not prevent rule results or saved history from working.
- **Performance:** scanning is asynchronous and reports status; endpoint/worker p50/p95 latency is measured on declared hardware. Do not publish a production SLA until it is benchmarked.
- **Explainability:** every warning has a rule ID/version and at least one validated evidence reference; unknown or low-confidence inputs remain visibly unknown.

## 1.7 Product metrics

Measure, do not assume: scan completion rate; manual correction rate; unknown-ingredient rate; OCR character error rate; ingredient-level extraction precision/recall; canonical-match accuracy and unresolved rate; declared-match precision/recall; per-rule false-positive/false-negative rate; citation validity and semantic support rate; scan queue time; OCR/RAG/LLM latency; job failure/retry rate; account export/deletion completion.

A 30-label set is a useful initial benchmark, not enough evidence to claim broad accuracy across brands, languages, label layouts, and image conditions. Expand and stratify the corpus before making generalized performance claims.

---

# 2. Technical Feasibility Report

## 2.1 Feasibility summary

| Area | Assessment | Main condition / decision |
|---|---|---|
| FastAPI SaaS foundation | **High** | Python 3.11 is supported by current FastAPI documentation; use the current stable release and verify the full dependency set in CI before pinning. ([FastAPI release notes](https://fastapi.tiangolo.com/release-notes/)) |
| SQL database and migrations | **High** | SQLAlchemy 2.x/2.1 + Alembic are suitable. Current SQLAlchemy 2.1 docs target Python 3.11+ and Alembic docs list Python 3.10+; exact package pins must be resolved and tested together. ([SQLAlchemy](https://docs.sqlalchemy.org/en/21/intro.html), [Alembic](https://alembic.sqlalchemy.org/en/latest/front.html)) |
| SQLite local / PostgreSQL production | **High with test work** | Use portable SQLAlchemy models. Run migrations and integration tests against both engines to catch dialect differences; PostgreSQL is the release target. |
| Authentication | **High** | Argon2id, opaque server-side sessions, one-time hashed reset/verification tokens, and email-provider adapter. A real transactional email service is still required before public email verification/reset works. OWASP recommends Argon2id for password storage. ([OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)) |
| Label OCR | **Medium / evaluation-gated** | Start with a replaceable OCR adapter and Tesseract baseline; test PaddleOCR as a challenger against real cosmetic labels. Curved packaging, glare, small type, languages, and ingredient punctuation make extraction accuracy uncertain. Keep correction mandatory. Tesseract documents Windows and Linux installation paths. ([Tesseract installation](https://tesseract-ocr.github.io/tessdoc/Installation.html)) |
| Ingredient normalization | **Medium** | Straightforward for reviewed aliases and exact names; inherently risky for ambiguous or chemically distinct similar names. Unknowns and uncertain fuzzy matches must remain unresolved. |
| Rules and evidence | **Medium / domain-review gated** | Technically straightforward; defensibility depends on narrow rule scope, source quality, current citations, and qualified review. Do not infer general safety from ingredient presence/absence. |
| RAG | **Medium** | Feasible with curated, versioned evidence and metadata-filtered retrieval. Semantic similarity is not proof; structured rules—not RAG—decide warnings. Use Qdrant as the vector store and an explicit in-house retrieval pipeline rather than adding LangChain at the outset. Qdrant documents persistent local mode and self-hosted deployment. ([Qdrant quickstart](https://python-client.qdrant.tech/quickstart.html)) |
| LLM providers | **Medium / live-verification gated** | M7 implements Ollama, OpenAI, and Groq structured chat adapters, strict response validation, and deterministic fallback. Unit/integration transports are mocked; live model compatibility, provider privacy/retention terms, latency, cost, and explanation quality remain unverified. ([Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [Ollama embeddings](https://docs.ollama.com/capabilities/embeddings)) |
| Asynchronous processing | **High with OS constraint** | Production-like queue: Celery + Redis in Linux containers. Celery’s FAQ says Windows is not supported; local native Windows mode should use an in-process development worker, not Celery. ([Celery Windows FAQ](https://docs.celeryq.dev/en/stable/faq.html), [Celery task queues](https://docs.celeryq.dev/en/latest/getting-started/introduction.html)) |
| Open Beauty Facts | **Conditional** | Optional catalog enrichment only. Capture attribution/license/source metadata and validate imported labels manually. The official data page lists ODbL for the database, Database Contents License for contents, and CC BY-SA for product images; obtain legal review before commercial caching/redistribution. ([Open Beauty Facts data/API](https://world.openbeautyfacts.org/data)) |
| Responsive vanilla-JS frontend | **High** | Serve same-origin static files from FastAPI/reverse proxy; use relative API URLs, accessible components, and custom CSS. No frontend framework is needed for the stated MVP. |
| Production SaaS / billing | **Medium** | Multi-user data isolation is feasible now. Subscription billing, service-level objectives, support operations, and regional regulatory/privacy review are separate release decisions—not assumed solved by Docker. |

## 2.2 Selected implementation stack

- **Runtime/API:** Python 3.11, FastAPI, Pydantic, `pydantic-settings`, SQLAlchemy 2.x, Alembic, Uvicorn.
- **Relational data:** SQLite for simple local development/unit tests; PostgreSQL for integration, staging, and production.
- **Vector retrieval:** Qdrant. Local persistent mode may be used for a single-process developer setup; use Qdrant server/container in integration and production.
- **Jobs:** a development-only in-process worker; Celery + Redis in Linux container environments. Job state remains in the relational database.
- **OCR/image:** Pillow for safe decode/resize/re-encode; Tesseract as the initial OCR provider; preprocessing behind an interface. Benchmark PaddleOCR before choosing whether it replaces or supplements Tesseract.
- **AI:** M6 uses Ollama embeddings for retrieval; M7 adds optional chat explanations through Ollama, OpenAI, and Groq. OpenAI/Groq require current provider-specific consent. The minimized payload contains one confirmed ingredient, one current finding, and currently approved evidence summaries/permitted excerpts; never send source URLs, raw images, email, other scan ingredients/full scan, or profile/skin data. The requested provider never silently changes.
- **RAG:** custom, testable retrieval pipeline; explicit chunking, metadata filters, Qdrant, citations from database records. No free-form LLM citation generation.
- **Frontend:** semantic HTML, custom CSS, vanilla ES modules, Fetch API; same-origin deployment; no required frontend build step.
- **Tests/tooling:** Pytest, `httpx2` for the current Starlette TestClient path, Ruff, and integration tests against PostgreSQL/Qdrant/Redis in later milestones. Unit tests do not require a live LLM.
- **Deployment:** Dockerfile and Compose profiles; HTTPS terminates at a production reverse proxy/load balancer; private object storage for label photos retained until user deletion; per-user authorization, deletion lifecycle, and backup-retention policy required. OpenAI/Groq credentials stay backend-side and are never exposed to frontend JavaScript.

### Dependency pinning and verification status

Milestone 2 selected and pinned direct dependencies in `backend/requirements.txt` and `backend/requirements-dev.txt`, with `backend/requirements-lock.txt` for development/test and `backend/requirements-runtime-lock.txt` for runtime. Milestones 2–6 use universal Python 3.11 resolutions. Milestone 5 adds `Pillow==13.0.0` and `python-multipart==0.0.33`; M6 adds `qdrant-client==1.20.0`. M7 adds no dependency. The development/runtime locks were regenerated at M6 and both environments passed `pip check`. M6's full local suite passed 67 tests; M7's full backend suite passed 76 tests, with Ruff format/lint checks passing. The local SQLite database remains at `0005_rules_rag_analysis`; M7 adds no migration. Synthetic OCR behavior is tested, but the sandbox has no Tesseract executable. M6 exercises in-memory Qdrant and a mocked Ollama response; M7 provider transports are mocked. Live OCR/retrieval/provider behavior, evidence/explanation quality, and production corpus behavior are not claimed. Windows CI and Docker image-build jobs are configured but have not run; PostgreSQL and SMTP remain unverified. Update pins only after reviewing compatibility and passing the test matrix.

---

# 3. System Architecture

## 3.1 Logical components

```text
Browser: HTML/CSS/Vanilla JS
        │ same-origin HTTPS; HttpOnly session cookie + CSRF token
        ▼
FastAPI application
  ├─ API routes / schemas / authorization
  ├─ Auth + profile + privacy operations
  ├─ Scan orchestration + persisted job status
  ├─ Ingredient catalog + normalization service
  ├─ Deterministic rule engine ───────────────┐
  ├─ Evidence/RAG retrieval service            │ approved findings only
  └─ On-demand LLM explanation adapters (optional)│
        │                 │                    │
        ▼                 ▼                    ▼
PostgreSQL / SQLite   Qdrant vector store   Source/evidence records
        │
        ├── Redis broker → Celery worker (Linux deployment profile)
        ├── private object storage (label photos retained until user deletion)
        ├── Ollama / OpenAI / Groq providers (cloud account opt-in; text-only payload)
        └── email provider (verification/reset; Mailpit in local Compose)
```

The browser never calls `localhost` to reach a backend. It calls relative `/api/v1/...` URLs. In development, FastAPI can serve the static frontend from the same origin. In production, a reverse proxy can serve the frontend and forward `/api` to FastAPI under the same origin.

## 3.2 Deployment modes

**Windows developer mode:** run FastAPI, Tesseract, and Ollama natively; SQLite for relational development; a single-process local job runner; Qdrant local persistent mode or the optional Qdrant container. This is convenient, but not a production topology.

**Integration/production-like mode:** Linux Docker containers for FastAPI, Celery worker, PostgreSQL, Redis, and Qdrant; Ollama is configured as a private service or host endpoint; OpenAI/Groq are called only by the backend after current, provider-specific account consent. A local mail-capture service can exercise verification/reset flows. Use the same Compose service names/configuration for reproducible tests.

**Production:** stateless API replicas, separate worker replicas, managed PostgreSQL/Redis/Qdrant or secured self-hosted equivalents, private object storage with user-controlled deletion, a transactional email provider, HTTPS, secrets manager, backups, monitoring, and source/rule review operations. Keep Qdrant payloads limited to public evidence identifiers/text—never put user skin profiles or private scans into the knowledge index. Provider API keys remain server-side; enforce consent, per-user quotas, cost monitoring, and no silent fallback.

## 3.3 Scan and analysis lifecycle

1. Authenticated user posts one multipart image. API checks CSRF, ownership/session, per-user/IP rate limits, complete request bytes, actual file format, byte and pixel limits. Pillow decodes, orientation-corrects, re-encodes to metadata-free JPEG, and stores it under a server-generated opaque key in a private per-user directory. Client filenames are not stored or used as paths. The photo remains until scan/account deletion and is never sent to OpenAI/Groq.
2. API persists a `scan` row in `queued` state and returns `202 Accepted`. M5 uses FastAPI `BackgroundTasks` as a simple local in-process runner; it is non-durable across process restarts and will be replaced/reconciled by the deployment queue.
3. The replaceable local Tesseract adapter reads the sanitized JPEG via stdin and parses TSV text, word confidence, and boxes where available. Missing executable/language data, timeout, and OCR errors are persisted as safe status/error codes; no cloud OCR fallback is used.
4. OCR text is untrusted. The correction draft starts empty, and users provide/edit/reorder the ingredient list through the API. Only the explicit confirmation endpoint marks entries confirmed; analysis rejects unconfirmed or not-yet-confirmed scans.
5. M6 resolves each confirmed entry using the exact catalog resolver. Ambiguous and unresolved terms stay without a canonical ID and never trigger a rule. Immutable versioned ingredient-presence rules match only canonical IDs and require separately approved evidence mappings.
6. Optional RAG embeds reviewed evidence summaries and filters Qdrant by exact ingredient ID plus evidence IDs from current approved SQL mappings and approval metadata. Vector hits provide candidate ranks only. Retrieval failure does not make or suppress a deterministic finding; no scan, profile, image, email, or excerpt is placed in the index.
7. The API validates and serializes citations from SQL-backed evidence/source records, rechecking rule state, catalog identity, source rights, and excerpt permissions. If relevant rules, ingredient resolution, or source rights have changed since the run, the analysis becomes stale and current findings are withheld. Empty/no-active-rule results explicitly state they are not proof or an assessment of safety.
8. After a current analysis, M7 optionally explains one selected finding on explicit request. The caller selects Ollama, OpenAI, or Groq; cloud requests require current provider-specific consent. Only that confirmed ingredient, its current deterministic finding, and currently approved evidence summaries/permitted excerpts may be sent. Source URLs, images, email, other scan ingredients, full scans, and profile/skin data are excluded. Output is schema-validated, ephemeral, and cannot change findings or citations; provider failures return the reviewed rule message without switching providers.
9. The sanitized retained JPEG remains in private storage until scan/account deletion. Authenticated photo retrieval, per-scan deletion, and account export are implemented; account export includes analysis history and scan deletion cascades analysis records. Backup-retention limits still need deployment documentation. M5's BackgroundTasks runner remains local and non-durable; production queue integration/recovery is future work.

## 3.4 Core trust boundaries

- Browser input, OCR text, product labels, imported sources, and model output are **untrusted**.
- API is the authorization boundary; every read/write query for user-owned objects is scoped by authenticated user ID.
- Admin source ingestion is separate from user scans and has allowlisted sources, licensing metadata, review, and audit records.
- The model has no tool permissions and cannot change rules, retrieve arbitrary URLs, select its own citations, or override deterministic output.
- Vector retrieval supplies candidate evidence identifiers/ranks only; reviewed summary embeddings never authorize a finding, and citation text/provenance come from SQL. It is not the rule engine or source of ingredient identity.

---

# 4. Database Schema Proposal

Use UUID primary keys, UTC timestamps, explicit foreign keys, unique constraints, and indexes on ownership/status/lookup fields. Keep model/database types portable where practical; test Alembic migrations on SQLite and PostgreSQL.

## 4.1 Main entities

| Table | Purpose / important fields |
|---|---|
| `users` | `id`, normalized unique `email`, `password_hash`, `role`, active/verified timestamps, created/updated timestamps. No password, reset token, or API secret in logs. |
| `auth_sessions` | `id`, `user_id`, hash of opaque session secret, created/expiry/revoked/last-seen timestamps. Store only the hash, not the browser token. |
| `one_time_tokens` | Hashed email-verification/password-reset token, purpose, expiry, used timestamp, user FK. Tokens are single-use and never stored in plaintext. |
| `user_profiles` | One-to-one with user; optional skin-type/preferences/locale fields; marked user-reported; no image-derived medical fields. |
| `user_declared_ingredients` | `user_id`, original user-entered term, optional canonical ingredient FK, match status, created/updated. Unresolved terms remain text and do not become verified allergies. |
| `ingredients` | M4 reviewed preferred name, normalized exact-match key, name kind, active/retired status, dataset version, source FK/locator, and timestamps. No safety or medical claim fields are seeded. Taxonomy and additional descriptors await reviewed sources. |
| `ingredient_aliases` | Ingredient/source FKs, display and normalized alias, locale, alias type, locator, and active/retired status. Duplicate normalized aliases across different ingredients are permitted so resolution can return `ambiguous` rather than guess. |
| `evidence_sources` | Publisher, title, canonical URL, source type, license/attribution, retrieval/version/checksum metadata, rights status, reviewer/note, and explicit excerpt-reuse permission. Rights start pending; rights changes can hide catalog content. |
| `ingredient_evidence_records` | Ingredient/source FKs, evidence kind, reviewed summary, scope/locator, optional excerpt, review status/note/actor. Public detail includes only approved records from currently approved sources; this is not a safety rules engine. |
| `ingredient_import_batches` / `ingredient_import_rows` | Source/version/content digest, immutable submitted row payloads, pending/approved/rejected decisions, reviewer notes, and explicit batch activation status. No import activates on submission. |
| `admin_audit_events` | Actor, action, object type/ID, timestamp, request ID, and allowlisted metadata for source/import changes. Never store credentials, tokens, or raw user scans.
| `products` | Catalog/user-created product identity, brand/name/barcode where available, source FK, ownership/publication state, timestamps. Open Beauty Facts data retains attribution and license metadata. |
| `product_ingredients` | Product FK, ingredient FK nullable, raw name, order, match status/confidence, source/confirmation. Preserve original label ordering and unresolved entries. |
| `saved_products` | User-owned bookmark/link to a catalog product or user-created product; supports dashboard and routines without duplicating catalog data. |
| `scans` | `user_id`, opaque generated image key, sanitized image dimensions/byte count/content type, scan and OCR statuses, raw OCR text, word tokens/confidence/boxes where available, engine/version where available, safe error code, and timestamps including explicit confirmation. No original client filename as a storage key. |
| `scan_ingredients` | Scan FK, editable user-provided/corrected text, order, and user-confirmed flag. M5 starts this draft empty and does not infer ingredient boundaries from raw OCR; only the explicit confirmation endpoint marks entries confirmed. |
| `scan_analyses` | Scan FK, requesting user, status, deterministic engine/resolver versions, rule-version/config snapshot, retrieval status, and creation time. M7 explanation output is ephemeral and is not persisted. |
| `analysis_ingredients` | Analysis and scan-item FKs, input/normalized text, exact resolution status/method, optional canonical ID/name, and candidate snapshot. Ambiguous/unresolved terms remain without a canonical ID. |
| `rule_versions` | Stable rule key/version, strict `ingredient_presence` type, structured canonical-ID condition, title/message/severity, lifecycle state, reviewer and activation/retirement metadata. Conditions are validated data; never evaluate arbitrary code. |
| `rule_evidence_mappings` | Many-to-many link between a rule version and an approved evidence record, with an independent review status, reviewer, note, and timestamps. Activation requires current target/source/evidence approval. |
| `analysis_findings` | Analysis, rule-version, scan-item, and canonical ingredient references plus immutable title/message/severity snapshots. Findings are deterministic and versioned. |
| `analysis_finding_evidence` | Finding-to-reviewed-mapping relationship plus optional Qdrant retrieval rank. Citation content/provenance is reloaded and rights-checked from SQL at read time. |
| `product_comparisons` / `comparison_items` | User FK, timestamp, ordered references to scans/products, result version. Authorization verifies ownership of every referenced item. |
| `routines` / `routine_items` | User FK, name/time-of-day; ordered items reference a saved product or scan, with a constraint that exactly one target is present. Fully editable. |
| `ai_provider_consents` | User FK, provider (OpenAI or Groq), disclosure/version, granted/revoked timestamps, and current status. Consent is provider-specific, revocable, and required before a cloud explanation; M7 requires the active disclosure version (`clarity-cloud-consent-v2`). |
| `audit_events` | Actor, action, object type/ID, timestamp, request ID, allowlisted metadata. Do not log passwords, tokens, full OCR text, image bytes, or model prompts containing sensitive profile data. |
| `usage_events` | User, operation, units, timestamp/idempotency key for fair-use limits and monitoring; no billing/payment data in MVP. |

## 4.2 Relationships and integrity rules

```text
User 1─1 Profile; User 1─* Sessions, DeclaredIngredients, Scans, Routines, Comparisons
Ingredient 1─* Aliases; Product *─* Ingredient through ProductIngredients
Scan 1─* ScanIngredients; Scan 1─* ScanAnalyses; ScanAnalysis 1─* AnalysisIngredients, Findings
EvidenceSource 1─* IngredientEvidenceRecords; RuleVersion *─* EvidenceRecord through RuleEvidenceMappings
Finding *─* RuleEvidenceMappings through AnalysisFindingEvidence
Routine 1─* RoutineItems → exactly one saved product or scan per item
```

Every user-owned table has an ownership path that can be checked on every request. Deleting a user must revoke sessions, cancel/ignore queued work, remove owned database records and private objects, remove any user-derived vector payloads, and record only the minimum non-sensitive deletion audit event. Public evidence/index records are not user-owned and should not contain user scans.

---

# 5. API Architecture

## 5.1 API conventions

- Base prefix: `/api/v1`; JSON request/response schemas validated by Pydantic.
- Same-origin browser requests; strict CORS allowlist only if a later deployment genuinely needs cross-origin access.
- Consistent error envelope with stable error code, safe message, request ID, and optional field errors. No stack traces or secrets.
- Authenticated routes require a server-side session cookie. State-changing cookie-authenticated calls require CSRF protection and Origin checks.
- Paginate history and apply per-user/rate/usage limits. OpenAPI/Swagger is enabled in development; restrict or disable it in production unless intentionally exposed.

Example response envelope:

```json
{
  "data": { "id": "<scan-id>", "status": "queued" },
  "error": null,
  "meta": { "request_id": "<request-id>" }
}
```

A validation error has `data: null` and an `error` object with a stable code and safe explanation. IDs in these examples are illustrative, not real records.

## 5.2 Proposed routes

### Health

- `GET /health/live` — process liveness.
- `GET /health/ready` — readiness including configured critical dependencies, without returning secrets.

### Authentication and account

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login` (sets session cookie)
- `POST /api/v1/auth/logout` (revokes session)
- `GET /api/v1/auth/csrf`
- `POST /api/v1/auth/verify-email`
- `POST /api/v1/auth/password-reset/request`
- `POST /api/v1/auth/password-reset/confirm`
- `GET /api/v1/users/me`; `PATCH /api/v1/users/me`
- `GET/PATCH /api/v1/users/me/profile`
- `GET/PATCH /api/v1/users/me/ai-settings` — provider preference/status only; never accepts provider API keys.
- `GET /api/v1/users/me/ai-consents` — current disclosure text/version and OpenAI/Groq consent status.
- `POST /api/v1/users/me/ai-consents/{provider}` and `DELETE /api/v1/users/me/ai-consents/{provider}` — versioned, provider-specific opt-in/revocation for OpenAI or Groq.
- `GET/POST/DELETE /api/v1/users/me/declared-ingredients`
- `POST /api/v1/privacy/export`; `DELETE /api/v1/users/me`

### Scanning and analysis

- `POST /api/v1/scans` — multipart image upload; returns `202 Accepted` and scan ID/status.
- `GET /api/v1/scans` — paginated current-user history.
- `GET /api/v1/scans/{scan_id}` — OCR/job status and user-confirmable draft.
- `PATCH /api/v1/scans/{scan_id}/ingredients` — replace/correct/reorder the unconfirmed draft.
- `POST /api/v1/scans/{scan_id}/confirm` — explicit affirmative confirmation required before analysis.
- `POST/GET /api/v1/scans/{scan_id}/analysis` — run/retrieve owner-scoped deterministic analysis; requires a confirmed scan and revalidates current citations/rights. Stale history withholds findings until rerun.
- `POST /api/v1/scans/{scan_id}/analysis/findings/{finding_id}/explanation` — explicitly request ephemeral supplemental prose for one current finding from the caller-selected Ollama/OpenAI/Groq provider; cloud consent required, no model citations, deterministic fallback, and no silent provider switch.
- `GET /api/v1/scans/{scan_id}/photo` — authenticated photo retrieval for its owner.
- `DELETE /api/v1/scans/{scan_id}` — delete scan/history, cascading analysis, and associated private image data.
- `GET /api/v1/ingredients/{ingredient_id}` — canonical detail and source links.

### Products, comparisons, routines

- `GET/POST /api/v1/products` — search/select or create a user product.
- `POST /api/v1/products/compare` — compare 2–4 user-authorized product/scan references.
- `GET/POST /api/v1/routines`
- `GET/PATCH/DELETE /api/v1/routines/{routine_id}`

### Admin (restricted)

- `/api/v1/admin/sources` and `/api/v1/admin/ingredient-imports` for source/license review and staged catalog import.
- `/api/v1/admin/rule-versions` for draft/version creation, separate mapping review, rule review, activation, and retirement; `/api/v1/admin/evidence/{evidence_record_id}/index` explicitly indexes a current approved summary. Admin changes are authenticated, role-checked, and audited. No public endpoint lets an LLM or user activate a rule.

## 5.3 Error and job states

Expected safe error codes include `invalid_image`, `unsupported_image`, `image_too_large`, `ocr_unavailable`, `scan_not_ready`, `scan_not_confirmed`, `analysis_not_found`, `rag_not_configured`, `evidence_index_unavailable`, `not_found`, `forbidden`, `rate_limited`, `email_delivery_unavailable`, and `internal_error`.

Implemented scan states are `queued`, `extracting`, `needs_confirmation`, `confirmed`, and `failed`; OCR has separate `queued`, `running`, `succeeded`, `unavailable`, and `failed` states. Analysis responses report `completed`, `no_active_rules`, `needs_review`, or `stale`, and retrieval reports `not_run`, `not_configured`, `empty`, `retrieved`, or `unavailable`. Every analysis read/write is scoped to the owning user. Analysis history is append-only per request; scan deletion cascades it.

---

# 6. Security and Privacy Threat Assessment

## 6.1 Assets and threat actors

**Assets:** credentials/session secrets, emails, user-declared sensitivity data, OCR text/scan history, retained label images, private routines, source/rule editorial controls, provider/API secrets, and service availability. **Threat actors:** anonymous attackers, credential-stuffing bots, malicious users uploading crafted files, compromised dependencies, unauthorized insiders, and prompt-injection content embedded in labels or imported documents.

## 6.2 Threats and controls

| Threat | Risk | Required controls |
|---|---|---|
| Credential theft, brute force, session fixation | Account takeover | Argon2id; breached/weak-password policy as appropriate; login/reset rate limits; generic auth errors; rotate session on login; hashed opaque session tokens; logout/revocation; secure cookie; optional MFA for admins. |
| CSRF / stolen browser credentials | Unauthorized state change | `HttpOnly`, `Secure` in HTTPS, `SameSite=Lax` or stricter cookies; signed double-submit CSRF cookie/header with HMAC validation and Origin checks; never put session tokens in localStorage. OWASP treats SameSite as defense-in-depth, not a substitute for CSRF validation ([OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)). |
| Cross-user IDOR/data leakage | Exposure of scans, routines, or declared sensitivities | Enforce owner-scoped queries in repositories/services; deny-by-default; verify ownership of every nested reference; cross-user API tests; private object storage; optional PostgreSQL row-level security as later defense-in-depth. |
| Malicious/oversized/decompression-bomb uploads | Code execution, resource exhaustion, storage abuse | Allowlist JPEG/PNG/WebP; inspect bytes, not just user MIME/header; cap bytes and pixel count; safe decoder; re-encode and strip metadata; randomized opaque object key; storage outside web root; per-user quotas/rate limits. OWASP explicitly recommends server-side type validation, size limits, generated filenames, and safe image re-encoding ([OWASP upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)). |
| XSS / unsafe OCR or model output | Session abuse or misleading content | Render user/OCR/LLM strings as text, not HTML; strict CSP/security headers; never trust model Markdown/HTML; validate schemas; no inline execution; frontend input validation is not the security boundary. |
| SQL injection / unsafe imports | Data loss or privilege escalation | SQLAlchemy parameterized statements; no string-built SQL from user input; allowlisted ingestion domains and parsers; strict schema validation; migrations reviewed; no arbitrary code in rules. |
| Prompt injection in labels or evidence | Model ignores instructions, fabricates/overstates claims | Treat OCR/document text as untrusted quotations; no model tools or network access; fixed schema; model cannot decide warnings/citations; source IDs/URLs attached by server; reject invalid response; deterministic fallback. |
| Sensitive-data transfer to cloud LLM | User privacy breach | Local Ollama plus OpenAI/Groq options; cloud explanations require current provider-specific consent and clear disclosure; send only one confirmed ingredient, its current deterministic finding, and currently approved evidence summaries/permitted excerpts. Exclude source URLs, raw images, email, other scan ingredients/full scan, and profile/skin data; no silent provider fallback; review provider terms and test outbound payloads. |
| Stale/incorrect evidence or license violation | Misleading warning/legal exposure | Source registry with date/version/license/attribution; reviewed claims; citations on each warning; update/supersede workflow; source-specific license checks; legal review before redistributing datasets/images. |
| DoS / OCR or LLM cost exhaustion | Outage or cost spike | Upload/time limits; job concurrency caps; per-user/IP limits; queue backpressure; timeouts, retry caps, circuit breaker; fair-use quotas; metrics and alerts. |
| Secrets/debug data in logs | Credential or health-data disclosure | Environment/secret manager; `.env` ignored; redact logs; allowlist audit fields; generic client errors; restricted log access/retention; no prompt, password, token, or full image logging. |
| Dependency or container compromise | Supply-chain compromise | Pin/lock dependencies; automated vulnerability checks; minimal base images; non-root containers; SBOM/release inventory; review package licenses; regular rebuilds. |
| Account deletion incomplete | Residual personal data | Deletion workflow covers DB, object storage, queued jobs, caches, and derived data; documented backup expiry; deletion tests; export format documented. |

## 6.3 Authentication decision

For this first-party browser application, prefer **opaque server-side sessions** over putting JWTs in browser storage. Generate a cryptographically random session secret, store only its hash, rotate after login/privilege changes, and revoke server-side on logout. Deliver it only as a secure, HttpOnly, SameSite cookie; protect unsafe calls with an HMAC-signed double-submit CSRF cookie/header pair and Origin validation. This avoids an unnecessary JWT refresh-token system and makes revocation explicit. If a future public/mobile API needs OAuth/JWT, design that separately. Therefore `JWT_SECRET_KEY` is not required for the proposed browser MVP; do not add it just because it appeared in an example environment template.

## 6.4 Privacy and retention defaults

- Retain uploaded label photos in private per-user storage until the user deletes the scan or account. Enforce actual ownership checks, encrypt storage/in transit, expose per-scan and account deletion, and document backup-retention windows. Photos are not sent to cloud LLM providers.
- Keep structured scan text/list, analysis, and evidence references in user history only as needed; users can export/delete them.
- Do not include user-specific profiles, sensitivities, private scans, or images in the public knowledge-base vector index.
- OpenAI/Groq explanations require current provider-specific consent. Send only one confirmed ingredient, that current deterministic finding, and approved evidence summaries/permitted excerpts; never send source URLs, images, email, other scan ingredients/full scan, or profile/skin data. Keep provider credentials server-side and never silently switch providers.
- Avoid user IP retention unless justified for abuse defense; if retained, limit/aggregate and document it.
- Provide export/delete flows and publish retention windows for backups, queued work, logs, and email tokens.
- Obtain jurisdiction-specific privacy, consumer-protection, provider-terms, and regulatory review before public launch. A disclaimer is important but does not replace legal or domain-expert review.

---

# 7. Development Roadmap and Approval Gates

The following sequence preserves the original milestone intent and acceptance gates. The architecture was approved on 9 November 2026; implementation status through M8 is recorded in the milestone documents and at the end of this review.

| Phase | Work | Exit gate |
|---|---|---|
| 0. Architecture approval | Confirm Clarity Checker + descriptor, retained-image policy, Ollama/OpenAI/Groq options, account-level cloud opt-in, text-only cloud payload, data sources, and this revised architecture. | Written approval or change list. |
| 1. Requirements/architecture baseline | Freeze PRD, architecture decision records, threat model, directory skeleton, test plan. | Scope and decisions versioned in docs. |
| 2. Backend foundation | Python environment, settings, logging, FastAPI app, DB abstraction, initial Alembic migration, health endpoints, Docker base, CI. | Clean Windows install; unit/API smoke tests; no secrets in repo. |
| 3. Auth and profiles | Users, Argon2id, sessions, CSRF, verification/reset adapter, profile and declared-term CRUD. | Auth, ownership, session-revocation, and cross-user tests pass. |
| 4. Ingredient/evidence base | Schemas, alias normalization, source/license registry, import pipeline, admin review and seed manifest. | No unlicensed/fabricated evidence; ambiguous mappings remain unresolved. |
| 5. Image and OCR | Upload validation, preprocessing, OCR adapter, job statuses, correction UI/API. | M5 core API/storage/state implemented and tested; evaluation corpus/ground truth plus live OCR metrics remain pending. Manual correction/confirmation API works. |
| 6. Rules and RAG | Versioned rules, separately reviewed evidence mappings, Qdrant/Ollama retrieval filters, owner-private analysis, and citation validation. | **Implemented and locally tested** with synthetic-only fixtures; 67-test backend suite passes, migration `0005_rules_rag_analysis` is current with no Alembic drift. Production source/rule corpus and live retrieval-quality evaluation remain empty/unverified. |
| 7. LLM explanation | Ollama, OpenAI, and Groq adapters; structured schema; provider-specific cloud consent; minimized one-finding payload; timeout/fallback; prompt-injection and provider-isolation tests. | **Implemented and locally tested:** 76 backend tests pass and Ruff passes. Invalid/unavailable model cannot add or alter findings/citations; cloud payload excludes images, email, full scans, profile data, and source URLs. Live providers and explanation quality remain unverified. |
| 8. Frontend modules | Landing, auth, onboarding, dashboard, profile, scanner/results, compare, routines, history/settings/legal pages. | **First pass implemented:** same-origin responsive app with current auth/profile/scan/privacy APIs. Compare/routines are honest placeholders until endpoints exist. Backend suite 78 passed; Ruff/Node syntax checks pass. Formal mobile, keyboard, screen-reader, and usability review remains pending. |
| 9. QA/security hardening | Integration, security, performance, usability, cross-database, evaluation run; fix findings. | **Local QA report delivered:** 81 backend tests pass; Ruff/Node checks, pip consistency, SQLite migration drift, CSP, and local loopback smoke checks are recorded in `docs/MILESTONE_9.md`. Production/release sign-off remains open: PostgreSQL, Docker/Windows CI, real evaluation corpus, live OCR/providers, CVE audit, and formal accessibility/usability review were not available/run. |
| 10. Deployment/docs | Docker Compose, production deployment path, guides, attribution/license, backups/monitoring. | **Scaffold delivered, not signed off:** single-Linux-host Compose/Caddy/PostgreSQL, encrypted backup/restore tooling, deployment/attribution docs, and a launch checklist are added. YAML/shell/static checks pass; Docker build, Compose runtime, PostgreSQL, hosted CI, and restore drill remain unrun. The later owner decisions are no public source-code license and an encrypted daily off-host backup baseline (30-day retention, 24-hour RPO, 4-hour RTO, quarterly drills); destination/scheduler/alerts/restore evidence remain open. |

---

# 8. Proposed Project Directory Structure

```text
ai-skincare-ingredient-checker/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                  # settings, security, errors, logging, rate limits
│   │   ├── api/v1/routes/         # auth, users, scans, ingredients, products, routines
│   │   ├── database/              # engine/session/base and repositories
│   │   ├── models/                # SQLAlchemy entities
│   │   ├── schemas/               # Pydantic request/response schemas
│   │   ├── services/              # business workflows
│   │   │   ├── auth/
│   │   │   ├── ocr/
│   │   │   ├── ingredients/
│   │   │   ├── safety_rules/
│   │   │   ├── evidence/
│   │   │   ├── rag/
│   │   │   ├── llm/
│   │   │   ├── scans/
│   │   │   ├── comparison/
│   │   │   ├── routines/
│   │   │   └── privacy/
│   │   ├── providers/             # OCR, LLM, embedding, email, storage, job adapters
│   │   ├── workers/               # Celery tasks + development runner adapter
│   │   └── utils/
│   ├── migrations/                # Alembic environment and revisions
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── security/
│   │   └── evaluation/             # manifest + licensed/approved test fixtures
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── pages/                      # login, onboarding, dashboard, scan, compare, etc.
│   ├── components/
│   ├── css/
│   ├── js/                         # api, auth, page controllers, shared state
│   └── assets/                     # logo, favicon, embedded/local SVG icons
├── data/
│   ├── seed/                       # reviewed, licensed seed records only
│   ├── knowledge_base/             # source manifest and approved evidence extracts
│   ├── evaluation/                 # test data with rights/attribution metadata
│   └── private/                    # ignored by Git; never commit uploads or credentials
├── scripts/                        # seed, import, evaluation, cleanup, admin bootstrap
├── docs/                           # architecture, guides, security, testing, deployment
├── infra/                          # Dockerfile, Compose profiles, reverse-proxy examples
├── .gitignore
├── docker-compose.yml
├── README.md
└── CHANGELOG.md                   # no LICENSE file: owner selected no public code license
```

`data/private/`, real user images, `.env`, logs, model weights, and local databases must be excluded from Git. The source-code license is separate from the licenses/attribution obligations for imported product data, images, evidence texts, and model weights.

---

# 9. Testing and Quality Strategy

## 9.1 Test layers

- **Unit:** normalization/Unicode/case handling; ambiguous synonyms; OCR output parsing; safe image validation; rule evaluation; evidence selection; citation validation; retention and access policy; settings validation.
- **Integration:** registration/login/logout; verification/reset; SQLAlchemy against SQLite and PostgreSQL; migrations; image-upload pipeline; queue state transitions; Qdrant retrieval filters; routine/comparison persistence; export/deletion.
- **API/authorization:** valid/invalid sessions, CSRF, expired tokens, cross-user object access, pagination, rate limits, consistent error schemas.
- **Security:** unsupported files, spoofed MIME, decompression/pixel limits, path traversal filenames, XSS strings from OCR/LLM, SQL injection payloads, prompt-injection corpus, rate-limit enforcement, secrets/log inspection.
- **Frontend/usability:** responsive layouts; keyboard-only operation; form labels; focus management; screen-reader status announcements; empty/loading/error states; mobile capture/upload; WCAG 2.2 AA review.
- **Provider tests:** mock Ollama/OpenAI/Groq adapters for deterministic CI; optional local Ollama smoke test; verify account opt-in and exact outbound payload; ensure no image/profile/email is sent to cloud; test provider outage, malformed JSON/schema violations, and no silent fallback.
- **Evaluation:** at least 30 real cosmetic labels with manually checked ingredient ground truth, source/permission metadata, varied print quality/layouts, and an explicit train/development/test split where the sample permits. Do not commit copyrighted/third-party images unless redistribution permission/license is documented.

## 9.2 Metrics definitions

- **OCR character error rate:** character edit distance divided by reference character count, reported by image condition/language.
- **Ingredient extraction precision/recall:** ingredient-level set/order-aware comparison against adjudicated ground truth; separately report missing, extra, duplicated, and misordered entries.
- **Normalization accuracy:** exact canonical-ID accuracy on confirmed matches; separately report auto-match coverage and unresolved/ambiguous rate.
- **Warning quality:** per-rule precision, recall, false-positive and false-negative counts against a reviewed expected outcome. Separate user-declared exact/synonym matching from broader concern rules.
- **Citation correctness:** structural validity of source record/URL and human audit that the cited material supports the displayed claim. The API must not display a citation that is absent from its approved source registry.
- **Latency/reliability:** API p50/p95, OCR duration, queue wait, RAG and LLM duration, retry/failure rate, and model-unavailable fallback count.

## 9.3 Reporting policy

`TESTING_REPORT.md` must say **not run** until tests actually run. It must include environment, commit, command, pass/fail counts, measured metrics, limitations, data licenses, and open issues. Do not claim 30 labels were evaluated, quote accuracy, or mark production readiness without measured evidence. Establish numeric release thresholds after the first baseline; a 30-label pilot is too small to support broad population-wide accuracy claims.

---

# 10. Risk Register

| ID | Risk | Likelihood / impact | Mitigation and release gate |
|---|---|---|---|
| R1 | OCR omits, inserts, or alters an ingredient | High / High | Mandatory review before analysis; retain raw OCR separately; confidence/uncertainty UI; benchmark across real labels; no silent correction. |
| R2 | Similar names or aliases map to the wrong chemical | Medium / High | Curated synonym provenance; exact matching first; ambiguous terms unresolved; tests for near-duplicates; human review of catalog changes. |
| R3 | Warning is unsupported, overstated, or misleading | Medium / Critical | Narrow source-backed rules; expert review; evidence links required; clear uncertainty and limitations; no general “unsafe” verdict. |
| R4 | User sensitivity/profile or scan is exposed | Medium / Critical | Owner-scoped access, secure sessions, CSRF, private storage, minimal logs, deletion/export, penetration/security tests. |
| R5 | Imported data/image violates license or attribution | Medium / High | Source-by-source license registry, attribution notices, legal review, do not ingest product images by default, keep source provenance. |
| R6 | LLM hallucinates a warning, citation, or ingredient | High / High | LLM explains only deterministic findings; strict schema; server-generated citations; no tools; fallback templates; adversarial tests. |
| R7 | OCR/vector/LLM dependency is difficult on Windows or incompatible | Medium / Medium | Python 3.11 compatibility check; Linux Docker for production worker; clean Windows install test; adapter boundaries; optional provider smoke tests. |
| R8 | User’s ingredients or images are sent to a cloud provider unexpectedly | Medium / High | Current provider-specific consent for OpenAI/Groq; send only one finding's confirmed ingredient, deterministic details, and currently approved evidence summaries/permitted excerpts. Exclude source URLs, raw images, email, other scan ingredients/full scan, and profile/skin data; no silent provider fallback; test outbound payloads and cost limits. |
| R9 | Single-process developer behavior is mistaken for production resilience | Medium / High | Label local worker as dev-only; production Compose uses queue/worker; test retry/idempotency; deployment docs explain process topology. |
| R10 | Product scope grows faster than evidence quality | High / Medium | Release gates; defer score, recommendations, billing, and vision model; prioritize catalog provenance and evaluation. |
| R11 | Thirty labels do not represent languages/markets or rare layouts | High / Medium | Stratify and expand corpus; publish limitations; no broad accuracy claims; include real-world pilot feedback. |
| R12 | Source becomes stale or changes its conclusion | Medium / High | Version/date every source; scheduled review; supersede and reindex; retain provenance for old scan results. |
| R13 | Deletion does not reach objects, queue, caches, or backups | Medium / High | Central deletion workflow; lifecycle policies; cleanup worker; deletion integration tests; documented backup retention. |
| R14 | Email delivery is unconfigured, breaking verification/reset | Medium / Medium | Provider interface; Mailpit in development; production provider selection/health check is a launch gate. |
| R15 | Marketing/UI implies clinical certainty | Medium / High | Ban “safe,” “toxic,” and disease claims unless reviewed; no overall grade; legal/domain-expert review of copy and target-market obligations. |
| R16 | Retained images accumulate or expose incidental personal information | Medium / High | Private encrypted object storage, opaque keys, quotas, image preview/deletion controls, no cloud transfer, lifecycle monitoring, and clear retention notice; test scan/account deletion and backup expiry. |

---

# Approved Architecture Baseline

Approval was received on 9 November 2026. The following choices are now the implementation baseline:

- **Brand/product naming:** “Clarity Checker” brand; “AI Skincare Ingredient Checker” descriptor.
- **Image retention:** uploaded label photos remain in private per-user storage until the user deletes the scan or account; export and deletion controls include the photo. Backup-retention limits will be disclosed.
- **Providers:** include local Ollama, OpenAI, and Groq as separate options. Keep credentials backend-side; do not silently switch providers.
- **Cloud consent:** OpenAI/Groq explanations require current provider-specific account consent against the displayed disclosure version; M7 uses `clarity-cloud-consent-v2`.
- **Cloud payload:** only one confirmed ingredient, its current deterministic finding, and currently approved evidence summaries/permitted excerpts. Do not send source URLs, raw images, email addresses, other scan ingredients/full scans, or profile/skin data. No cloud multimodal OCR/image analysis.
- **OCR:** Tesseract baseline plus a measured PaddleOCR comparison; user confirmation is required regardless.
- **Safety/evidence:** deterministic, source-backed rules; no overall safety score or unreviewed evidence letter grade.

Milestones 1–9 have implementations through image/OCR intake, exact ingredient resolution, versioned deterministic rules, separately reviewed evidence mappings, optional retrieval, private owner-scoped analysis, on-demand LLM explanations, a first-pass responsive frontend, and local QA/security hardening. M10 adds a documented single-Linux-host Compose scaffold, restricted PostgreSQL runtime role, Caddy TLS configuration, persistent private-photo storage, and manual age-encrypted backup/restore tooling. M11 adds release-gate CI and cross-browser accessibility checks; local browser checks passed but do not establish WCAG conformance. See the milestone reports and `docs/MILESTONE_11.md` for results and verification boundaries. M6 passed 67 tests at completion; M7 passed 76; M8 passed 78; the current full backend suite passed 81 tests. Ruff, Node syntax/security smoke checks, `pip check`, SQLite migration checks, M10 YAML/static assertions, shell syntax, and the new fake-tool off-site backup wrapper smoke passed. The latter used no real encryption or remote service and was not a restore drill. The local SQLite database remains at `0005_rules_rag_analysis`; M10 adds no migration. M6/M7 source/evidence fixtures are synthetic and providers are mocked; the production corpus remains empty. The owner selected no public source-code license and approved encrypted daily off-host backups (30-day retention, 24-hour RPO, 4-hour RTO, quarterly drills). Rights-cleared source/evaluation data and reviewer approval, code/data rights review, actual backup destination, target-host scheduling/alerts, and measured restore-drill evidence remain open. Docker/Compose/PostgreSQL execution, hosted Windows/Linux CI, Tesseract, live Ollama/Qdrant/LLM quality, CVE remediation, and formal accessibility/usability review remain unresolved; comparison/routine APIs and real SMTP remain pending.

---

## Technical references checked for this review

- PyPI release metadata for the pinned FastAPI, Pydantic, pydantic-settings, Alembic, Uvicorn, httpx2, argon2-cffi, and email-validator packages: [FastAPI](https://pypi.org/project/fastapi/), [Pydantic](https://pypi.org/project/pydantic/), [pydantic-settings](https://pypi.org/project/pydantic-settings/), [Alembic](https://pypi.org/project/alembic/), [Uvicorn](https://pypi.org/project/uvicorn/), [httpx2](https://pypi.org/project/httpx2/), [argon2-cffi 25.1.0](https://pypi.org/project/argon2-cffi/25.1.0/), [email-validator 2.3.0](https://pypi.org/project/email-validator/2.3.0/)
- FastAPI Python 3.11 support: [3](https://fastapi.tiangolo.com/release-notes/)
- SQLAlchemy 2.1 Python support: [3](https://docs.sqlalchemy.org/en/21/intro.html); Alembic Python support and SQLAlchemy dependency: [1](https://alembic.sqlalchemy.org/en/latest/front.html)
- Ollama structured output/chat and embeddings: [1](https://docs.ollama.com/capabilities/structured-outputs), [2](https://docs.ollama.com/api/chat), [1](https://docs.ollama.com/capabilities/embeddings)
- Qdrant local/self-hosted quickstart: [2](https://python-client.qdrant.tech/quickstart.html)
- Celery Python 3.11/Redis task-queue docs and Windows support FAQ: [3](https://docs.celeryq.dev/en/main/history/whatsnew-5.6.html), [4](https://docs.celeryq.dev/en/latest/getting-started/introduction.html), [1](https://docs.celeryq.dev/en/stable/faq.html)
- OWASP upload, password storage, CSRF, and session guidance: [1](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html), [1](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [1](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [2](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- FastAPI upload-file/multipart guidance: [1](https://fastapi.tiangolo.com/tutorial/request-files/); Pillow 13.0.0 and python-multipart 0.0.33 package metadata: [Pillow](https://pypi.org/project/Pillow/13.0.0/), [python-multipart](https://pypi.org/project/python-multipart/0.0.33/)
- Tesseract CLI TSV usage and installation: [command-line usage](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html), [installation](https://tesseract-ocr.github.io/tessdoc/Installation.html)
- Open Beauty Facts data/API and reuse terms: [1](https://world.openbeautyfacts.org/data)
- WCAG 2.2 Recommendation: [1](https://www.w3.org/TR/WCAG22/)
