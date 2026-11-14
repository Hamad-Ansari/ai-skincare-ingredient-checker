# Milestone 10 — Deployment and Documentation

**Status:** Single-Linux-host Docker Compose deployment scaffold, operator documentation, and encrypted backup/restore helpers are implemented. Deployment and release sign-off remain **open**: Docker/PostgreSQL execution was unavailable here, and the M9 safety/security/browser/evaluation gates remain outstanding. Subsequent owner decisions selected no public source-code license and approved a backup-policy baseline; see M11 and the current deployment checklist for the remaining rights and operational work.  
**Verification date:** 9 November 2026 (local static checks only; no Docker, PostgreSQL, or hosted execution)  
**Database migration:** None.  
**Dependency changes:** None.

## Implemented

- `compose.yaml` defines Caddy, a single FastAPI worker, PostgreSQL 17, operator-run migrations, and isolated private-photo volume-init/backup helpers. Only Caddy publishes ports 80/443; the app and DB have no host ports. PostgreSQL is on an internal-only network; Caddy and the API also have egress for ACME, SMTP, and explicitly configured provider calls.
- The database initializer creates a dedicated non-superuser application role and assigns it ownership of the application database; the PostgreSQL bootstrap account is not sent to the API. The init script runs only for a fresh database volume.
- The API container runs read-only as the existing non-root user, with a writable private-photo volume and bounded `/tmp`, dropped Linux capabilities, a single worker, proxy-header trust, no access log, log rotation, and a DB-backed readiness check. Caddy persists certificate/config state and adds HSTS.
- `.env.production.example` documents the deployment inputs; production mode requires a strong application secret, PostgreSQL, explicit same-origin HTTPS, and STARTTLS mail. No optional cloud provider keys are passed in the default Compose setup.
- `scripts/backup_production.sh` streams PostgreSQL and photo-volume snapshots directly through age encryption and writes checksums. `scripts/restore_production.sh` verifies checksums/decryption before a guarded destructive restore; restore failures leave app traffic stopped. Scripts do not automate scheduling, off-host transfer, retention, or alerting.
- `docs/DEPLOYMENT.md`, `docs/DEPLOYMENT_CHECKLIST.md`, and `docs/LICENSE_AND_ATTRIBUTION.md` describe setup, operations, owner decisions, and explicit release gates. The later no-public-license decision is recorded without adding a `LICENSE` file; see the updated M11 status for subsequent owner choices and remaining work.
- GitHub CI now includes a Compose configuration validation step before the existing Docker build. Hosted CI has not yet been observed.
- Dockerfile prepares the private scan directory before mounting the named volume. `.gitignore` and `.dockerignore` exclude local backups.

## Local verification

| Check | Result |
|---|---|
| Compose and GitHub workflow YAML parse | Passed with the available YAML parser. |
| Static Compose assertions | Passed: expected services/healthchecks and private-network settings exist; neither API nor PostgreSQL declares a published host port; Caddy publishes only 80/443 (UDP 443 optional). |
| `bash -n` backup/restore scripts | Passed. |
| `sh -n` PostgreSQL init script | Passed. |
| Full backend suite, `python -m pytest -q backend/tests` | **81 passed in 7.06 s.** |
| Ruff format/check, `backend scripts` | Passed; all 101 files formatted and lint checks clean. |
| Node syntax/security smoke checks | Passed. |
| `pip check` in development environment | Passed; no broken requirements found. |
| SQLite current/head and migration-drift checks | Rechecked: `0005_rules_rag_analysis` is head; no new upgrade operations detected. M10 adds no migration. |
| Docker Compose config / Docker image build | **Not run:** Docker, Podman, and Compose executables are unavailable in this environment. CI has a Compose validation/build step, but no hosted run was observed. |
| PostgreSQL fresh-volume init, migration, integration, backup and restore | **Not run:** no PostgreSQL service/client or Docker runtime available. |

## Decisions and release gates still open

1. At M10, the owner had not yet recorded the source-code decision. The later decision is **no public source-code license or reuse grant**; no `LICENSE` file is added. Confirm ownership/contributor permissions and dependency notices before distribution; data/evidence/image/model rights remain separate.
2. At M10, the backup baseline was not yet approved. The later approved baseline is encrypted off-host daily backups, 30-day retention, 24-hour RPO, 4-hour RTO, and quarterly restore drills. Destination selection/configuration, actual scheduling and alerting, key recovery, retention verification, and restore-drill evidence remain open; M11 adds local wrappers/templates but does not configure a host or prove recovery.
3. The Compose path is a single-host scaffold, not a high-availability deployment. Local filesystem photo storage and process-local rate limits prevent horizontal scaling. Host-level disk encryption and access controls are mandatory for any real user data.
4. Docker image tags are not digest-pinned or vulnerability-audited. Docker build and Compose schema/runtime behavior remain unverified here.
5. SMTP delivery, live Tesseract OCR, live Qdrant/Ollama/OpenAI/Groq, Windows/Linux hosted CI, PostgreSQL migrations/integration, browser/accessibility, production monitoring, backup restore, and real corpus/rule/citation evaluation remain open.
6. The production evidence/rule corpus is still empty. Do not describe the application as production-ready or imply that no triggered finding proves safety.

## Files

- `compose.yaml`
- `infra/Caddyfile`
- `infra/postgres/10-app-role.sh`
- `.env.production.example`
- `scripts/backup_production.sh`
- `scripts/restore_production.sh`
- `docs/DEPLOYMENT.md`
- `docs/DEPLOYMENT_CHECKLIST.md`
- `docs/LICENSE_AND_ATTRIBUTION.md`

M10 delivers a documented deployment scaffold and security-conscious operational starting point, but **does not satisfy the deployment sign-off gate** until the Docker/PostgreSQL/hosted checks, policy decisions, and safety/release gates above are completed.
