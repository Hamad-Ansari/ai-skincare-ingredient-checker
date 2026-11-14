# Milestone 6 — Deterministic Rules, Evidence Retrieval, and Private Analysis

**Status:** M6 backend core implemented and locally verified with synthetic-only rule/evidence fixtures. This is not a populated safety corpus, clinical validation, or production-readiness claim.  
**Verification date:** 9 November 2026  
**Migration:** `0005_rules_rag_analysis` (upgrades from `0004_image_scans`)  
**Scope:** versioned deterministic ingredient-presence rules, separately reviewed evidence mappings, optional Qdrant/Ollama retrieval, owner-private scan analysis, and server-validated citations.

## Delivered

### Deterministic rule lifecycle

- Rules are immutable, versioned `ingredient_presence` records with a strict schema over canonical ingredient UUIDs; arbitrary executable expressions are not accepted.
- Admin workflow creates drafts, separately reviews each evidence mapping, reviews the rule, activates one version per rule key, and supports retirement. Activation rechecks active canonical targets, current source rights, and approved evidence coverage for every target.
- Source/evidence/ingredient status is authoritative in SQL. Source-rights changes retire dependent active rules and trigger a best-effort vector purge. SQL filters still block current findings and citations when a purge cannot be completed; reapproving a source does not reactivate retired rules.
- The production seed/evidence corpus remains empty. No external skincare source or safety claim was introduced.

### Qdrant and embeddings

- Qdrant is accessed through a small adapter and can be configured as a single-process local path (`VECTOR_DB_PATH`) or remote endpoint (`QDRANT_URL`), never both. `QDRANT_API_KEY` is accepted only with a remote URL. The collection dimension is established from a validated embedding vector; existing dimension drift fails closed, and a concurrent collection-creation race is handled by rechecking the collection.
- Ollama `/api/embed` is the embedding adapter. Input, response size, response shape, numeric values, and vector dimension are bounded/validated. Embedding/model errors do not become warnings or guessed citations.
- Only an explicitly approved evidence summary is embedded. The vector payload contains minimal source/evidence/ingredient identifiers and approval metadata; it contains no scan, profile, email, image, excerpt, or private user content.
- Retrieval requires the exact ingredient ID and the current SQL-approved mapping IDs, in addition to approved review/rights metadata in Qdrant. Qdrant hits are candidates/ranks only; citation text and provenance are loaded from SQL.
- If retrieval is disabled or unavailable, deterministic rule findings and currently approved SQL citations can still be returned with an explicit retrieval status. A vector result never creates or suppresses a deterministic rule match.

### Private scan analysis and citations

- `POST /api/v1/scans/{scan_id}/analysis` requires an owned scan that was explicitly confirmed and whose every entry is marked user-confirmed. `GET /api/v1/scans/{scan_id}/analysis` is owner-scoped. Other users receive not-found behavior.
- Confirmed names use the existing exact resolver. Ambiguous and unresolved inputs have no canonical ingredient ID, do not trigger a rule, and are returned for review; the system never guesses.
- Analysis snapshots the active rule versions and exact resolver outcomes, persists findings and reviewed evidence mappings, and rechecks current catalog/rule/source rights when serializing. Changed rule/catalog/rights state makes the prior analysis stale and withholds current findings/citations until it is rerun.
- Each displayed finding has a non-empty citation list resolved from current approved evidence mappings and sources. Citation URLs are server-generated from stored source records; excerpts are shown only when current source permissions allow them.
- Responses carry an educational disclaimer. No active rules and no matching configured rules are explicitly **not** an assessment or proof of safety. There is no safety score. Rule results are limited to the reviewed rule set.
- Account export includes analysis history. Scan deletion cascades analysis/findings/references.
- LLM-generated explanations are not implemented in M6; no chat model makes, changes, or cites findings.

## API and configuration

Admin routes include:

- `POST/GET /api/v1/admin/rule-versions` and `GET /api/v1/admin/rule-versions/{id}`
- `POST /api/v1/admin/rule-versions/{id}/evidence-mappings/{mapping_id}/review`
- `POST /api/v1/admin/rule-versions/{id}/review`, `/activate`, and `/retire`
- `POST /api/v1/admin/evidence/{evidence_record_id}/index` for explicit indexing of an approved summary

Analysis routes are `POST` and `GET /api/v1/scans/{scan_id}/analysis`. Both inherit the authenticated-session and CSRF protections of the existing API; analysis additionally requires owner scope and explicit scan confirmation.

M6 settings documented in `.env.example`:

- `OLLAMA_BASE_URL`, `OLLAMA_EMBED_MODEL` (default model name: `embeddinggemma`), and `RAG_EMBEDDING_TIMEOUT_SECONDS`.
- Exactly one of `QDRANT_URL` or `VECTOR_DB_PATH`; optional remote `QDRANT_API_KEY`; `QDRANT_COLLECTION`; and `RAG_TOP_K`.
- Local Qdrant data is ignored by Git (`data/qdrant/*`). Do not point multiple application processes at a local embedded Qdrant path; use a Qdrant server for multi-process deployments.
- Live retrieval requires the selected Ollama embedding model to be installed and reachable as well as a configured Qdrant backend. If either is unavailable, rule analysis remains deterministic and reports retrieval as unconfigured/unavailable.

## Schema and dependency changes

Migration `0005_rules_rag_analysis` adds `rule_versions`, `rule_evidence_mappings`, `scan_analyses`, `analysis_ingredients`, `analysis_findings`, and `analysis_finding_evidence`, with version/status constraints, foreign keys, indexes, and scan-deletion cascades. It downgrades through M5 and M4. `qdrant-client==1.20.0` is pinned as a direct dependency. The universal Python 3.11 development and runtime locks were regenerated and both environments passed `pip check`.

## Verification

- Full backend suite: **67 passed**.
- Ruff format and lint: passed.
- Synthetic-only integration tests cover rule/mapping review and version activation, exact/ambiguous/unresolved handling, owner privacy, current-rights revocation and reapproval behavior, SQL citation validation, retrieval outage behavior, privacy export, and scan-deletion cascades.
- Unit tests cover deterministic condition validation, Qdrant metadata/ingredient/allowed-ID filters, vector validation and collection-dimension/race behavior, Ollama response validation without network access, and fail-closed retrieval.
- Migration integration test upgrades to `0005_rules_rag_analysis` and downgrades through `0004_image_scans` and `0003_ingredient_evidence`.
- The local SQLite development database was upgraded from `0004_image_scans` to `0005_rules_rag_analysis`; `alembic check` reported **No new upgrade operations detected**. `PRAGMA foreign_key_check` found zero violations; local source, ingredient, evidence, rule, and evidence-mapping tables contain zero rows.

## Not verified / not included

- No real source, evidence, ingredient catalog, or production rule was seeded. Test fixtures are explicitly synthetic and use `.example.invalid` sources.
- No live Ollama endpoint, real embedding model, remote Qdrant, retrieval-quality benchmark, citation-support evaluation, or production corpus was tested. Qdrant behavior is exercised with its in-memory client; Ollama HTTP behavior is mocked.
- Tesseract execution/accuracy, Windows CI, Docker image build, PostgreSQL, SMTP delivery, frontend UI, product comparisons/routines, and LLM explanation adapters remain outside M6 verification.
- The feature is not medical advice, a safety certification, or evidence that an unflagged product is safe. Human/domain review, licensed sources, and measured evaluation are prerequisites before populating a production corpus.
