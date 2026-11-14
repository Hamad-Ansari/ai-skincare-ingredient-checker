# Deployment guide — single Linux host with Docker Compose

> **Status: deployment scaffold, not production approval.** Milestone 10 adds a single-host Compose path with PostgreSQL, Caddy TLS termination, persistent private-photo storage, health checks, and encrypted backup/restore helpers. It has **not** been exercised with Docker or PostgreSQL in this workspace. Do not put real users or scans on it until the deployment checklist is signed and the M9 safety, security, browser, database, and evaluation gates are closed.

## Intended topology and limits

```text
Internet -- HTTPS :443 / HTTP :80 --> Caddy --> FastAPI (private container port 8000)
                                                   |-- PostgreSQL 17 (private network only)
                                                   `-- private scan-photo named volume
```

- This is a **single Linux VM** template. Only Caddy publishes host ports. PostgreSQL and FastAPI have no published ports.
- Caddy obtains and renews public certificates automatically for the configured DNS hostname. TLS terminates at Caddy; Uvicorn trusts forwarded headers only from its Docker network. Do not publish the FastAPI port or attach untrusted containers to the private network.
- The API runs one Uvicorn worker. Rate limiting is process-local and photo storage is a local Docker volume; do not add workers, replicas, or another host without replacing those components with shared implementations.
- The template requires PostgreSQL, a working SMTP relay, a public DNS name, Docker Engine/Compose, and ports 80/443. It does not add an Ollama/Qdrant service or cloud LLM credentials.
- **OCR is not enabled in the current image.** The Dockerfile does not install Tesseract; image submissions remain reviewable, but OCR will report unavailable until a reviewed image build includes the engine and has live OCR evaluation.
- The production ingredient/rule/evidence corpus remains empty. No scan result or “no finding” can be represented as evidence of safety.

## Host and DNS preparation

The current decision is Pakistan-only hosting; any Pakistan location is acceptable, and all backup/DR copies must also remain in Pakistan. Google Compute Engine's published region list has no Pakistan location. See [`HOSTING_RECOMMENDATION.md`](HOSTING_RECOMMENDATION.md) and the [`HOSTING_VENDOR_RFQ.md`](HOSTING_VENDOR_RFQ.md) quote worksheet. No local provider, quote, project, domain, or host has been selected or provisioned.

1. Use a patched Linux host with Docker Engine and the Docker Compose plugin installed from the official Docker instructions. Restrict SSH to administrator IPs/keys.
2. Point the domain's `A` record (and `AAAA` record only if IPv6 ingress works) at the host. Set `SITE_ADDRESS` to the hostname alone, without a scheme, port, or path.
3. Permit inbound TCP 80 and 443. UDP 443 is optional for HTTP/3. Do not expose TCP 5432 or 8000. Permit outbound HTTPS for Caddy ACME and any deliberately configured provider, plus SMTP STARTTLS (normally TCP 587).
4. Use an encrypted host disk/volume and limit Docker/host access to trusted operators. Docker named volumes are **not** application-level encrypted; private label photos are personal data.

## Configure and start a fresh deployment

Run commands from the repository root on the host:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -hex 32
```

Generate three separate 32-byte hexadecimal values and use them for `APP_SECRET_KEY`, `POSTGRES_ADMIN_PASSWORD`, and `APP_DB_PASSWORD`. Hex characters avoid reserved characters in the PostgreSQL connection URL. Edit `.env.production` and replace every example value:

- `SITE_ADDRESS`: the DNS name above.
- `APP_IMAGE_TAG`: a unique, reviewed release tag; do not reuse `local` for a public deployment.
- `POSTGRES_DB`, `POSTGRES_ADMIN_USER`, `POSTGRES_ADMIN_PASSWORD`: PostgreSQL database and bootstrap administrator.
- `APP_DB_USER`, `APP_DB_PASSWORD`: separate runtime/migration account. The initialization script creates it as a non-superuser and makes it owner of this application database. The API does not receive the PostgreSQL bootstrap administrator credentials.
- `MAIL_HOST`, `MAIL_FROM`, and, if needed, `MAIL_USERNAME` plus `MAIL_PASSWORD`: a real mail relay supporting STARTTLS. Username and password must either both be set or both left blank. The sample host/sender are placeholders and will not deliver mail.

