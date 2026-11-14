#!/usr/bin/env bash
# Create an age-encrypted Compose snapshot, verify its off-site copy, and prune only old Clarity backup sets.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env.production}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
: "${BACKUP_AGE_RECIPIENT:?Set BACKUP_AGE_RECIPIENT to an age public recipient}"
: "${BACKUP_REMOTE:?Set BACKUP_REMOTE to a dedicated configured rclone remote path}"

for command_name in docker age sha256sum rclone; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'Required command not found: %s\n' "$command_name" >&2
        exit 1
    }
done
[[ "$BACKUP_RETENTION_DAYS" =~ ^[1-9][0-9]*$ ]] || {
    printf 'BACKUP_RETENTION_DAYS must be a positive whole number.\n' >&2
    exit 1
}
[[ -f "$ENV_FILE" ]] || { printf 'Missing env file: %s\n' "$ENV_FILE" >&2; exit 1; }

# Require a named rclone remote and a dedicated non-root prefix; reject path traversal before any remote mutation.
while [[ "$BACKUP_REMOTE" == */ ]]; do BACKUP_REMOTE="${BACKUP_REMOTE%/}"; done
REMOTE_NAME="${BACKUP_REMOTE%%:*}"
REMOTE_PATH="${BACKUP_REMOTE#*:}"
VALIDATION_PATH="${REMOTE_PATH#/}"
if [[ "$REMOTE_NAME" == "$BACKUP_REMOTE" || ! "$REMOTE_NAME" =~ ^[A-Za-z0-9_-]+$ || "$VALIDATION_PATH" != */* || "$BACKUP_REMOTE" == *$'\n'* || "$BACKUP_REMOTE" == *$'\r'* ]]; then
    printf 'BACKUP_REMOTE must be a named rclone remote plus a dedicated path, e.g. remote:bucket/clarity-checker-production.\n' >&2
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
RUN_LOG="$(mktemp "$BACKUP_DIR/.offsite-backup.XXXXXXXX")"
chmod 600 -- "$RUN_LOG"
cleanup() {
    rm -f -- "$RUN_LOG"
}
trap cleanup EXIT

# Keep the local encrypted set if the upload/verification fails, so an operator can retry it.
if ! ENV_FILE="$ENV_FILE" BACKUP_DIR="$BACKUP_DIR" BACKUP_AGE_RECIPIENT="$BACKUP_AGE_RECIPIENT" \
    "$ROOT/scripts/backup_production.sh" | tee "$RUN_LOG"; then
    printf 'Local encrypted backup failed; no remote retention was applied.\n' >&2
    exit 1
fi
BACKUP_SET="$(sed -n 's/^Encrypted backup set created: //p' "$RUN_LOG" | tail -n 1)"
[[ -n "$BACKUP_SET" && -d "$BACKUP_SET" ]] || {
    printf 'Could not locate the newly created local backup set in the backup output.\n' >&2
    exit 1
}
BACKUP_NAME="$(basename -- "$BACKUP_SET")"
BACKUP_NAME_PATTERN='^clarity-checker-([0-9]{8})T([0-9]{6})Z\.([[:alnum:]]{6})$'
[[ "$BACKUP_NAME" =~ $BACKUP_NAME_PATTERN ]] || {
    printf 'Unexpected backup-set directory name; refusing remote upload: %s\n' "$BACKUP_NAME" >&2
    exit 1
}

REMOTE_SET="${BACKUP_REMOTE%/}/$BACKUP_NAME"
rclone mkdir "$BACKUP_REMOTE"
REMOTE_ENTRIES_BEFORE_COPY="$(rclone lsf "$BACKUP_REMOTE")"
if grep -Fqx -- "$BACKUP_NAME/" <<< "$REMOTE_ENTRIES_BEFORE_COPY" || \
   grep -Fqx -- "$BACKUP_NAME" <<< "$REMOTE_ENTRIES_BEFORE_COPY"; then
    printf 'Remote backup-set name already exists; refusing to overwrite it: %s\n' "$REMOTE_SET" >&2
    exit 1
fi
if ! rclone copy "$BACKUP_SET" "$REMOTE_SET" --checksum; then
    printf 'Remote upload failed; attempting to remove only this incomplete set.\n' >&2
    rclone purge "$REMOTE_SET" || printf 'WARNING: incomplete remote set may remain and must not be restored: %s\n' "$REMOTE_SET" >&2
    exit 1
fi
# Force a byte-for-byte remote read-back before pruning any previously retained backup.
if ! rclone check --download "$BACKUP_SET" "$REMOTE_SET"; then
    printf 'Remote read-back verification failed; attempting to remove only this unverified set.\n' >&2
    rclone purge "$REMOTE_SET" || printf 'WARNING: unverified remote set may remain and must not be restored: %s\n' "$REMOTE_SET" >&2
    exit 1
fi
printf 'Off-site backup verified: %s\n' "$REMOTE_SET"

RETENTION_CUTOFF="$(date -u -d "$BACKUP_RETENTION_DAYS days ago" +%s)"
REMOTE_DIRS="$(rclone lsf --dirs-only "$BACKUP_REMOTE")"
PRUNED=0
while IFS= read -r entry; do
    [[ -n "$entry" ]] || continue
    candidate="${entry%/}"
    [[ "$candidate" =~ $BACKUP_NAME_PATTERN ]] || continue

    date_part="${BASH_REMATCH[1]}"
    time_part="${BASH_REMATCH[2]}"
    timestamp="${date_part:0:4}-${date_part:4:2}-${date_part:6:2}T${time_part:0:2}:${time_part:2:2}:${time_part:4:2}Z"
    created_at="$(date -u -d "$timestamp" +%s)"
    if (( created_at < RETENTION_CUTOFF )); then
        rclone purge "${BACKUP_REMOTE%/}/$candidate"
        printf 'Pruned expired off-site backup set: %s\n' "$candidate"
        ((PRUNED += 1))
    fi
done <<< "$REMOTE_DIRS"

# The local snapshot is staging only. Keep it if any prior step failed; remove after remote verification/retention succeeds.
rm -rf -- "$BACKUP_SET"
printf 'Off-site retention applied: %s days; expired sets pruned: %s. Local staging snapshot removed.\n' \
    "$BACKUP_RETENTION_DAYS" "$PRUNED"
