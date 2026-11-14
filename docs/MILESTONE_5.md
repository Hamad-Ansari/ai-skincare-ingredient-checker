# Milestone 5 — Image and OCR

**Status:** Core implementation complete and locally tested on CPython 3.11/Linux with SQLite. Live Tesseract execution and the architecture's OCR evaluation gate remain pending.  
**Date:** 9 November 2026

## Implemented

### Secure image intake and private storage

- Added authenticated, signed-CSRF-protected `POST /api/v1/scans` multipart intake. It accepts exactly one file in the `image` field; unsupported extra form fields/files are rejected.
- The API trusts neither the client MIME type nor filename. Pillow inspects and decodes actual bytes; only single-frame JPEG, PNG, and WebP are accepted. SVG and unsupported raster formats are not accepted.
- Default caps are **10 MiB per image** (`SCAN_MAX_UPLOAD_BYTES`) and **20,000,000 pixels** (`SCAN_MAX_IMAGE_PIXELS`). An ASGI receive limiter caps the complete multipart body before multipart spooling; the file bytes are independently checked after parsing.
- Images are orientation-corrected, converted to RGB, re-encoded to JPEG, and stripped of metadata before storage. The input is never passed to a cloud OCR service.
- `PrivateScanStorage` stores sanitized bytes under `PRIVATE_SCAN_STORAGE_DIR/<user-uuid>/<random-uuid>.jpg`. Client filenames are not stored, returned, or used in any path. POSIX directory/file permissions are restricted (`0700`/`0600`). The default directory is ignored by Git and is not mounted as public web content.
- Uploads have process-local per-user and per-IP limits. The default policy is 8 uploads per user per hour and 40 per client IP per hour; this limiter is not shared across workers.

### Persisted OCR and explicit review

- Added Alembic revision `0004_image_scans` with `scans` and `scan_ingredients` tables, ownership indexes, and database constraints for statuses, metadata, confidence ranges, and ordered draft entries.
- Scan state is persisted (`queued`, `extracting`, `needs_confirmation`, `confirmed`, `failed`) separately from OCR state (`queued`, `running`, `succeeded`, `unavailable`, `failed`). Safe error codes distinguish a missing OCR executable, timeout, generic OCR failure, and missing stored photo.
- Added a replaceable `OcrEngine` interface and a local Tesseract CLI adapter. It sends the sanitized JPEG to the local process via stdin, requests TSV output, and preserves word text, confidence, and bounding boxes where available. No shell is used. The adapter does not submit images to OpenAI, Groq, Ollama, or another network service.
- Raw OCR text and tokens are always unconfirmed. Milestone 5 does **not** guess ingredient boundaries; the editable ingredient draft starts empty. A user can replace/correct/reorder that list with `PATCH /api/v1/scans/{scan_id}/ingredients`, then must call `POST /api/v1/scans/{scan_id}/confirm` with `{"accepted": true}`. Only that explicit action sets the confirmation timestamp and entry flags. Product analysis is not implemented by this milestone.
- Missing-engine behavior is explicit: the scan remains available for manual entry, reports OCR state `unavailable` and error code `ocr_engine_unavailable`, and does not fabricate OCR text or confidence.

### Ownership, photo retrieval, export, and deletion

- Added current-user-only paginated scan history, scan detail, correction/confirmation, photo retrieval, and per-scan deletion routes. All scan queries include the authenticated owner ID; another account receives `404` for a scan or its photo.
- `GET /api/v1/scans/{scan_id}/photo` returns the sanitized retained JPEG as an authenticated attachment. The response filename is generated from the scan UUID, not the uploaded filename.
- Per-scan deletion removes the photo before deleting the database row; account deletion removes the entire private per-user directory (including orphan files) before the user row is deleted. Scan draft rows cascade with scan deletion and scan rows cascade with account deletion. Missing photos/directories are handled idempotently.
- `GET /api/v1/privacy/export` now includes each scan's OCR text/tokens/confidence, persisted state, corrected entries, confirmation time, photo availability, and relative authenticated photo-download URL. Export never exposes an on-disk path or storage key and does not inline photo bytes.

## API routes