The Compose file fixes production mode, disables development token exposure, sets the same-origin HTTPS allowlist, and requires SMTP. Compose injects secrets as container environment variables; host root and Docker administrators can inspect them. Protect `.env.production` and the host accordingly. For managed secrets, add a reviewed secret-file/secret-manager integration rather than committing credentials.

Validate the resolved deployment configuration before starting:

```bash
docker compose --env-file .env.production config --quiet
```

Build/pull the services and run the database initialization and migrations explicitly:

```bash
docker compose --env-file .env.production pull db caddy
docker compose --env-file .env.production --profile ops pull scan-export scan-list scan-restore
docker compose --env-file .env.production build --pull app migrate
docker compose --env-file .env.production up -d db
# On a fresh, empty PostgreSQL volume, the init script creates the restricted app role.
docker compose --env-file .env.production --profile ops run --rm migrate
docker compose --env-file .env.production up -d app caddy
docker compose --env-file .env.production ps
```

Confirm the database is healthy and the app/Caddy are running before proceeding. The migration service is intentionally operator-run rather than an application-start side effect. For an **existing** deployment, take and verify a backup before running migrations.

Smoke checks from an external machine:

```bash
curl --fail "https://$SITE_ADDRESS/health/live"
curl --fail "https://$SITE_ADDRESS/health/ready"
curl --fail "https://$SITE_ADDRESS/"
curl --head "https://$SITE_ADDRESS/"
```

Confirm `/docs` and `/openapi.json` are not exposed in production; verify TLS and secure session cookies in a real browser; perform a test registration and password reset through the configured mail relay. Passing these checks is not launch approval.

### Database initialization and credentials

`infra/postgres/10-app-role.sh` runs only when PostgreSQL initializes an empty `postgres_data` volume. It creates the restricted app role, transfers ownership of the app database to it, and grants only the needed database connection. Editing `.env.production` later does **not** rotate existing PostgreSQL roles or passwords. Rotate credentials with a reviewed SQL procedure and coordinate the app configuration; do not delete the database volume to apply a password change.

The app runs Alembic migrations with the same non-superuser database owner account. PostgreSQL and image data persist in named volumes. `docker compose down` keeps them; **do not** run `docker compose down -v` except for an explicitly approved, destructive teardown after verified backups and data-deletion review.

## Backups and restore

**Owner-approved baseline:** encrypted off-host backups every day, 30-day retention, 24-hour RPO, 4-hour RTO, and quarterly restore drills. The owner requires the primary host and **all backup/DR copies to remain in Pakistan** and accepts any verified in-country backup approach, including provider-native service. S3-compatible storage was an earlier preference, not a current requirement. No provider, location/account separation, bucket/prefix, or target-host configuration is selected. The policy does **not** mean a real destination or schedule is configured, alerting works, a restore has been drilled, or recovery targets have been met. Those are deployment blockers. Do not store real scans until the actual in-country destination, access controls, scheduled job, completion alerts, and first successful isolated restore are verified. Any provider-native alternative to the `rclone` wrapper must have a reviewed implementation/runbook and pass the same end-to-end restore tests.

The backup covers the PostgreSQL database and private scan-photo volume. It does not back up `.env.production`, encryption identities, Compose/source files, built images, or Caddy's certificate/config volumes; keep the release, configuration, and secrets in separately protected recovery procedures. It also does not encrypt the live Docker volumes. Protect the host with disk encryption and operator access controls.

### Configure encrypted off-host backups (current `rclone` implementation)

These steps describe only the repository's current `rclone` implementation; they do not configure or validate a provider-native backup service. If provider-native backup is chosen, use a separately reviewed provider-specific runbook and equivalent end-to-end encryption, scope, retention, monitoring, and restore tests. For the `rclone` path, the scripts require Docker Compose, `age`, `sha256sum`, and `rclone` for off-host transfer. `age` encrypts the database dump and photo archive on the host before transfer; the remote's transport, identity/access policy, and any storage-side encryption must also be checked for the chosen provider. Keep the age private identity in a separate, access-controlled recovery location (with an independently protected recovery copy); only the public recipient belongs on the deployment host. Never put the private identity or remote credentials in this repository, `.env.production`, or a report. Configure `rclone` under the same service account that will run the job, treat its config as credential material (owner-only permissions such as root/0600), and restrict credentials to a **dedicated remote prefix** for this deployment/environment.

