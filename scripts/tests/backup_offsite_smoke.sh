#!/usr/bin/env bash
# Isolated smoke test for off-site upload, read-back verification, retention, and local staging cleanup.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP="$(mktemp -d)"
cleanup() { rm -rf -- "$TMP"; }
trap cleanup EXIT
BIN="$TMP/bin"
REMOTE_ROOT="$TMP/remote/clarity-checker-production"
BACKUP_DIR="$TMP/local-staging"
mkdir -p -- "$BIN" "$REMOTE_ROOT/clarity-checker-20200101T000000Z.ABC123" "$REMOTE_ROOT/not-a-clarity-backup"
printf 'expired payload\n' > "$REMOTE_ROOT/clarity-checker-20200101T000000Z.ABC123/old.age"
printf 'leave unrelated remote data alone\n' > "$REMOTE_ROOT/not-a-clarity-backup/sentinel.txt"
printf 'test-only compose environment\n' > "$TMP/.env.production"

cat > "$BIN/docker" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
args=" $* "
case "$args" in
  *" ps --status running --services "*) printf 'app\ncaddy\n' ;;
  *" exec -T db sh -ec "*) printf 'test-only-postgres-dump\n' ;;
  *" scan-export "*) printf 'test-only-photo-archive\n' ;;
  *) exit 0 ;;
esac
SH

cat > "$BIN/age" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${1:-}" == --recipient ]] || exit 2
shift 2
[[ "${1:-}" == --output ]] || exit 2
output="$2"
mkdir -p -- "$(dirname -- "$output")"
cat > "$output"
SH

cat > "$BIN/rclone" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
remote_to_local() {
  [[ "$1" == test:* ]] || { printf 'unexpected test remote: %s\n' "$1" >&2; exit 2; }
  printf '%s' "${1#test:}"
}
case "${1:-}" in
  mkdir)
    mkdir -p -- "$(remote_to_local "$2")"
    ;;
  copy)
    source="$2"
    destination="$(remote_to_local "$3")"
    if [[ "${RCLONE_FAIL_COPY:-}" == 1 ]]; then
      mkdir -p -- "$destination"
      cp -- "$source/database.dump.age" "$destination/"
      exit 9
    fi
    mkdir -p -- "$(dirname -- "$destination")"
    cp -a -- "$source" "$destination"
    ;;
  check)
    shift
    [[ "${1:-}" == --download ]] && shift
    source="$1"
    destination="$(remote_to_local "$2")"
    diff -qr -- "$source" "$destination"
    ;;
  lsf)
    shift
    [[ "${1:-}" == --dirs-only ]] && shift
    target="$(remote_to_local "$1")"
    find "$target" -mindepth 1 -maxdepth 1 -type d -printf '%f/\n' | sort
    ;;
  purge)
    rm -rf -- "$(remote_to_local "$2")"
    ;;
  *)
    printf 'unsupported fake-rclone command: %s\n' "${1:-}" >&2
    exit 2
    ;;
esac
SH
chmod 700 "$BIN/docker" "$BIN/age" "$BIN/rclone"

# A failed remote copy must preserve both old remote sets and the new encrypted local staging set.
if PATH="$BIN:$PATH" RCLONE_FAIL_COPY=1 \
    ENV_FILE="$TMP/.env.production" \
    BACKUP_DIR="$BACKUP_DIR" \
    BACKUP_REMOTE="test:$REMOTE_ROOT" \
    BACKUP_RETENTION_DAYS=30 \
    BACKUP_AGE_RECIPIENT=age1-test-recipient \
    "$ROOT/scripts/backup_offsite.sh" > "$TMP/upload-failure.log" 2>&1; then
  printf 'Injected remote-copy failure unexpectedly succeeded.\n' >&2
  exit 1
fi
[[ -d "$REMOTE_ROOT/clarity-checker-20200101T000000Z.ABC123" ]] || {
  printf 'An old remote set was pruned after upload failure.\n' >&2
  exit 1
}
REMOTE_SET_COUNT="$(find "$REMOTE_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'clarity-checker-*' | wc -l)"
[[ "$REMOTE_SET_COUNT" == 1 ]] || {
  printf 'An incomplete remote backup set was left after injected upload failure.\n' >&2
  exit 1
}
STAGED_SET="$(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name 'clarity-checker-*' -print -quit)"
[[ -n "$STAGED_SET" && -f "$STAGED_SET/database.dump.age" && -f "$STAGED_SET/private-scans.tar.gz.age" ]] || {
  printf 'Encrypted local staging set was not preserved after upload failure.\n' >&2
  exit 1
}
rm -rf -- "$STAGED_SET"

PATH="$BIN:$PATH" \
ENV_FILE="$TMP/.env.production" \
BACKUP_DIR="$BACKUP_DIR" \
BACKUP_REMOTE="test:$REMOTE_ROOT" \
BACKUP_RETENTION_DAYS=30 \
BACKUP_AGE_RECIPIENT=age1-test-recipient \
"$ROOT/scripts/backup_offsite.sh"

[[ ! -e "$REMOTE_ROOT/clarity-checker-20200101T000000Z.ABC123" ]] || {
  printf 'Expired Clarity backup was not pruned.\n' >&2
  exit 1
}
[[ -f "$REMOTE_ROOT/not-a-clarity-backup/sentinel.txt" ]] || {
  printf 'Unrelated remote directory was removed.\n' >&2
  exit 1
}
NEW_SET="$(find "$REMOTE_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'clarity-checker-*' -print -quit)"
[[ -n "$NEW_SET" && -f "$NEW_SET/database.dump.age" && -f "$NEW_SET/private-scans.tar.gz.age" && -f "$NEW_SET/SHA256SUMS" ]] || {
  printf 'Verified remote backup set is incomplete.\n' >&2
  exit 1
}
[[ -z "$(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]] || {
  printf 'Local staging artifacts were not removed after verification.\n' >&2
  exit 1
}

if PATH="$BIN:$PATH" \
    ENV_FILE="$TMP/.env.production" \
    BACKUP_DIR="$BACKUP_DIR" \
    BACKUP_REMOTE="test:$TMP/remote/../escaped-prefix" \
    BACKUP_RETENTION_DAYS=30 \
    BACKUP_AGE_RECIPIENT=age1-test-recipient \
    "$ROOT/scripts/backup_offsite.sh" > "$TMP/path-traversal.log" 2>&1; then
  printf 'Path-traversal remote prefix was unexpectedly accepted.\n' >&2
  exit 1
fi
[[ -z "$(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]] || {
  printf 'Invalid remote path created local staging artifacts.\n' >&2
  exit 1
}
[[ -f "$NEW_SET/database.dump.age" ]] || {
  printf 'Invalid remote path affected the verified remote backup.\n' >&2
  exit 1
}
RESTORE_NAME="$(basename -- "$NEW_SET")"
if CONFIRM_RESTORE=NO "$ROOT/scripts/restore_offsite.sh" "$RESTORE_NAME" > "$TMP/restore-guard.log" 2>&1; then
  printf 'Off-site restore unexpectedly passed without explicit confirmation.\n' >&2
  exit 1
else
  restore_status=$?
  [[ "$restore_status" == 2 ]] || {
    printf 'Off-site restore failed with unexpected guard status: %s\n' "$restore_status" >&2
    exit 1
  }
fi
printf 'Off-site backup smoke passed (fake Docker/age/rclone; tested upload failure, safe retention, path traversal rejection, restore confirmation guard, and staging cleanup; no real data, encryption, or remote service used).\n'