- `POST /api/v1/scans` — authenticated multipart upload; returns `202 Accepted` and a scan ID/state.
- `GET /api/v1/scans?limit=50&offset=0` — current-user paginated scan history.
- `GET /api/v1/scans/{scan_id}` — owner-scoped OCR state and draft.
- `PATCH /api/v1/scans/{scan_id}/ingredients` — replace the unconfirmed ingredient draft.
- `POST /api/v1/scans/{scan_id}/confirm` — explicit user confirmation.
- `GET /api/v1/scans/{scan_id}/photo` — authenticated retrieval of the retained sanitized photo.
- `DELETE /api/v1/scans/{scan_id}` — remove one scan and its retained photo.
- `GET /api/v1/privacy/export` — includes scan/OCR/correction history and photo retrieval links.
- `DELETE /api/v1/users/me` — password-confirmed account deletion includes private image cleanup.

No `/analysis` endpoint is added in M5; later analysis must refuse any scan that has not been explicitly confirmed.

## Settings and dependencies

- Added `Pillow==13.0.0` and `python-multipart==0.0.33` to `backend/requirements.txt`; regenerated both universal Python 3.11 lock files.
- New settings: `PRIVATE_SCAN_STORAGE_DIR`, `SCAN_MAX_UPLOAD_BYTES`, `SCAN_MAX_IMAGE_PIXELS`, `OCR_TESSERACT_COMMAND`, `OCR_TESSERACT_LANGUAGE`, and `OCR_TIMEOUT_SECONDS`. Defaults and limits are documented in `.env.example` and the installation guide.
- Tesseract is an optional external executable, not a Python package. Install Tesseract and the desired trained data separately; the sandbox has no `tesseract` executable.

## Verification performed

- Test interpreter: CPython 3.11.18/Linux. The M5 suite uses generated synthetic raster data, synthetic TSV, and an explicitly named fake OCR adapter. It contains no real private product-label photos and makes no OCR accuracy claim.
- `pytest -q`: **59 passed**.
- `ruff check backend scripts`: **passed**.
- `ruff format --check backend scripts`: **passed**.
- Fresh Python 3.11 development/runtime lock environments installed successfully; `uv pip check` passed (44 development packages; 35 runtime packages). A final `python -m pip check` also passed in both environments after bootstrapping pip. Pillow 13.0.0, FastAPI 0.143.0, python-multipart 0.0.33, and SQLAlchemy imports passed.
- SQLite Alembic migration integration upgrades to `0004_image_scans`, verifies the scan tables, then downgrades through `0003_ingredient_evidence`, `0002_auth_profiles`, and `0001_schema_baseline`. The local development database is at `0004_image_scans (head)`; `alembic check` reports no model/migration drift.
- API tests cover CSRF/auth, request-size and upload-rate limits, actual-byte format checks with mismatched client MIME, metadata-free JPEG storage, photo retrieval, missing-Tesseract state, corrections/confirmation, cross-user denial, export, and per-scan/account deletion.
- Live Uvicorn smoke checks returned HTTP 200 for `/health/live`, `/health/ready`, and `/openapi.json`; OpenAPI advertises multipart scan upload and all M5 scan routes. An unsafe scan POST without CSRF returned HTTP 403.

## Limitations and remaining gates

- **Live Tesseract was not available in the sandbox.** The CLI adapter's invocation and TSV parser are tested with mocks/fixtures, and missing-engine behavior is tested, but actual OCR operation is unverified.
- No reviewed cosmetic-label evaluation corpus or ground truth has been approved. No OCR character error rate, ingredient precision/recall, or generalized OCR accuracy is claimed. Evaluate only on data with documented rights and manually verified ground truth.
- The current OCR runner is FastAPI `BackgroundTasks`: convenient for local development/tests but non-durable across process restarts. A production worker/queue must reclaim stuck `queued`/`extracting` scans and retain the same database state contract.
- The filesystem storage adapter is local development storage, not encrypted production object storage. Production deployment still needs private encrypted object storage, backup-expiry policy, access controls, monitoring, and tested deletion lifecycle.
- There is no scan frontend yet. Users can use the API; the planned browser correction/review experience remains in the frontend milestone.
- Windows CI, Docker image build, PostgreSQL, and live SMTP remain unverified. Later analysis/rules/RAG/provider calls are not implemented.

**Next work:** install and verify local Tesseract with the required trained data; approve an evaluation corpus and ground truth; report measured OCR and extraction metrics without overstating generality; build the accessible scan review UI; and implement durable queue/recovery plus production object-storage integration before launch.