On a trusted workstation, create and securely preserve the age identity; copy only the public recipient (`age1...`) to the deployment host:

```bash
umask 077
age-keygen -o clarity-backup-identity.txt
chmod 600 clarity-backup-identity.txt
age-keygen -y clarity-backup-identity.txt
```

After the owner/operator chooses and configures a real off-host destination, set `BACKUP_REMOTE` to its dedicated prefix (example syntax only):

```text
remote:bucket/clarity-checker-production
```

Do not use a shared bucket/root or a local path as proof of off-host protection. The operator must verify the actual provider, region/location, access controls, transport security, version/deletion behavior, and that it is physically/account-wise separate from the deployment host. Keep the staging directory on a protected filesystem with sufficient space; the default `./backups/` is local staging, not off-host protection. An upload or verification failure deliberately leaves the encrypted local snapshot for a controlled retry; remove it only after confirming a valid remote copy or an approved disposition.

`scripts/backup_offsite.sh` creates the local encrypted snapshot, uploads it, downloads/compares it with `rclone check --download`, and only then prunes matching Clarity backup sets older than `BACKUP_RETENTION_DAYS` (default `30`) inside the configured prefix. Use a dedicated prefix because retention is destructive within that path. The local staging snapshot is deleted only after verification and retention succeed. The helper does not send failure alerts or establish that a run completed within the RPO.

A systemd service/timer template is provided at `infra/systemd/clarity-checker-backup.{service,timer}`. It expects the checkout at `/opt/clarity-checker`, a root-controlled `/etc/clarity-checker/backup.env` with the public age recipient and dedicated `BACKUP_REMOTE`, `rclone` configured for the service account, and a protected staging directory. The example timer is daily at 02:00 UTC; confirm or change the run window with the operator. The unit is **not installed or enabled** by this repository and has not been validated on the target host. The unit itself provides no alerting; monitor failed runs and alert if the last verified backup is approaching or exceeds 24 hours.

After choosing a destination and installing prerequisites on the target host, install/configure the host-specific environment file and unit templates. The following assumes the checkout is at `/opt/clarity-checker`; adjust paths if necessary. Do not start the job until the remote and age recipient are set and the service account's `rclone` configuration has been tested:

```bash
sudo install -d -m 700 /etc/clarity-checker /var/lib/clarity-checker/staging
sudo install -m 600 /dev/null /etc/clarity-checker/backup.env
sudoedit /etc/clarity-checker/backup.env
# Set BACKUP_AGE_RECIPIENT=age1..., BACKUP_REMOTE=remote:bucket/clarity-checker-production,
# and BACKUP_RETENTION_DAYS=30. These are examples; use the owner-approved destination.
# Configure rclone for the service account; do not paste its credentials into a ticket or chat.
sudo install -m 644 /opt/clarity-checker/infra/systemd/clarity-checker-backup.service /etc/systemd/system/
sudo install -m 644 /opt/clarity-checker/infra/systemd/clarity-checker-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start clarity-checker-backup.service
sudo journalctl -u clarity-checker-backup.service --since today
# Only after the manual run is reviewed and the destination is verified:
sudo systemctl enable --now clarity-checker-backup.timer
sudo systemctl list-timers clarity-checker-backup.timer
```

Confirm the timer is scheduled, the service exits successfully, the verified remote set is present, retention prunes only expired Clarity sets, and an independent monitor alerts on failure/staleness. The current template expects `/opt/clarity-checker`; adjust the unit if the deployment path differs. A daily timer alone does not prove the 24-hour RPO, especially during downtime or a failed/long-running backup.

### Restore and quarterly drill

