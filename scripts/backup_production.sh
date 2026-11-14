#!/usr/bin/env bash
# Stream a Compose PostgreSQL and private-scan backup directly into age encryption.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env.production}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
: "${BACKUP_AGE_RECIPIENT:?Set BACKUP_AGE_RECIPIENT to an age public recipient}"

for command_name in docker age sha256sum; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'Required command not found: %s\n' "$command_name" >&2
        exit 1
    }
done
[[ -f "$ENV_FILE" ]] || { printf 'Missing env file: %s\n' "$ENV_FILE" >&2; exit 1; }

cd "$ROOT"
COMPOSE=(docker compose --env-file "$ENV_FILE")
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" up -d db

# Stop user writes so the database snapshot and image volume describe one point in time.
RUNNING_SERVICES="$("${COMPOSE[@]}" ps --status running --services 2>/dev/null || true)"
APP_WAS_RUNNING=0
CADDY_WAS_RUNNING=0
if grep -Fxq app <<<"$RUNNING_SERVICES"; then APP_WAS_RUNNING=1; fi
if grep -Fxq caddy <<<"$RUNNING_SERVICES"; then CADDY_WAS_RUNNING=1; fi

BACKUP_SET=""
DB_PART=""
SCANS_PART=""
restart_after_backup() {
    local status=$?
    trap - EXIT
    [[ -n "$DB_PART" ]] && rm -f -- "$DB_PART"
    [[ -n "$SCANS_PART" ]] && rm -f -- "$SCANS_PART"
    if (( APP_WAS_RUNNING )); then
        "${COMPOSE[@]}" up -d app >/dev/null || {
            printf 'WARNING: app restart failed; inspect Compose status.\n' >&2
            status=1
        }
    fi
    if (( CADDY_WAS_RUNNING )); then
        "${COMPOSE[@]}" up -d caddy >/dev/null || {
            printf 'WARNING: Caddy restart failed; inspect Compose status.\n' >&2
            status=1
        }
    fi
    exit "$status"
}
trap restart_after_backup EXIT

TO_STOP=()
if (( CADDY_WAS_RUNNING )); then TO_STOP+=(caddy); fi
if (( APP_WAS_RUNNING )); then TO_STOP+=(app); fi
if ((${#TO_STOP[@]})); then
    "${COMPOSE[@]}" stop "${TO_STOP[@]}" >/dev/null
fi

umask 077
mkdir -p -- "$BACKUP_DIR"
chmod 700 -- "$BACKUP_DIR"
BACKUP_SET="$(mktemp -d "$BACKUP_DIR/clarity-checker-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")"
chmod 700 -- "$BACKUP_SET"
DB_PART="$BACKUP_SET/database.dump.age.partial"
SCANS_PART="$BACKUP_SET/private-scans.tar.gz.age.partial"

# age reads stdin; plaintext dumps/archives are never written to disk.
"${COMPOSE[@]}" exec -T db sh -ec \
    'pg_dump --format=custom --no-owner --username "$APP_DB_USER" --dbname "$POSTGRES_DB"' \
    | age --recipient "$BACKUP_AGE_RECIPIENT" --output "$DB_PART"
"${COMPOSE[@]}" --profile ops run --rm --no-deps scan-volume-init >/dev/null
"${COMPOSE[@]}" --profile ops run --rm --no-deps -T scan-export \
    | age --recipient "$BACKUP_AGE_RECIPIENT" --output "$SCANS_PART"

mv -- "$DB_PART" "$BACKUP_SET/database.dump.age"
mv -- "$SCANS_PART" "$BACKUP_SET/private-scans.tar.gz.age"
DB_PART=""
SCANS_PART=""
(
    cd "$BACKUP_SET"
    sha256sum database.dump.age private-scans.tar.gz.age > SHA256SUMS
)
printf 'Encrypted backup set created: %s\n' "$BACKUP_SET"
printf 'This local helper does not upload or prune backups; use scripts/backup_offsite.sh for off-host transfer/retention, and configure a host scheduler separately.\n'
