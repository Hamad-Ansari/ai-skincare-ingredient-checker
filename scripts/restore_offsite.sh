#!/usr/bin/env bash
# Download and verify one retained off-site backup, then invoke the guarded destructive restore.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env.production}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"
AGE_IDENTITY_FILE="${AGE_IDENTITY_FILE:-}"
BACKUP_NAME="${1:-}"
BACKUP_NAME_PATTERN='^clarity-checker-([0-9]{8})T([0-9]{6})Z\.([[:alnum:]]{6})$'

[[ "${CONFIRM_RESTORE:-}" == YES ]] || {
    printf 'Refusing destructive off-site restore. Set CONFIRM_RESTORE=YES after reviewing the target.\n' >&2
    exit 2
}
: "${BACKUP_REMOTE:?Set BACKUP_REMOTE to the configured rclone remote path}"
: "${AGE_IDENTITY_FILE:?Set AGE_IDENTITY_FILE to the private age identity file}"
[[ "$BACKUP_NAME" =~ $BACKUP_NAME_PATTERN ]] || {
    printf 'Supply a backup-set name created by scripts/backup_offsite.sh.\n' >&2
    exit 2
}
[[ -r "$AGE_IDENTITY_FILE" ]] || { printf 'Cannot read age identity file.\n' >&2; exit 1; }

for command_name in rclone age sha256sum docker; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'Required command not found: %s\n' "$command_name" >&2
        exit 1
    }
done
[[ -f "$ENV_FILE" ]] || { printf 'Missing env file: %s\n' "$ENV_FILE" >&2; exit 1; }
while [[ "$BACKUP_REMOTE" == */ ]]; do BACKUP_REMOTE="${BACKUP_REMOTE%/}"; done
REMOTE_NAME="${BACKUP_REMOTE%%:*}"
REMOTE_PATH="${BACKUP_REMOTE#*:}"
VALIDATION_PATH="${REMOTE_PATH#/}"
if [[ "$REMOTE_NAME" == "$BACKUP_REMOTE" || ! "$REMOTE_NAME" =~ ^[A-Za-z0-9_-]+$ || "$VALIDATION_PATH" != */* || "$BACKUP_REMOTE" == *$'\n'* || "$BACKUP_REMOTE" == *$'\r'* ]]; then
    printf 'BACKUP_REMOTE must be a named rclone remote plus its dedicated path.\n' >&2
    exit 1
fi
IFS='/' read -r -a REMOTE_PARTS <<< "$VALIDATION_PATH"
for remote_part in "${REMOTE_PARTS[@]}"; do
    if [[ -z "$remote_part" || "$remote_part" == . || "$remote_part" == .. ]]; then
        printf 'BACKUP_REMOTE must not contain empty, dot, or dot-dot path segments.\n' >&2
        exit 1
    fi
done

umask 077
mkdir -p -- "$BACKUP_DIR"
chmod 700 -- "$BACKUP_DIR"
STAGING_ROOT="$(mktemp -d "$BACKUP_DIR/offsite-restore.XXXXXXXX")"
chmod 700 -- "$STAGING_ROOT"
cleanup() {
    rm -rf -- "$STAGING_ROOT"
}
trap cleanup EXIT
LOCAL_SET="$STAGING_ROOT/$BACKUP_NAME"
mkdir -m 700 -- "$LOCAL_SET"
REMOTE_SET="${BACKUP_REMOTE%/}/$BACKUP_NAME"

rclone copy "$REMOTE_SET" "$LOCAL_SET" --checksum
for file_name in database.dump.age private-scans.tar.gz.age SHA256SUMS; do
    [[ -f "$LOCAL_SET/$file_name" ]] || {
        printf 'Downloaded backup is missing %s\n' "$file_name" >&2
        exit 1
    }
done
(
    cd "$LOCAL_SET"
    sha256sum --check SHA256SUMS
)

# The companion restore script decrypts only into streaming PostgreSQL/tar processes and requires explicit confirmation.
CONFIRM_RESTORE=YES AGE_IDENTITY_FILE="$AGE_IDENTITY_FILE" ENV_FILE="$ENV_FILE" \
    "$ROOT/scripts/restore_production.sh" "$LOCAL_SET"
printf 'Off-site restore staging removed; the remote backup remains intact.\n'
