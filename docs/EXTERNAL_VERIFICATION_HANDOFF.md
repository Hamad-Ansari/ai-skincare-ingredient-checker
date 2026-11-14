# External verification handoff

**Purpose:** collect evidence for the checks that cannot run in this workspace. No credentials, encryption keys, database dumps, real user photos, or personal data are required in a response.

## Safe sharing rules

- Do **not** paste or upload `.env.production`, `.env`, `rclone.conf`, age identity/private keys, passwords, tokens, SMTP/provider credentials, database dumps, photo archives, or real scan images/labels.
- Do not share GitHub access tokens, cloud credentials, SSH keys, or a complete unsanitized environment/log bundle. A public age recipient is not secret, but it is not needed in a report.
- Redact hostnames, public IPs, account emails, bucket/account identifiers, user IDs, and private paths. Keep commit SHA, job/step names, exit status, error text after redaction, timestamps/timezones needed to measure recovery, and CVE IDs/severity/fix status.
- Use synthetic test accounts and data for CI/Compose/backup checks. Never point a destructive restore at live production volumes.

## Hosted GitHub Actions

The repository workflow `.github/workflows/backend-ci.yml` supports `push`, `pull_request`, and `workflow_dispatch`. From the repository's Actions page, run **Backend CI** on the candidate commit (or use the normal PR/push trigger). Capture:

1. Full commit SHA and workflow run ID/URL (the URL may be redacted if the repository is private).
2. Conclusion and any failed step for each job: `Tests (ubuntu-latest, Python 3.11)`, `Tests (windows-latest, Python 3.11)`, `Accessibility smoke (chromium)`, `Accessibility smoke (firefox)`, `Accessibility smoke (webkit)`, `Compose build, image CVE scan, runtime, and restore smoke`, `Python dependency vulnerability audit`, and `PostgreSQL 17 integration`.
3. Whether the `clarity-container-cve-reports-*` artifact and all three `clarity-browser-accessibility-*` artifacts were uploaded. For the container scans, note whether the four JSON reports (`api`, `postgres`, `caddy`, `busybox`) were produced before enforcement and summarize fixable HIGH/CRITICAL findings. Share redacted reports only if useful; do not include credentials or unrelated runner data.
4. For failures, the relevant step's redacted log excerpt and whether the failure is reproducible on the same commit. Do not rerun away a failure without recording it.

The workflow's Compose job creates an ephemeral test environment and exercises PostgreSQL initialization, migrations, health/least-privilege checks, encrypted local backup, and guarded restore. It also scans the **built API image** plus the three Compose infrastructure/helper images. This is the required evidence for the configured CI gate; a local scan of remote tags is not equivalent.

## Docker and PostgreSQL checks outside hosted CI

Use an isolated, disposable Linux VM/runner with Docker Engine/Compose installed and synthetic data. Do not run migration, `down --volumes`, backup, or restore commands against production unless the operator explicitly authorizes the operation and has a verified recovery path. Follow `docs/DEPLOYMENT.md` for host-specific setup; capture only exit statuses, service health, schema/revision, and redacted failure text.

The release workflow already performs the core checks. If repeating the Compose part manually, use an isolated `.env.production` containing newly generated throwaway values, then record results for:

```bash
docker compose --env-file .env.production config --quiet
docker compose --env-file .env.production --profile ops build --pull app migrate scan-volume-init
docker compose --env-file .env.production up -d db
docker compose --env-file .env.production --profile ops run --rm migrate
docker compose --env-file .env.production up -d --wait app
```

For a separate PostgreSQL integration run, point both variables at a disposable PostgreSQL database whose name ends in `_test` or `_tests` (or starts with `test_`); never use production credentials/data:

```bash
export DATABASE_URL='postgresql+psycopg://TEST_USER:TEST_PASSWORD@TEST_HOST:5432/clarity_checker_test'
export TEST_DATABASE_URL="$DATABASE_URL"
python -m alembic -c backend/alembic.ini check
python -m pytest -q backend/tests
```

Also verify readiness, persistence after a disposable-container restart, and that the app's PostgreSQL role is not a superuser. The workflow's checked assertion can be used as the reference. Do not share the throwaway env file, connection string, or full `docker inspect` output; they can expose credentials.

## Off-host backup and restore evidence

The owner-approved policy is daily encrypted off-host copies, 30-day retention, 24-hour RPO, 4-hour RTO, and quarterly restore drills. The owner requires all backup/DR copies to stay in Pakistan and accepts any verified local backup method; S3-compatible storage is optional, and provider-native service may be evaluated. Provider, failure-domain/account separation, and actual configuration remain open, as do target-host scheduling/alerts and successful drill evidence. The systemd units in `infra/systemd/` are templates, not an installed schedule. A provider-native alternative to the `rclone` wrapper needs a documented, monitored implementation and equivalent isolated restore evidence.

Before testing these `rclone` wrappers, the owner/operator must select an approved, genuinely off-host in-country destination and configure a **dedicated test prefix** separate from any production prefix. Use synthetic rows/photos and a disposable Compose project/host. The backup helper pauses app/Caddy services that are running. Never share the remote credential configuration or age private identity. If a provider-native backup service is selected instead, do not treat this wrapper test as its verification; first document the alternative implementation and repeat equivalent scope, encryption, retention, alerting and timed isolated-restore tests.

Run `scripts/backup_offsite.sh` on the disposable stack with `BACKUP_REMOTE` set to the dedicated test prefix, `BACKUP_AGE_RECIPIENT` set to the test public recipient, and `BACKUP_RETENTION_DAYS=30`. Verify the command reports `Off-site backup verified`, the remote read-back/checksum comparison succeeds, only expired matching test backup sets are pruned, and the local encrypted staging set is removed after success. Confirm that a deliberately failed upload does not prune prior sets, keeps the encrypted local staging set, and attempts to remove any incomplete remote set (check the warning if remote cleanup fails). Record command exit status, broad completion time, and retention result; redact the remote name/path.

For a restore drill, use a separate isolated VM or host, a unique `COMPOSE_PROJECT_NAME`, a firewalled test hostname/network, and a test mail sink. Use a production backup only if its owner authorizes access to the user data it contains. Run `scripts/restore_offsite.sh` with the explicitly selected backup-set name and `CONFIRM_RESTORE=YES`; never run it against the live production Compose project for a drill. Verify the database and representative photo access, health endpoints, and all required checks. Record the backup point, start/end times, elapsed recovery time, data-integrity checks, operator/reviewer, issues, and corrective actions. Measure the end-to-end duration against 4 hours; a successful CI restore is not a quarterly production-data restore drill.

## Suggested redacted result template

```text
Commit SHA:
Hosted workflow run ID:
Hosted job results (job: conclusion):
Container report artifact present: yes/no; built API fixable HIGH/CRITICAL summary:
Accessibility artifacts present: chromium / firefox / webkit:
Docker/Compose version (optional):
PostgreSQL migration/integration result:
Off-host backup test (synthetic only): exit code; verified read-back; retention result; broad elapsed time:
Restore drill (isolated): snapshot age; exit code; elapsed time; checks passed/failed; reviewer; remediation:
Redacted failure excerpt:
```
