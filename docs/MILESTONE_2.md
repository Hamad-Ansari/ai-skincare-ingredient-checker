# Milestone 2 — Backend Foundation

**Status:** Implemented and tested in the Linux/Python 3.11 sandbox; Windows CI and Docker image-build CI are configured but have not yet been run.  
**Date:** 9 November 2026

## Implemented

- Pinned direct runtime and development dependencies for Python 3.11 in `backend/requirements.txt` and `backend/requirements-dev.txt`.
- Added `backend/requirements-lock.txt` with a Python 3.11 universal development/test resolution and `backend/requirements-runtime-lock.txt` for the container runtime, including transitive pins.
- Added Pydantic Settings with project-root `.env` loading, explicit-origin validation, production secret checks, and a PostgreSQL-only production database guard.
- Added a FastAPI app factory with development-only OpenAPI docs, explicit optional CORS origins, baseline response security headers, and server-generated request IDs.
- Added `/health/live` and database-backed `/health/ready` endpoints with safe generic failure responses.
- Added SQLAlchemy engine/session helpers for SQLite and PostgreSQL, with an isolated in-memory SQLite engine for tests.
- Initialized Alembic with an initial no-op schema-baseline revision. The first domain tables are intentionally deferred to the authentication milestone.
- Added unit, API, database-readiness, and migration tests.
- Added a Windows/Linux GitHub Actions test matrix and a Dockerfile build job.
- Added PowerShell and Linux setup/run steps in `docs/INSTALLATION_GUIDE.md`.

## Dependency selections

Direct pins: FastAPI 0.143.0; Uvicorn 0.54.0; Pydantic 2.14.3; pydantic-settings 2.16.2; SQLAlchemy 2.1.8; Alembic 1.20.1; psycopg 3.3.8; python-dotenv 1.2.4; httpx2 2.16.0; pytest 9.2.0; Ruff 0.17.4.

The current FastAPI/Pydantic/Pydantic Settings and SQLAlchemy/Alembic release metadata supports the Python 3.11 target. Alembic 1.20 requires SQLAlchemy 2.0 or newer, and the selected SQLAlchemy 2.1.8 satisfies that requirement. See the technical references at the end of `docs/ARCHITECTURE_REVIEW.md` and the upstream release pages before future upgrades.

## Actual verification performed

- Test interpreter: CPython 3.11.18 on Linux.
- `pytest -q`: **13 passed**.
- `ruff check backend`: **passed**.
- `ruff format --check backend`: **passed**.
- `uv pip check`: **all installed packages are compatible**.
- `alembic upgrade head` against the local SQLite configuration: **passed**; current revision: `0001_schema_baseline`.
- Database `SELECT 1` readiness smoke check: **passed**.
- Live Uvicorn smoke checks: `/health/live` and `/health/ready` returned `{"status":"ok"}`; development `/openapi.json` returned HTTP 200.
- Test coverage includes invalid production settings, wildcard CORS rejection, health/readiness behavior, safe error output, response headers, development OpenAPI availability, and migration recording.

## Not yet verified / not implemented

- The Windows GitHub Actions job has been configured but has not been executed from this workspace; run the included PowerShell commands locally or push to a GitHub repository to verify the Windows runner.
- The Dockerfile and image-build CI job have been added, but the local sandbox has no Docker CLI; an actual image build remains pending a runner with Docker.
- No PostgreSQL server was available; PostgreSQL connectivity is configured but not integration-tested yet.
- Authentication/profile/privacy, the reviewed catalog foundation, and image/OCR intake have since been added in [Milestones 3](MILESTONE_3.md) through [5](MILESTONE_5.md). Frontend, RAG, safety rules, external ingredient/evidence data, cloud provider calls, and scan analysis remain pending.
- No production-readiness or security-certification claim is made.

## Follow-on milestone

Milestones 3–5 have since implemented authentication/profile/privacy, catalog-ingestion, and image/OCR intake foundations. See `docs/MILESTONE_3.md` through `docs/MILESTONE_5.md` for results and limitations. OCR evaluation and a live Tesseract engine remain pending.
