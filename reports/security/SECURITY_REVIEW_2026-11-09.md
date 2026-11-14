# Security and cybersecurity review

**Review date:** 9 November 2026 (Asia/Karachi)  
**Scope:** Local source/configuration review of the skincare checker repository; no production endpoint was supplied or tested.  
**Disposition:** **Not a production security sign-off.** Local code/dependency checks were clean, but final container-image evidence and deployment verification remain open.

## Executive summary

No confirmed exploitable application-code vulnerability was established in the reviewed scope. The implementation has several good baseline controls: password hashing and server-side sessions, signed CSRF checks, restrictive production headers, per-user scan access, bounded and normalized image uploads, optional LLM consent and output validation, and a hardened single-host Compose scaffold.

That is not a clean bill of health. The current release image CVE status was not independently verified; an existing image report is explicitly provisional and has timestamps later than this review date. The Compose deployment trusts forwarded headers from any address that can reach the API container, and deployment uses mutable image tags. CI has dependency and image scans but no dedicated SAST or repository secret-scanning job. The deployment checklist itself remains unsigned/incomplete. **Do not treat this review as production approval or as a penetration test.**

## Verification performed

| Check | Result |
|---|---|
| Backend tests | **81 passed** (`.venv/bin/python -m pytest -q backend/tests`, 6.80 s). `TEST_DATABASE_URL` was unset, so these used the default SQLite test database; PostgreSQL integration was not exercised. |
| Python dependency advisories | `pip-audit` on both `backend/requirements-lock.txt` and `backend/requirements-runtime-lock.txt`: **no known vulnerabilities reported**. |
| Python lock/environment consistency | `uv pip check --python .venv/bin/python`: **56 packages checked; compatible**. |
| Frontend dependency advisories | `npm audit` and `npm audit --omit=dev`: **0 reported vulnerabilities**. The package is a small browser-test toolchain, not a bundled production JS dependency tree. |
| Lint/format | Ruff check passed; format check passed (**101 files already formatted**). |
| Frontend security smoke | Node syntax checks and `frontend/tests/security-smoke.mjs` passed. |
| Secret-pattern review | A limited local scan covered 867 files and found no high-confidence private-key, AWS-key, GitHub-token, or credential-URL patterns. One credential-looking URL was a test fixture, not a discovered credential. Only `.env.example` and `.env.production.example` were present; no real `.env` or `.env.production` was found. This was **not** a substitute for Gitleaks or a history scan. |
| Repository history | Not assessable: this workspace snapshot contains no `.git` metadata. Tracked-file status, prior commits, deleted secrets, and branch protections could not be reviewed. |
| Container/hosted validation | Not run locally: Docker/Podman and Trivy were unavailable. No hosted CI run was observed, no production Compose deployment was exercised, and no live endpoint or penetration test was assessed. |

## Confirmed code/configuration observations

### Controls that looked sound in the reviewed code

- Authentication uses Argon2id password hashes, generic login errors, hashed random session/one-time tokens, server-side session revocation, and expiry checks. Production configuration rejects short app secrets and development token exposure.
- Unsafe API requests require a signed CSRF cookie/header pair; production also requires a valid Origin. Production cookies are Secure, the session cookie is HttpOnly, and tests check the restrictive CSP and cookie attributes.
- Scan uploads are bounded before multipart spooling, decoded by actual image bytes, restricted by byte/pixel/type/frame limits, and re-encoded to metadata-free JPEG. The photo store uses generated keys, per-user directories, restrictive permissions, and authenticated user scoping.
- Admin endpoints require an explicit admin role and record audit events. Optional LLM explanations use bounded context, no tool execution, strict response schemas, and link/markup rejection. These properties have unit/integration coverage; this review did not assess model quality or external provider contracts.
- The API container runs as a non-root user. Compose applies a read-only root filesystem, `no-new-privileges`, dropped capabilities, a PID limit, and a private DB network. Only Caddy publishes host ports in the scaffold. Caddy handles TLS and emits HSTS.
- CI is configured for dependency audits and Trivy scans with a blocking fixable HIGH/CRITICAL policy for the API, PostgreSQL, Caddy, and helper images. The Trivy action itself is pinned by commit SHA.

### Open findings and hardening follow-ups