**Restore is destructive.** It overwrites the target Compose project's application database and private scan-photo volume. `scripts/restore_offsite.sh` downloads a named remote set, validates its checksum manifest, and then invokes `scripts/restore_production.sh`, which preflights decryptability before stopping traffic. A failure during the destructive phase intentionally leaves the app/Caddy stopped. Do not run this against the live production project for a drill.

Run each quarterly drill on an isolated host/VM with a unique Compose project name and no public ingress; use approved access controls for the production snapshot, which contains user data. Keep email/provider integrations disabled or directed to test services. Example after selecting a set and installing the required age identity on that isolated host:

```bash
COMPOSE_PROJECT_NAME=clarity-checker-restore-drill \
CONFIRM_RESTORE=YES \
AGE_IDENTITY_FILE=/secure/offline/identity.txt \
BACKUP_REMOTE=remote:bucket/clarity-checker-production \
ENV_FILE=/secure/restore-drill/.env.production \
scripts/restore_offsite.sh clarity-checker-YYYYMMDDThhmmssZ.ABC123
```

Keep the drill host firewalled and isolated: the restore helper starts the app and Caddy after restoring, and Caddy's Compose ports are 80/443. Verify the restored database, representative private-photo access, health endpoints, and required operational state; time the complete recovery and compare it with the 4-hour RTO. Record the snapshot timestamp/data point, elapsed time, checks, operator/reviewer, failures, corrective actions, and approval without including secrets or user data. Repeat quarterly and after material storage/restore changes. The target RPO/RTO remain unproven until measured drills and monitored successful backups provide evidence.

## Health, logs, updates, and operations

- PostgreSQL has a `pg_isready` health check. FastAPI's container check calls `/health/ready`; external uptime checks should probe both `/health/live` and `/health/ready` over HTTPS. Readiness reveals only `ok`/`not_ready`.
- Docker JSON logs rotate at 10 MB × 5 files per container. Uvicorn access logging is disabled to avoid routinely retaining request paths/IPs; Caddy access logs are not enabled by this template. Application warnings/errors are sent to container stdout/stderr with request IDs. Protect logs and set an approved host/log retention policy; do not enable body, cookie, token, email, or photo logging.
- Monitor host disk, memory, container health/restarts, Postgres volume growth, private-photo volume growth, backup completion, external TLS/availability, and SMTP delivery. There is no metrics backend, paging integration, database HA, or tested restore monitoring in this scaffold.
- For a release: verify the new image/tag and notes, take a backup, build/pull, run migrations explicitly, restart app/Caddy, then verify health, TLS, mail, and key user flows. Keep the previous image tag available for rollback; database migrations may not be reversible, so rollback requires a tested database restore plan.
- The current `postgres:17-alpine`, `caddy:2-alpine`, `busybox:1.37.0`, and Python base image tags are not digest-pinned. Review upstream updates and vulnerability notices; pin tested digests for an actual controlled release and establish a patch cadence.
- If the Docker daemon or host restarts, `unless-stopped` services start again. The Compose health checks do not by themselves alert an operator.

## Release gates

Before launch, complete and sign [`DEPLOYMENT_CHECKLIST.md`](DEPLOYMENT_CHECKLIST.md). The owner has selected no public source-code license (no `LICENSE` file); confirm ownership/contributor rights and release notices before any distribution. The backup-policy baseline is approved, but destination configuration, target-host scheduling/alerting, and quarterly restore-drill evidence remain open. PostgreSQL/Docker execution, hosted CI, CVE review, browser/accessibility work, rights-cleared evaluation data, OCR/provider assessment, legal/domain-expert review, privacy/retention, and incident/restore readiness also remain release gates. See [`MILESTONE_9.md`](MILESTONE_9.md) and [`MILESTONE_11.md`](MILESTONE_11.md) for local QA evidence and limitations. Use the [external verification handoff](EXTERNAL_VERIFICATION_HANDOFF.md) for hosted CI, Docker/PostgreSQL, backup/restore evidence, and safe redaction instructions.

References: [Docker Compose installation](https://docs.docker.com/compose/install/), [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https), [age](https://github.com/FiloSottile/age), and [PostgreSQL container image](https://hub.docker.com/_/postgres).
