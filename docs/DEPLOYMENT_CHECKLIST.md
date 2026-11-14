# Deployment and launch checklist

**Current disposition:** Not signed off. M10 provides a Compose deployment scaffold; environment execution and several legal, safety, operations, and recovery gates remain open. Complete this checklist for the chosen release environment. A checked local smoke test is not a substitute for the corresponding hosted/production test.

## Scope and owners

- Hosting scope: owner requires **Pakistan-only** hosting and confirms any in-country city is acceptable; primary host and all backup/DR copies must remain in Pakistan. Owner accepts any verified local backup method (S3-compatible is optional; provider-native service may be evaluated). Budget is USD $30–$40/month planning range, excluding domain/email; exact hard cap remains unconfirmed. **Local provider, quote, project, domain, and backup service are not selected.** See [`HOSTING_RECOMMENDATION.md`](HOSTING_RECOMMENDATION.md) and [`HOSTING_VENDOR_RFQ.md`](HOSTING_VENDOR_RFQ.md).
- Environment/hostname: ______________________________
- Release tag and image digests: ______________________
- Operator/owner: ____________________________________
- Technical reviewer: ________________________________
- Safety/domain reviewer: ____________________________
- Legal/privacy reviewer: ____________________________
- Target launch date: ________________________________

## Build, install, and database

- [ ] Clean Windows 10/11 Python 3.11 installation from `docs/INSTALLATION_GUIDE.md` completed and test results recorded.
- [ ] Clean Linux Python 3.11 installation completed and test results recorded.
- [ ] Hosted Ubuntu and Windows GitHub Actions runs pass; failures reviewed, not merely re-run.
- [ ] Docker image builds from the release revision; final image digest and SBOM are captured.
- [ ] `docker compose --env-file .env.production config --quiet` passes on the deployment host.
- [ ] PostgreSQL 17 fresh-volume init, least-privilege role, Alembic upgrade, integration tests, and restart/persistence tests pass.
- [ ] PostgreSQL backup and restore are tested on an isolated host/volume using the selected production version.
- [ ] Production update/rollback procedure is rehearsed with a migration that may not be reversible.

## Network, secrets, and security

- [ ] DNS and TLS issuance/renewal verified for the actual hostname; firewall exposes only approved ports.
- [ ] FastAPI and PostgreSQL have no public host ports; Caddy is the only public ingress.
- [ ] `.env.production` is unique, root/operator-restricted, excluded from backups or separately protected, and absent from logs/artifacts.
- [ ] App secret, PostgreSQL administrator/app passwords, SMTP credentials, and any provider keys are generated/stored/rotated under an approved secret policy.
- [ ] Production CORS/Origin behavior, secure cookies, CSP, upload limits, and proxy-header trust are tested through the actual proxy.
- [ ] Vulnerability/CVE scan is run against Python dependencies and all final container images; exceptions and patch cadence are approved.
- [ ] Single-worker/process-local rate limits and single-host storage constraints are accepted or replaced before scaling.
- [ ] Host disk encryption, administrator access, firewall, patching, container permissions, and incident contacts are reviewed.
- [ ] Provider contract confirms the host, database, private uploads, logs/metadata, snapshots, backups and DR copies remain in Pakistan; Docker/Compose/root access, fixed IP, ports, support-access terms and all-in price are verified.

## Product, safety, and privacy

- [x] Owner selected no public source-code license or reuse grant; no `LICENSE` file is added. This is a no-public-license status, not an open-source grant.
- [ ] Confirm copyright ownership/contributor permissions; prepare and review release-specific dependency/image notices and SBOM before any external distribution.
- [ ] Receive and review the owner-reported ready source packet: verify provenance, rights/permission, allowed use/attribution, expiry/review metadata, and traceable import mapping; see [`PRODUCTION_DATA_INTAKE.md`](PRODUCTION_DATA_INTAKE.md). The packet has not yet been supplied or approved, so the production corpus remains empty.
- [ ] Owner reports a qualified reviewer is confirmed; record their role/qualifications/scope, row/rule/evidence decisions, review version/date, and written approval before any item is enabled.
- [ ] A rights-cleared, reviewed evaluation corpus and predeclared adjudication protocol are approved; OCR/extraction/rule/citation metrics and limitations are measured and published.
- [ ] Qualified safety/domain experts review every enabled production rule, evidence mapping, citation, warning, and user-facing claim.
- [ ] Live Tesseract OCR is installed/evaluated, or image flows explicitly remain manual-only; no OCR accuracy claim is made without measured results.
- [ ] Live provider calls, consent, outbound-payload minimization, provider terms/retention, failure behavior, and explanation quality are reviewed; no unapproved provider is enabled.
- [ ] Browser/device, keyboard, screen-reader, WCAG 2.2 AA, usability, and security review are completed and findings resolved or accepted.
- [ ] Privacy notice covers account data, uploaded photos, deletion, email, providers, logs, backup retention, and user rights for target jurisdictions.
- [ ] Product language and intended-market regulatory/consumer-protection requirements receive legal and domain review.

## Backups, monitoring, and operations

- [x] Owner-approved baseline: encrypted off-host backups daily; 30-day retention; RPO 24 hours; RTO 4 hours; quarterly restore drills. This is a policy decision only, not proof that operations are configured or objectives met.
- [ ] Select and verify an in-country off-host backup provider/method, separate failure domain and restricted access. Confirm **all** copies/replicas stay in Pakistan, and verify encryption, daily cadence, 30-day retention, deletion/expiry protections, restore/export, and every fee. S3-compatible `rclone` storage is optional; provider-native backup is acceptable only with a reviewed implementation/runbook and the same restore evidence.
- [ ] For the age + `rclone` implementation, configure the public recipient, separately protected private-key recovery copy, and restricted remote for the target service account; rehearse key recovery without exposing key material. If provider-native backup is chosen, document and verify its key ownership, access controls, credential recovery and equivalent protections instead.
- [ ] Install and enable a target-host daily scheduler (the `infra/systemd/` files are uninstalled templates), select/confirm its run window, and monitor successful completion/staleness.
- [ ] Configure failure, staleness (>24 hours), and staging/destination capacity alerts; test delivery to the responsible operator. The supplied systemd unit does not alert by itself.
- [ ] Verify each daily backup completes and passes an independent integrity/read-back check. Test 30-day expiry/deletion is limited to the authorized backup scope (for `rclone`, a dedicated prefix); provider-native services require equivalent retention and deletion tests.
- [ ] Complete an isolated restore drill before launch and quarterly thereafter; measure end-to-end recovery against the 4-hour RTO and record evidence, reviewer, and remediation. Do not drill against live volumes.
- [ ] Backup owner/on-call responder: __________; approved service/destination reference (no credentials): __________; next drill due: __________.
- [ ] External HTTPS/liveness/readiness and SMTP delivery monitoring are configured without collecting unnecessary personal/request data.
- [ ] Log retention, access, sanitization, alert routing, incident response, and breach-notification processes are approved.
- [ ] Object/private-photo storage quotas, host encryption, account deletion, backup expiry, and restore behavior are verified.
- [ ] Deployment, migration, rollback, emergency contact, and destructive teardown runbooks are owned and rehearsed.

## Approval

- Product owner: __________________________ Date: __________
- Engineering/operator: ___________________ Date: __________
- Safety/domain reviewer: _________________ Date: __________
- Legal/privacy reviewer: _________________ Date: __________

A deployment is not approved while material sections above are blank, the M9 release gates remain open, or an approver has unresolved critical/high findings.
