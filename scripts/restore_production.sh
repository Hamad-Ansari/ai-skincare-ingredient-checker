#!/usr/bin/env bash
# Destructively restore a matching encrypted Compose database/photo backup set.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env.production}"
AGE_IDENTITY_FILE="${AGE_IDENTITY_FILE:-}"
BACKUP_SET="${1:-}"

if [[ -z "$BACKUP_SET" ]]; then
    printf 'Usage: CONFIRM_RESTORE=YES AGE_IDENTITY_FILE=/secure/path/identity.txt %s BACKUP_SET\n' "$0" >&2
    exit 2
fi
if [[ "${CONFIRM_RESTORE:-}" != YES ]]; then
    printf 'Refusing destructive restore. Set CONFIRM_RESTORE=YES after reviewing the target.\n' >&2
    exit 2
fi
: "${AGE_IDENTITY_FILE:?Set AGE_IDENTITY_FILE to the private age identity file}"

for command_name in docker age sha256sum; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'Required command not found: %s\n' "$command_name" >&2
        exit 1
    }
done
[[ -f "$ENV_FILE" ]] || { printf 'Missing env file: %s\n' "$ENV_FILE" >&2; exit 1; }
[[ -r "$AGE_IDENTITY_FILE" ]] || { printf 'Cannot read age identity file.\n' >&2; exit 1; }
[[ -d "$BACKUP_SET" ]] || { printf 'Backup set directory not found: %s\n' "$BACKUP_SET" >&2; exit 1; }

BACKUP_SET="$(cd -- "$BACKUP_SET" && pwd)"
for file_name in database.dump.age private-scans.tar.gz.age SHA256SUMS; do
    [[ -f "$BACKUP_SET/$file_name" ]] || {
        printf 'Backup set is missing %s\n' "$file_name" >&2
        exit 1
    }
done
(
    cd "$BACKUP_SET"
    sha256sum --check SHA256SUMS
)

cd "$ROOT"
COMPOSE=(docker compose --env-file "$ENV_FILE")
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" up -d db

# Preflight both encrypted streams before stopping traffic or modifying volumes.
age --decrypt --identity "$AGE_IDENTITY_FILE" "$BACKUP_SET/database.dump.age" \
    | "${COMPOSE[@]}" exec -T db pg_restore --list - >/dev/null
"${COMPOSE[@]}" --profile ops run --rm --no-deps scan-volume-init >/dev/null
age --decrypt --identity "$AGE_IDENTITY_FILE" "$BACKUP_SET/private-scans.tar.gz.age" \
    | "${COMPOSE[@]}" --profile ops run --rm --no-deps -T scan-list >/dev/null

printf 'Restoring %s will overwrite the current application database and all private scan photos.\n' "$BACKUP_SET" >&2
RUNNING_SERVICES="$("${COMPOSE[@]}" ps --status running --services 2>/dev/null || true)"
TO_STOP=()
if grep -Fxq caddy <<<"$RUNNING_SERVICES"; then TO_STOP+=(caddy); fi
if grep -Fxq app <<<"$RUNNING_SERVICES"; then TO_STOP+=(app); fi
if ((${#TO_STOP[@]})); then
    "${COMPOSE[@]}" stop "${TO_STOP[@]}" >/dev/null
fi

# A restore failure intentionally leaves app/Caddy stopped to avoid serving a partial restore.
age --decrypt --identity "$AGE_IDENTITY_FILE" "$BACKUP_SET/database.dump.age" \
    | "${COMPOSE[@]}" exec -T db sh -ec \
        'pg_restore --clean --if-exists --no-owner --exit-on-error --username "$APP_DB_USER" --dbname "$POSTGRES_DB" -'
age --decrypt --identity "$AGE_IDENTITY_FILE" "$BACKUP_SET/private-scans.tar.gz.age" \
    | "${COMPOSE[@]}" --profile ops run --rm --no-deps -T scan-restore

"${COMPOSE[@]}" up -d app caddy
printf 'Restore completed. Verify /health/ready, account data, and private-photo access before reopening traffic.\n'