| ID | Status / priority | Evidence and impact | Recommended action |
|---|---|---|---|
| **R-01: Current release-image CVE status is unverified** | **Open release gate; high priority before deployment. Not a confirmed current CVE.** | `docs/CONTAINER_CVE_REVIEW.md` records a remote-tag snapshot with fixable HIGH/CRITICAL findings for PostgreSQL, Caddy, and the Python base. However, that report records scan timestamps on **13 November 2026**, after this review date, and it did not scan the final built API image. Its counts are therefore provisional and were not independently reproduced here. The CI gate is configured, but no hosted run/result was available. | Run the CI image build and Trivy policy on a trusted runner for the exact release artifacts; capture immutable digests and full reports, patch or document time-bounded exceptions, and rerun the blocking policy. Do not release using the old report as current evidence. |
| **R-02: Forwarded-header trust is wildcarded** | **Conditional hardening gap; medium. No internet exploit path established for the current topology.** | `compose.yaml` passes `--forwarded-allow-ips=*` to Uvicorn. The API has no published host port and Caddy is the only published ingress, which materially limits exposure. But any container/peer able to connect directly to the API can supply trusted `X-Forwarded-*` values, affecting client IP/scheme/host interpretation and IP-based controls. | Restrict trusted forwarded headers to the actual proxy path/source, isolate the API-to-proxy network, and verify spoofed-header behavior through the deployed proxy. Keep the API port unpublished and do not attach untrusted containers to its networks. |
| **R-03: No dedicated SAST or secret scanner is configured in CI** | **Confirmed CI coverage gap; medium. Not evidence that a vulnerability or secret exists.** | The repository has one workflow with tests, Ruff, dependency audits, frontend smoke, and Trivy image scans. It has no dedicated CodeQL/Semgrep/Bandit or Gitleaks/TruffleHog job. The local history could not be scanned because `.git` is absent, and Gitleaks was unavailable. | Add a maintained SAST and secret-scanning job for pull requests and the default branch; scan history where repository access permits. Keep baseline suppressions reviewed and narrowly scoped. |
| **R-04: Infrastructure image references are mutable tags** | **Confirmed supply-chain/reproducibility hardening gap; medium.** | `Dockerfile` uses `python:3.11-slim`; Compose uses tags including `postgres:17-alpine`, `caddy:2-alpine`, and `busybox:1.37.0`. Tags can move, so the image scanned in CI may not be the one later deployed under the same tag. The deployment checklist asks for image digests, but the scaffold does not pin these references to digests. | For a release, build/promote immutable image digests and deploy those exact digests that passed scanning. Generate and retain an SBOM and the associated scan report; update pins deliberately. |
| **R-05: Production operational gates remain open** | **Release readiness issue; high priority before real users/data.** | `docs/DEPLOYMENT.md` calls the Compose path a scaffold, and `docs/DEPLOYMENT_CHECKLIST.md` still has open items for hosted CI, container builds, database/restore, proxy behavior, secret handling, vulnerability scans, and operations. No target host or production endpoint was reviewed. | Complete the deployment checklist against the real host and DNS, test TLS/renewal, firewall and proxy headers, least-privilege DB access, backup/restore, monitoring, secret rotation, and incident response; record reviewers and evidence before launch. |

## Important limitations and review questions

- This is source/configuration inspection plus local tests, not a live-system assessment. No production URL, credentials, network target, Docker host, or external provider was tested.
- The full backend test run used SQLite. PostgreSQL-specific behavior, the Compose build/runtime, host firewall, TLS issuance, and actual proxy trust were not validated here.
- The local secret-pattern scan is deliberately described as limited. Because there is no repository history, it cannot rule out a secret committed and later removed.
- CI/deployment scan evidence should be attached to the exact immutable image digests used for release; a scan of a remote mutable tag or only the base image is not sufficient.
- The intended deployment is single-worker/single-host. Its rate limiters are process-local and photo storage is local-volume based. Do not scale to multiple workers/replicas/hosts without replacing these with shared controls/storage and retesting.
- The production CSP still permits inline styles (`style-src 'unsafe-inline'`), as documented in `docs/MILESTONE_9.md`; inline scripts remain disallowed. Consider removing the style exception during UI cleanup.

## Conclusion

**Local results are encouraging, but the application is not cleared for production.** The locked Python and npm dependency audits reported no known vulnerabilities; all 81 local backend tests, Ruff checks, and frontend security smoke checks passed. No application-code defect was substantiated, so no code remediation was made in this pass. The highest-priority next step is a trusted, current scan of the final release images, followed by validation of proxy trust and closure of the deployment checklist.
